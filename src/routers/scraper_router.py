"""
API router for scraper operations.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorCollection
import logging

# Configure logging
logger = logging.getLogger(__name__)

from src.scraper import (
    scrape_moneycontrol_earnings,
    scrape_by_result_type,
    scrape_custom_url,
    get_db_collection
)
from src.scraper.db_operations import remove_quarter_from_all_companies

router = APIRouter(
    prefix="",
    tags=["scraper"],
    responses={404: {"description": "Not found"}},
)

class ScrapeRequest(BaseModel):
    """Request model for scraping financial data."""
    result_type: str = Field(default="LR", description="Type of results to scrape (LR, BP, WP, PT, NT)")
    url: Optional[str] = Field(default=None, description="Optional URL to scrape")
    refresh_connection: bool = Field(default=False, description="Whether to refresh the database connection before scraping")

class ScrapeResponse(BaseModel):
    """Response model for scraping financial data."""
    success: bool
    message: str
    companies_scraped: int
    data: Optional[List[Dict[str, Any]]] = None

class RemoveQuarterRequest(BaseModel):
    """Schema for remove quarter request parameters."""
    quarter: str = Field(..., description="Quarter to remove (Q1, Q2, Q3, Q4)")

class RemoveQuarterResponse(BaseModel):
    """Schema for remove quarter response."""
    success: bool
    message: str
    documents_updated: int = 0

async def get_financials_collection() -> AsyncIOMotorCollection:
    """
    Get the financials collection.
    
    Returns:
        AsyncIOMotorCollection: MongoDB collection for financial data.
    """
    collection = await get_db_collection()
    if collection is None:
        raise HTTPException(status_code=500, detail="Failed to connect to database")
    return collection

@router.post("/scrape", response_model=ScrapeResponse)
async def scrape_data(request: ScrapeRequest, collection: AsyncIOMotorCollection = Depends(get_financials_collection)):
    """
    Scrape financial data from MoneyControl.
    
    Args:
        request (ScrapeRequest): Scrape request parameters.
        collection (AsyncIOMotorCollection): MongoDB collection for financial data.
        
    Returns:
        ScrapeResponse: Scrape response.
    """
    try:
        if request.url:
            # Scrape custom URL
            results = await scrape_custom_url(request.url, collection)
        else:
            # Scrape by result type
            results = await scrape_by_result_type(request.result_type, collection)
        
        # If no results but no error was raised, provide a helpful message
        if not results:
            return ScrapeResponse(
                success=True,
                message="Scraping completed, but no new companies were found or all companies were already in the database.",
                companies_scraped=0
            )
        
        return ScrapeResponse(
            success=True,
            message=f"Successfully scraped {len(results)} companies",
            companies_scraped=len(results),
            data=results
        )
    except Exception as e:
        error_message = str(e)
        # Provide more user-friendly messages for common errors
        if "chrome not reachable" in error_message.lower() or "no such window" in error_message.lower():
            error_message = "Browser was closed during scraping. Please try again."
        elif "invalid session id" in error_message.lower():
            error_message = "Browser session was terminated. This usually happens when the browser is closed manually."
        elif "timeout" in error_message.lower():
            error_message = "Timeout waiting for page to load. Please check your internet connection and try again."
        elif "connection" in error_message.lower():
            error_message = "Network connection issue. Please check your internet connection and try again."
        
        logger.error(f"Scraping error: {str(e)}")
        
        return ScrapeResponse(
            success=False,
            message=f"Error scraping data: {error_message}",
            companies_scraped=0
        )

@router.post("/remove-quarter", response_model=RemoveQuarterResponse)
async def remove_quarter(request: RemoveQuarterRequest, collection: AsyncIOMotorCollection = Depends(get_financials_collection)):
    """
    Remove a specific quarter from all companies.
    
    Args:
        request (RemoveQuarterRequest): Remove quarter request parameters.
        collection (AsyncIOMotorCollection): MongoDB collection for financial data.
        
    Returns:
        RemoveQuarterResponse: Remove quarter response.
    """
    try:
        logger.info(f"Attempting to remove quarter: {request.quarter}")
        
        documents_updated = await remove_quarter_from_all_companies(request.quarter, collection)
        
        if documents_updated > 0:
            logger.info(f"Successfully removed quarter {request.quarter} from {documents_updated} documents")
            return RemoveQuarterResponse(
                success=True,
                message=f"Successfully removed quarter {request.quarter} from {documents_updated} documents",
                documents_updated=documents_updated
            )
        else:
            logger.warning(f"No documents were updated when removing quarter {request.quarter}")
            return RemoveQuarterResponse(
                success=True,
                message=f"No documents were found with quarter {request.quarter}",
                documents_updated=0
            )
    except Exception as e:
        logger.error(f"Error removing quarter {request.quarter}: {str(e)}")
        return RemoveQuarterResponse(
            success=False,
            message=f"Error removing quarter: {str(e)}",
            documents_updated=0
        ) 