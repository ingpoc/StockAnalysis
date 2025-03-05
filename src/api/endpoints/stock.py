from fastapi import APIRouter, HTTPException, Body, Depends, Query
from typing import List, Optional, Dict, Any
from datetime import datetime
from src.models.schemas import StockResponse
from src.services.market_service import MarketService
import logging
from src.utils.database import get_database, refresh_database_connection

router = APIRouter()
market_service = MarketService()
logger = logging.getLogger(__name__)

@router.get("/{symbol}", response_model=Dict[str, Any])
async def get_stock_data(
    symbol: str, 
    refresh: bool = False,
    db=Depends(get_database)
):
    """
    Get stock data for a specific symbol.
    
    Args:
        symbol (str): Stock symbol to retrieve data for.
        refresh (bool): Whether to refresh the database connection before fetching data.
        db: MongoDB database dependency.
        
    Returns:
        Dict[str, Any]: Stock data.
    """
    try:
        # Refresh the database connection if requested
        if refresh:
            logger.info(f"Refreshing database connection before fetching stock data for {symbol}")
            db = await refresh_database_connection()
            
        # Get the stocks collection
        stocks_collection = db.detailed_financials
        
        # Find the stock by symbol
        stock = await stocks_collection.find_one({"symbol": symbol})
        
        if not stock:
            # Try finding by company name that contains the symbol
            stock = await stocks_collection.find_one({"company_name": {"$regex": symbol, "$options": "i"}})
            
        if not stock:
            raise HTTPException(status_code=404, detail=f"Stock with symbol {symbol} not found")
        
        # Process the _id field for JSON serialization
        stock["_id"] = str(stock["_id"])
        
        # Format the response to match the expected structure
        # Use the market service to extract formatted metrics
        formatted_metrics = market_service._extract_latest_metrics(stock)
        
        # Create the response structure expected by the frontend
        response = {
            "stock": {
                "company_name": stock.get("company_name", ""),
                "symbol": stock.get("symbol", ""),
                "financial_metrics": stock.get("financial_metrics", []),
                "timestamp": stock.get("timestamp", "")
            },
            "formatted_metrics": formatted_metrics or {}
        }
        
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving stock data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving stock data: {str(e)}")

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