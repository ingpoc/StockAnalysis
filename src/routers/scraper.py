"""
Router for scraper functionality.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Dict, Any

from src.schemas.financial_data import ScrapeRequest, ScrapeResponse, CompanyFinancials
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
        request (ScrapeRequest): Request containing URL to scrape and optional result type.
        db (AsyncIOMotorDatabase): MongoDB database dependency.
        
    Returns:
        ScrapeResponse: Response with scraped data status.
    """
    try:
        # Get the company financials collection
        collection = db.detailed_financials
        
        # Log the request details
        result_type = "custom"
        if request.result_type:
            result_type = request.result_type
        elif "tab=" in request.url:
            tab_param = request.url.split("tab=")[1].split("&")[0]
            result_type = tab_param
            
        if result_type == "LR":
            result_type_name = "Latest Results"
        elif result_type == "BP":
            result_type_name = "Best Performer"
        elif result_type == "WP":
            result_type_name = "Worst Performer"
        elif result_type == "PT":
            result_type_name = "Positive Turnaround"
        elif result_type == "NT":
            result_type_name = "Negative Turnaround"
        else:
            result_type_name = "Custom URL"
            
        logger.info(f"Scraping request received for {result_type_name} ({result_type})")
        
        # Perform the scraping
        results = await scrape_moneycontrol_earnings(request.url, collection)
        
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