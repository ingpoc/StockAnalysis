from fastapi import APIRouter, HTTPException
from typing import List, Optional
from datetime import datetime
from src.models.schemas import MarketOverview
from src.services.market_service import MarketService
import logging

router = APIRouter()
market_service = MarketService()
logger = logging.getLogger(__name__)

@router.get("/market-data", response_model=MarketOverview)
async def get_market_data(quarter: Optional[str] = None, force_refresh: bool = False):
    """Get market overview data with optional force refresh"""
    try:
        return await market_service.get_market_data(quarter, force_refresh)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/quarters")
async def get_quarters(force_refresh: bool = False):
    """Get list of available quarters"""
    try:
        quarters = await market_service.get_available_quarters(force_refresh=force_refresh)
        return {"quarters": quarters}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 