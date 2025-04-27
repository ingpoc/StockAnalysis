from fastapi import APIRouter, HTTPException
from typing import List, Optional
from datetime import datetime
from src.models.schemas import MarketOverview
from src.services.market_service import MarketService
from src.utils.cache import get_from_cache, set_to_cache, CACHE_EXPIRY_MEDIUM, CACHE_EXPIRY_LONG, get_cache_key
import logging

router = APIRouter()
market_service = MarketService()
logger = logging.getLogger(__name__)

@router.get("/market-data", response_model=MarketOverview)
async def get_market_data(quarter: Optional[str] = None, force_refresh: bool = False):
    """Get market overview data with optional force refresh"""
    cache_key = get_cache_key("market_data", quarter or "latest")
    if not force_refresh:
        cached_data = get_from_cache(cache_key)
        if cached_data:
            return cached_data
    try:
        data = await market_service.get_market_data(quarter, force_refresh)
        set_to_cache(cache_key, data.dict(), CACHE_EXPIRY_MEDIUM)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/quarters")
async def get_quarters(force_refresh: bool = False):
    """Get list of available quarters"""
    cache_key = get_cache_key("quarters", "all")
    if not force_refresh:
        cached_data = get_from_cache(cache_key)
        if cached_data:
            return cached_data
    try:
        quarters = await market_service.get_available_quarters(force_refresh=force_refresh)
        response = {"quarters": quarters}
        set_to_cache(cache_key, response, CACHE_EXPIRY_LONG)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 