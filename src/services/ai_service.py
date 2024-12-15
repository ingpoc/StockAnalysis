from typing import List, Optional
from datetime import datetime
from bson import ObjectId
from src.models.schemas import AIAnalysis, AIAnalysisResponse
from src.utils.ai_utils import generate_analysis, analyze_sentiment
from src.utils.database import get_database
import logging

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        self.db = None

    async def get_db(self):
        if self.db is None:  # Changed from 'if not self.db'
            self.db = await get_database()
        return self.db

    async def get_analysis_history(self, symbol: str) -> List[AIAnalysis]:
        try:
            db = await self.get_db()
            cursor = db.ai_analysis.find({"symbol": symbol}).sort("timestamp", -1)
            analyses = await cursor.to_list(length=None)
            if analyses is None:  # Added null check
                analyses = []
            logger.info(f"Fetched {len(analyses)} analyses for symbol: {symbol}")
            return [AIAnalysis(**analysis) for analysis in analyses]
        except Exception as e:
            logger.error(f"Error fetching analysis history: {str(e)}")
            raise Exception(f"Error fetching analysis history: {str(e)}")

    async def get_analysis_by_id(self, analysis_id: str) -> Optional[AIAnalysis]:
        try:
            db = await self.get_db()
            analysis = await db.ai_analysis.find_one({"_id": ObjectId(analysis_id)})
            if analysis is None:  # Changed from 'if not analysis'
                return None
            logger.info(f"Fetched analysis with ID: {analysis_id}")
            return AIAnalysis(**analysis)
        except Exception as e:
            logger.error(f"Error fetching analysis: {str(e)}")
            raise Exception(f"Error fetching analysis: {str(e)}")

    async def analyze_stock(self, symbol: str) -> AIAnalysisResponse:
        try:
            db = await self.get_db()
            
            # Get stock data from main collection
            stock_data = await db.detailed_financials.find_one({"symbol": symbol})
            if stock_data is None:  # Changed from 'if not stock_data'
                raise Exception(f"Stock with symbol {symbol} not found")

            # Generate analysis using AI
            analysis_text = await generate_analysis(stock_data)
            sentiment = await analyze_sentiment(analysis_text)

            # Create analysis document
            analysis = {
                "company_name": stock_data.get("company_name", ""),
                "symbol": symbol,
                "analysis": analysis_text,
                "sentiment": sentiment,
                "recommendation": self._get_recommendation(sentiment["score"]),
                "timestamp": datetime.now()
            }

            # Insert into database
            result = await db.ai_analysis.insert_one(analysis)
            if result is None:  # Added null check
                raise Exception("Failed to insert analysis")
                
            logger.info(f"Generated new analysis for symbol: {symbol}")

            return AIAnalysisResponse(
                id=str(result.inserted_id),
                content=analysis_text,
                timestamp=analysis["timestamp"],
                recommendation=analysis["recommendation"]
            )

        except Exception as e:
            logger.error(f"Error generating analysis: {str(e)}")
            raise Exception(f"Error generating analysis: {str(e)}")

    def _get_recommendation(self, sentiment_score: float) -> str:
        """Convert sentiment score to recommendation"""
        if sentiment_score >= 0.6:
            return "Buy"
        elif sentiment_score <= 0.4:
            return "Sell"
        else:
            return "Hold"