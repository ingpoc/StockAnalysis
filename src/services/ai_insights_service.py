from typing import Dict, List
import os
import httpx
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

class AIInsightsService:
    def __init__(self):
        self.api_key = os.getenv("XAI_API_KEY")
        self.base_url = "https://api.xai.com/v1"  # Replace with actual XAI API base URL
        
    async def get_stock_insights(self, symbol: str, timeframe: str = "1d") -> Dict:
        """Get AI-powered insights for a given stock symbol."""
        try:
            if not self.api_key:
                logger.error("XAI API key not configured")
                raise HTTPException(
                    status_code=500,
                    detail="AI service not properly configured"
                )
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/stock/insights",
                    headers=headers,
                    json={
                        "symbol": symbol,
                        "timeframe": timeframe
                    }
                )
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during API call: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error communicating with AI service: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Internal server error during analysis"
            )
            
    async def get_market_sentiment(self) -> Dict:
        """Get overall market sentiment analysis."""
        if not self.api_key:
            raise HTTPException(status_code=500, detail="XAI API key not configured")
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/market/sentiment",
                    headers=headers
                )
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPError as e:
            raise HTTPException(status_code=500, detail=f"Error fetching market sentiment: {str(e)}") 