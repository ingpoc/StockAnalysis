"""
API router for scraper operations.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorCollection
import logging
from bson import ObjectId
import asyncio
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

# Custom JSON encoder for MongoDB ObjectId
class PyObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        return v

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

# Add after other global variables
_scraping_status: Dict[str, bool] = {}
_last_scrape_time: Dict[str, datetime] = {}

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

@router.get("/status")
async def get_scraping_status():
    """Get the current status of scraping operations."""
    return {
        "is_scraping": any(_scraping_status.values()),
        "last_scrape_time": max(_last_scrape_time.values()) if _last_scrape_time else None
    }

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
        # Create a unique key for this scraping operation
        scrape_key = f"{datetime.now().timestamp()}"
        _scraping_status[scrape_key] = True
        
        # Create a background task for scraping
        async def background_scrape():
            try:
                if request.url:
                    await scrape_custom_url(request.url, collection)
                else:
                    await scrape_by_result_type(request.result_type, collection)
            except Exception as e:
                logger.error(f"Background scraping failed: {str(e)}")
            finally:
                _scraping_status[scrape_key] = False
                _last_scrape_time[scrape_key] = datetime.now()
                
                # Cleanup old status entries
                current_time = datetime.now()
                old_keys = [k for k, t in _last_scrape_time.items() 
                          if (current_time - t).total_seconds() > 3600]  # Remove entries older than 1 hour
                for k in old_keys:
                    _scraping_status.pop(k, None)
                    _last_scrape_time.pop(k, None)

        # Start the background task
        asyncio.create_task(background_scrape())
        
        return ScrapeResponse(
            success=True,
            message="Scraping started in background",
            companies_scraped=0
        )
        
    except Exception as e:
        logger.error(f"Failed to start scraping: {str(e)}")
        return ScrapeResponse(
            success=False,
            message=f"Failed to start scraping: {str(e)}",
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