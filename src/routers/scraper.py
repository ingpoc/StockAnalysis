"""
Router for scraper functionality.
"""
import logging
import asyncio
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, status, Depends, HTTPException, BackgroundTasks
from motor.motor_asyncio import AsyncIOMotorClient

from src.schemas.financial_data import ScrapeRequest, ScrapeResponse, CompanyFinancials
from src.scraper.moneycontrol_scraper import scrape_moneycontrol_earnings, get_company_financials
from src.utils.database import get_database, refresh_database_connection, MONGO_URI
from src.config.settings import get_settings

# Create logger
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/scraper",
    tags=["scraper"]
)

# Background task for scraping
async def background_scrape(request: ScrapeRequest, db_instance=None):
    """
    Background task to perform scraping without blocking the API response.
    
    Args:
        request (ScrapeRequest): Request with URL and result type.
        db_instance: MongoDB database (optional, will create a new connection if None).
    """
    try:
        logger.info(f"Starting background scraping for result_type: {request.result_type}")
        
        # Create a dedicated database connection for the background task
        # to avoid interfering with other operations
        settings = get_settings()
        mongo_client = AsyncIOMotorClient(MONGO_URI)
        db = mongo_client[settings.mongodb_database]
        
        logger.info("Created dedicated database connection for background scraping")
        
        # Get the company financials collection
        companies_collection = db.detailed_financials
        
        # Map result types to their corresponding names and URLs
        result_type_mapping = {
            "LR": {
                "name": "Latest Results",
                "url": "https://www.moneycontrol.com/markets/earnings/latest-results/?tab=LR&subType=yoy"
            },
            "BP": {
                "name": "Best Performer",
                "url": "https://www.moneycontrol.com/markets/earnings/latest-results/?tab=BP&subType=yoy"
            },
            "WP": {
                "name": "Worst Performer",
                "url": "https://www.moneycontrol.com/markets/earnings/latest-results/?tab=WP&subType=yoy"
            },
            "PT": {
                "name": "Positive Turnaround",
                "url": "https://www.moneycontrol.com/markets/earnings/latest-results/?tab=PT&subType=yoy"
            },
            "NT": {
                "name": "Negative Turnaround",
                "url": "https://www.moneycontrol.com/markets/earnings/latest-results/?tab=NT&subType=yoy"
            }
        }
        
        # Determine URL to scrape
        url_to_scrape = None
        result_name = None
        
        # Check if it's a direct stock URL or a result type
        if request.url and ("stockpricequote" in request.url or "stock" in request.url):
            # Direct stock URL provided
            url_to_scrape = request.url
            result_name = "Direct Stock URL"
            logger.info(f"Using provided direct stock URL: {url_to_scrape}")
        elif request.result_type in result_type_mapping:
            # Standard result type
            url_to_scrape = result_type_mapping[request.result_type]["url"]
            result_name = result_type_mapping[request.result_type]["name"]
            logger.info(f"Using standard result type URL for {result_name}: {url_to_scrape}")
        elif request.url:
            # Custom URL provided
            url_to_scrape = request.url
            result_name = "Custom URL"
            logger.info(f"Using custom URL: {url_to_scrape}")
        else:
            # Unknown result type and no URL provided
            error_message = f"Unknown result type '{request.result_type}' and no URL provided"
            logger.error(error_message)
            return
        
        # Log the URL being scraped
        logger.info(f"Background scraping URL: {url_to_scrape} ({result_name})")
        
        # Add a small delay to ensure this doesn't immediately block other operations
        await asyncio.sleep(1)
        
        # Perform the scraping
        scraped_results = await scrape_moneycontrol_earnings(url_to_scrape, companies_collection)
        
        if not scraped_results:
            logger.warning(f"No data scraped from {result_name} in background task")
            return
        
        # Process the scraped data
        companies_count = len(scraped_results)
        logger.info(f"Successfully scraped {companies_count} companies from {result_name} in background task")
        
        # Close the database connection
        mongo_client.close()
        logger.info("Closed dedicated database connection for background scraping")
        
    except Exception as e:
        error_message = f"Error during background scraping: {str(e)}"
        logger.error(error_message)
        # Try to close the database connection in case of error
        try:
            if 'mongo_client' in locals():
                mongo_client.close()
                logger.info("Closed database connection after error")
        except:
            pass

