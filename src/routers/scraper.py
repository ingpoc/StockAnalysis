"""
Router for scraper functionality.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Dict, Any

from src.schemas.financial_data import (
    ScrapeRequest, 
    ScrapeResponse, 
    CompanyFinancials, 
    RemoveQuarterRequest, 
    RemoveQuarterResponse
)
from src.utils.database import get_database
from src.scraper.moneycontrol_scraper import scrape_moneycontrol_earnings, get_company_financials
from src.utils.logger import logger

router = APIRouter(
    prefix="/scraper",
    tags=["scraper"],
    responses={404: {"description": "Not found"}},
)

@router.post("/scrape", response_model=ScrapeResponse)
async def scrape_moneycontrol(
    request: ScrapeRequest,
    db: AsyncIOMotorDatabase = Depends(get_database)
) -> ScrapeResponse:
    """
    Scrape financial data from MoneyControl earnings page.
    
    Args:
        request (ScrapeRequest): Request containing result type to scrape.
        db (AsyncIOMotorDatabase): MongoDB database dependency.
        
    Returns:
        ScrapeResponse: Response with scraped data status.
    """
    try:
        # Get the company financials collection
        collection = db.detailed_financials
        
        # Map result types to names and URLs
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
        
        # Get the URL and name based on result type
        result_type = request.result_type
        if result_type in result_type_mapping:
            result_type_name = result_type_mapping[result_type]["name"]
            url = request.url or result_type_mapping[result_type]["url"]
        else:
            result_type_name = "Custom URL"
            url = request.url
            if not url:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="URL is required for custom result types"
                )
            
        logger.info(f"Scraping request received for {result_type_name} ({result_type})")
        
        # Perform the scraping
        results = await scrape_moneycontrol_earnings(url, collection)
        
        if not results:
            return ScrapeResponse(
                success=True,
                message=f"Scraping completed for {result_type_name}, but no new data was found or updated.",
                companies_scraped=0
            )
            
        return ScrapeResponse(
            success=True,
            message=f"Successfully scraped {len(results)} companies' financial data from {result_type_name}.",
            companies_scraped=len(results),
            data=results
        )
        
    except Exception as e:
        logger.error(f"An error occurred during scraping: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during scraping: {str(e)}"
        )

@router.get("/companies", response_model=List[CompanyFinancials])
async def get_all_companies(
    db: AsyncIOMotorDatabase = Depends(get_database)
) -> List[CompanyFinancials]:
    """
    Get all companies and their financial data from the database.
    
    Args:
        db (AsyncIOMotorDatabase): MongoDB database dependency.
        
    Returns:
        List[CompanyFinancials]: List of company financial data.
    """
    try:
        collection = db.detailed_financials
        companies = await collection.find().to_list(length=None)
        return companies
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while retrieving companies: {str(e)}"
        )

@router.get("/company/{company_name}", response_model=CompanyFinancials)
async def get_company(
    company_name: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
) -> CompanyFinancials:
    """
    Get financial data for a specific company.
    
    Args:
        company_name (str): Name of the company.
        db (AsyncIOMotorDatabase): MongoDB database dependency.
        
    Returns:
        CompanyFinancials: Financial data for the company.
    """
    collection = db.detailed_financials
    company = await get_company_financials(company_name, collection)
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company '{company_name}' not found"
        )
        
    return company

@router.post("/remove-quarter", response_model=RemoveQuarterResponse)
async def remove_quarter_data(
    request: RemoveQuarterRequest,
    db: AsyncIOMotorDatabase = Depends(get_database)
) -> RemoveQuarterResponse:
    """
    Remove all financial data for a specific quarter from the database.
    
    Args:
        request (RemoveQuarterRequest): Request containing the quarter to remove.
        db (AsyncIOMotorDatabase): MongoDB database dependency.
        
    Returns:
        RemoveQuarterResponse: Response with removal status.
    """
    try:
        # Get the company financials collection
        collection = db.detailed_financials
        
        # Log the request details
        logger.info(f"Removing {request.quarter} data from all companies")
        
        # Find all documents with the specified quarter
        documents_with_quarter = await collection.count_documents(
            {"financial_metrics.quarter": request.quarter}
        )
        
        if documents_with_quarter == 0:
            return RemoveQuarterResponse(
                success=True,
                message=f"No {request.quarter} data found in the database.",
                documents_updated=0
            )
        
        # Update all documents to remove the specified quarter from financial_metrics
        result = await collection.update_many(
            {"financial_metrics.quarter": request.quarter},
            {"$pull": {"financial_metrics": {"quarter": request.quarter}}}
        )
        
        # Log the result
        logger.info(f"Removed {request.quarter} data from {result.modified_count} companies")
        
        return RemoveQuarterResponse(
            success=True,
            message=f"Successfully removed {request.quarter} data from {result.modified_count} companies.",
            documents_updated=result.modified_count
        )
        
    except Exception as e:
        logger.error(f"An error occurred while removing {request.quarter} data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while removing {request.quarter} data: {str(e)}"
        ) 