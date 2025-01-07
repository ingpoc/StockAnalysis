from typing import List, Optional
from datetime import datetime
from bson import ObjectId
from src.models.schemas import AIAnalysis, AIAnalysisResponse
from src.utils.xai_utils import analyze_with_xai
from src.utils.database import get_database
import logging
import json

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        self.db = None

    async def get_db(self):
        if self.db is None:
            self.db = await get_database()
        return self.db

    async def get_analysis_history(self, symbol: str) -> List[AIAnalysis]:
        try:
            db = await self.get_db()
            cursor = db.ai_analysis.find({"symbol": symbol}).sort("timestamp", -1)
            analyses = await cursor.to_list(length=None)
            if analyses is None:
                analyses = []
            
            logger.info(f"Fetched {len(analyses)} analyses for symbol: {symbol}")
            try:
                return [AIAnalysis.from_mongo(analysis) for analysis in analyses if analysis]
            except Exception as e:
                logger.error(f"Error converting MongoDB documents to AIAnalysis: {str(e)}")
                raise Exception(f"Error parsing analysis data: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error fetching analysis history: {str(e)}")
            raise Exception(f"Error fetching analysis history: {str(e)}")

    async def get_analysis_by_id(self, analysis_id: str) -> Optional[AIAnalysis]:
        try:
            db = await self.get_db()
            analysis_doc = await db.ai_analysis.find_one({"_id": ObjectId(analysis_id)})
            if analysis_doc is None:
                logger.info(f"No analysis found with ID: {analysis_id}")
                return None
            
            logger.info(f"Fetched analysis with ID: {analysis_id}")
            try:
                return AIAnalysis.from_mongo(analysis_doc)
            except Exception as e:
                logger.error(f"Error converting MongoDB document to AIAnalysis: {str(e)}")
                raise Exception(f"Error parsing analysis data: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error fetching analysis: {str(e)}")
            raise Exception(f"Error fetching analysis: {str(e)}")

    async def analyze_stock(self, symbol: str) -> AIAnalysisResponse:
        try:
            db = await self.get_db()
            
            # Get stock data from main collection
            stock_data = await db.detailed_financials.find_one({"symbol": symbol})
            if stock_data is None:
                logger.error(f"Stock with symbol {symbol} not found")
                raise Exception(f"Stock with symbol {symbol} not found")

            try:
                # Generate analysis using xAI
                logger.info(f"Requesting XAI analysis for symbol: {symbol}")
                xai_analysis = await analyze_with_xai(stock_data)
                logger.debug(f"Received XAI analysis response: {xai_analysis}")
            except Exception as e:
                logger.error(f"XAI analysis failed: {str(e)}")
                raise Exception(f"Failed to generate AI analysis: {str(e)}")

            # Create analysis document
            analysis = {
                "company_name": stock_data.get("company_name", ""),
                "symbol": symbol,
                "analysis": xai_analysis["analysis"],
                "sentiment": xai_analysis["sentiment"],
                "technical_indicators": xai_analysis["technical_indicators"],
                "fundamental_analysis": xai_analysis["fundamental_analysis"],
                "recommendation": self._get_recommendation(xai_analysis["sentiment"]["score"]),
                "timestamp": datetime.now()
            }

            # Insert into database
            try:
                result = await db.ai_analysis.insert_one(analysis)
                if result is None:
                    raise Exception("Failed to insert analysis into database")
                    
                logger.info(f"Generated new analysis for symbol: {symbol}")
                
                # Create response with serialized content
                response_data = {
                    "id": str(result.inserted_id),
                    "content": json.dumps(analysis["analysis"]) if isinstance(analysis["analysis"], dict) else analysis["analysis"],
                    "timestamp": analysis["timestamp"],
                    "recommendation": analysis["recommendation"]
                }
                
                return AIAnalysisResponse.model_validate(response_data)
                
            except Exception as e:
                logger.error(f"Database operation failed: {str(e)}")
                raise Exception(f"Failed to save analysis: {str(e)}")

        except Exception as e:
            logger.error(f"Error generating analysis: {str(e)}")
            raise

    def _get_recommendation(self, sentiment_score: float) -> str:
        if sentiment_score >= 0.7:
            return "Strong Buy"
        elif sentiment_score >= 0.6:
            return "Buy"
        elif sentiment_score >= 0.4:
            return "Hold"
        elif sentiment_score >= 0.3:
            return "Sell"
        else:
            return "Strong Sell"