@router.post("/scrape", response_model=ScrapeResponse, status_code=status.HTTP_200_OK)
async def scrape_moneycontrol(request: ScrapeRequest, background_tasks: BackgroundTasks, db=Depends(get_database)):
    """
    Trigger the scraping process in the background and immediately return a response.
    
    Args:
        request (ScrapeRequest): Request with URL and result type.
        background_tasks: FastAPI BackgroundTasks to run the scraping asynchronously.
        db: MongoDB database dependency.
        
    Returns:
        ScrapeResponse: Response with success status.
    """
    try:
        logger.info(f"Received scraping request with result_type: {request.result_type}")
        
        # Determine result name for the response
        result_name = "Custom Scrape"
        if request.result_type in ["LR", "BP", "WP", "PT", "NT"]:
            result_type_mapping = {
                "LR": "Latest Results",
                "BP": "Best Performer",
                "WP": "Worst Performer",
                "PT": "Positive Turnaround",
                "NT": "Negative Turnaround"
            }
            result_name = result_type_mapping.get(request.result_type, "Custom Scrape")
        
        # Add the scraping task to background tasks - don't pass the database instance
        # since the background task will create its own connection
        background_tasks.add_task(background_scrape, request)
        
        # Return an immediate response
        return ScrapeResponse(
            success=True,
            message=f"Scraping process for {result_name} started in the background",
            companies_scraped=0,
            data=None
        )
    
    except Exception as e:
        error_message = f"Error starting scraping process: {str(e)}"
        logger.error(error_message)
        return ScrapeResponse(
            success=False,
            message=error_message,
            companies_scraped=0,
            data=None
        )

@router.get("/companies", response_model=List[Dict[str, Any]], status_code=status.HTTP_200_OK)
async def get_companies(refresh: bool = False, db=Depends(get_database)):
    """
    Get all companies and their financial data.
    
    Args:
        refresh (bool): Whether to refresh the database connection before fetching data.
        db: MongoDB database dependency.
        
    Returns:
        List[Dict[str, Any]]: List of companies with their financial data.
    """
    try:
        # Refresh the database connection if requested
        if refresh:
            logger.info("Refreshing database connection before fetching companies")
            db = await refresh_database_connection()
            
        companies_collection = db.detailed_financials
        logger.info("Retrieving all companies")
        companies = await companies_collection.find({}).to_list(1000)
        logger.info(f"Retrieved {len(companies)} companies")
        
        # Process the _id field for JSON serialization
        for company in companies:
            company["_id"] = str(company["_id"])
        
        return companies
    except Exception as e:
        error_message = f"Error retrieving companies: {str(e)}"
        logger.error(error_message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_message
        )

