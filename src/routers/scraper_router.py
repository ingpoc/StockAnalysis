"""
API router for scraper operations.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorCollection

from src.scraper import (
    scrape_moneycontrol_earnings,
    scrape_by_result_type,
    scrape_custom_url,
    get_db_collection
)

router = APIRouter(
    prefix="/scraper",
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
        
        return ScrapeResponse(
            success=True,
            message=f"Successfully scraped {len(results)} companies",
            companies_scraped=len(results),
            data=results
        )
    except Exception as e:
        return ScrapeResponse(
            success=False,
            message=f"Error scraping data: {str(e)}",
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
        from src.scraper import remove_quarter_from_all_companies
        
        documents_updated = await remove_quarter_from_all_companies(request.quarter, collection)
        
        return RemoveQuarterResponse(
            success=True,
            message=f"Successfully removed quarter {request.quarter} from {documents_updated} documents",
            documents_updated=documents_updated
        )
    except Exception as e:
        return RemoveQuarterResponse(
            success=False,
            message=f"Error removing quarter: {str(e)}",
            documents_updated=0
        ) 