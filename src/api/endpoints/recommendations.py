from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Any, Optional
import logging
from src.services.recommendation.stock_recommendation_service import StockRecommendationService
from src.services.portfolio_service import PortfolioService
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)

def get_recommendation_service():
    return StockRecommendationService()

def get_portfolio_service():
    return PortfolioService()

@router.get("/stock/{symbol}")
async def get_stock_recommendation(
    symbol: str,
    recommendation_service: StockRecommendationService = Depends(get_recommendation_service)
):
    """
    Get a buy/hold/sell recommendation for a specific stock.
    
    Returns detailed recommendation with:
    - Action (BUY/SELL/HOLD)
    - Confidence level
    - Reasoning
    - Target price (if applicable)
    - Stop loss (if applicable)
    - Timeframe
    """
    try:
        recommendation = await recommendation_service.get_recommendation_for_stock(symbol)
        return recommendation
    except Exception as e:
        logger.error(f"Error getting recommendation for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/portfolio")
async def get_portfolio_recommendations(
    recommendation_service: StockRecommendationService = Depends(get_recommendation_service),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """
    Get recommendations for all stocks in the user's portfolio.
    
    Returns:
    - Individual stock recommendations
    - Portfolio-level summary and suggestions
    """
    try:
        # Get enriched holdings with current prices
        holdings = await portfolio_service.get_batch_enriched_holdings()
        
        if not holdings:
            return {
                "recommendations": {},
                "summary": {
                    "message": "No holdings found in portfolio",
                    "recommendation_counts": {"buy": 0, "sell": 0, "hold": 0, "total": 0}
                }
            }
            
        # Generate recommendations
        recommendations = await recommendation_service.get_portfolio_recommendations(holdings)
        
        return recommendations
    except Exception as e:
        logger.error(f"Error getting portfolio recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