@router.get("/company/{company_name}", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def get_company(company_name: str, refresh: bool = False, db=Depends(get_database)):
    """
    Get financial data for a specific company.
    
    Args:
        company_name (str): Name of the company.
        refresh (bool): Whether to refresh the database connection before fetching data.
        db: MongoDB database dependency.
        
    Returns:
        Dict[str, Any]: Financial data for the company.
    """
    try:
        # Refresh the database connection if requested
        if refresh:
            logger.info(f"Refreshing database connection before fetching company {company_name}")
            db = await refresh_database_connection()
            
        companies_collection = db.detailed_financials
        logger.info(f"Retrieving financial data for {company_name}")
        company = await get_company_financials(company_name, companies_collection)
        
        if not company:
            logger.warning(f"Company {company_name} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Company {company_name} not found"
            )
        
        # Process the _id field for JSON serialization
        company["_id"] = str(company["_id"])
        
        return company
    except HTTPException:
        raise
    except Exception as e:
        error_message = f"Error retrieving company data: {str(e)}"
        logger.error(error_message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_message
        )

@router.post("/remove-quarter", status_code=status.HTTP_200_OK)
async def remove_quarter(quarter_data: dict, db=Depends(get_database)):
    """
    Remove all financial data for a specific quarter.
    
    Args:
        quarter_data (dict): Dictionary containing the quarter to remove.
        db: MongoDB database dependency.
        
    Returns:
        Dict[str, Any]: Result of the operation.
    """
    try:
        # Extract the quarter from the request body
        if "quarter" not in quarter_data:
            logger.error("Quarter parameter missing from request body")
            return {
                "success": False,
                "message": "Quarter parameter is required",
                "companies_affected": 0
            }
            
        quarter = quarter_data["quarter"]
        companies_collection = db.detailed_financials
        logger.info(f"Removing financial data for quarter: {quarter}")
        
        # Find all companies with this quarter
        companies_with_quarter = await companies_collection.find(
            {"financial_metrics.quarter": quarter}
        ).to_list(1000)
        
        if not companies_with_quarter:
            logger.warning(f"No companies found with quarter {quarter}")
            return {
                "success": False,
                "message": f"No companies found with quarter {quarter}",
                "companies_affected": 0
            }
        
        # For each company, remove the financial metrics for this quarter
        companies_updated = 0
        for company in companies_with_quarter:
            company_name = company.get("company_name", "Unknown")
            
            # Filter out the financial metrics for this quarter
            new_metrics = [
                metric for metric in company.get("financial_metrics", [])
                if metric.get("quarter") != quarter
            ]
            
            # Update the company with the new metrics
            if len(new_metrics) != len(company.get("financial_metrics", [])):
                await companies_collection.update_one(
                    {"_id": company["_id"]},
                    {"$set": {"financial_metrics": new_metrics}}
                )
                companies_updated += 1
                logger.info(f"Removed quarter {quarter} from {company_name}")
        
        logger.info(f"Removed quarter {quarter} from {companies_updated} companies")
        return {
            "success": True,
            "message": f"Removed quarter {quarter} from {companies_updated} companies",
            "documents_updated": companies_updated
        }
    
    except Exception as e:
        error_message = f"Error removing quarter: {str(e)}"
        logger.error(error_message)
        return {
            "success": False,
            "message": error_message,
            "documents_updated": 0
        }

@router.get("/verify-company", status_code=status.HTTP_200_OK)
async def verify_company_data(company_name: str, quarter: Optional[str] = None, db=Depends(get_database)):
    """
    Verify if a company's data exists in the database.
    
    Args:
        company_name (str): Name of the company to verify.
        quarter (str, optional): Specific quarter to check for.
        db: MongoDB database dependency.
        
    Returns:
        Dict[str, Any]: Information about the company's data in the database.
    """
    try:
        companies_collection = db.detailed_financials
        
        # Build the query
        query = {"company_name": company_name}
        if quarter:
            query["financial_metrics.quarter"] = quarter
            
        # Find the company
        company_data = await companies_collection.find_one(query)
        
        if not company_data:
            return {
                "exists": False,
                "message": f"Company '{company_name}' not found in the database" + (f" for quarter {quarter}" if quarter else ""),
                "data": None
            }
            
        # Extract quarters
        quarters = [metric.get("quarter") for metric in company_data.get("financial_metrics", []) if metric.get("quarter")]
        
        return {
            "exists": True,
            "message": f"Company '{company_name}' found in the database",
            "quarters": quarters,
            "data": company_data
        }
        
    except Exception as e:
        error_message = f"Error verifying company data: {str(e)}"
        logger.error(error_message)
        return {
            "exists": False,
            "message": error_message,
            "data": None
        } 