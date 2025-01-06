from fastapi import APIRouter, Depends
from typing import Dict
from src.services.ai_insights_service import AIInsightsService

router = APIRouter()

@router.get("/stock/{symbol}")
async def get_stock_insights(
    symbol: str,
    timeframe: str = "1d",
    ai_service: AIInsightsService = Depends(AIInsightsService)
) -> Dict:
    """Get AI-powered insights for a specific stock."""
    return await ai_service.get_stock_insights(symbol, timeframe)

@router.get("/market/sentiment")
async def get_market_sentiment(
    ai_service: AIInsightsService = Depends(AIInsightsService)
) -> Dict:
    """Get overall market sentiment analysis."""
    return await ai_service.get_market_sentiment() 