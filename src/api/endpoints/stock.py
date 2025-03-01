from fastapi import APIRouter, HTTPException
from typing import List, Optional
from datetime import datetime
from src.models.schemas import StockResponse
from src.services.market_service import MarketService
import logging

router = APIRouter()
market_service = MarketService()
logger = logging.getLogger(__name__)

@router.get("/{symbol}", response_model=StockResponse)
async def get_stock_details(symbol: str):
    """Get detailed stock information"""
    try:
        return await market_service.get_stock_details(symbol)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 