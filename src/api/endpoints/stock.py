from fastapi import APIRouter, HTTPException, Body
from typing import List, Optional, Dict
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

@router.post("/batch", response_model=Dict[str, StockResponse])
async def get_batch_stock_details(symbols: List[str] = Body(...)):
    """Get detailed stock information for multiple symbols in a single call"""
    try:
        result = {}
        # Process each symbol and collect results
        for symbol in symbols:
            try:
                stock_data = await market_service.get_stock_details(symbol)
                result[symbol] = stock_data
            except Exception as e:
                # Store error information in the result
                logger.warning(f"Error fetching stock details for {symbol}: {str(e)}")
                result[symbol] = {"error": str(e)}
        
        return result
    except Exception as e:
        logger.error(f"Error in batch stock details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 