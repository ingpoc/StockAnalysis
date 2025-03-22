from typing import Dict, List, Optional, Any
import logging
from datetime import datetime, timedelta
from src.models.schemas import Holding, StockResponse, EnrichedHolding
from src.utils.database import get_database
from src.services.market_service import MarketService
from src.services.ai_service import AIService
from bson import ObjectId

logger = logging.getLogger(__name__)

class StockRecommendationService:
    """Service for generating stock recommendations based on portfolio holdings and market data."""
    
    def __init__(self):
        self.market_service = MarketService()
        self.ai_service = AIService()
        
    async def get_recommendation_for_stock(self, symbol: str) -> Dict[str, Any]:
        """
        Generate a recommendation for a single stock based on technical and fundamental analysis.
        
        Args:
            symbol (str): The stock symbol to analyze
            
        Returns:
            Dict containing recommendation details:
            - action: "BUY", "SELL", or "HOLD"
            - confidence: 0-100 indicating confidence level
            - reasons: List of reasons for the recommendation
            - target_price: Estimated target price (if available)
            - stop_loss: Suggested stop loss price (if applicable)
            - timeframe: Short, medium, or long term
        """
        try:
            db = await get_database()
            
            # Get stock details from market service
            stock_details = await self.market_service.get_stock_details(symbol)
            
            # Get any existing AI analysis 
            ai_analyses = await self.ai_service.get_analysis_history(symbol)
            latest_analysis = ai_analyses[0] if ai_analyses else None
            
            # If no analysis exists or it's older than 15 days, generate a new one
            if not latest_analysis or (datetime.now() - latest_analysis.timestamp > timedelta(days=15)):
                try:
                    analysis_response = await self.ai_service.analyze_stock(symbol)
                    latest_analysis_id = analysis_response.id
                    latest_analysis = await self.ai_service.get_analysis_by_id(latest_analysis_id)
                except Exception as e:
                    logger.error(f"Error generating new analysis for {symbol}: {str(e)}")
            
            # Generate recommendation based on available data
            recommendation = await self._generate_recommendation(stock_details, latest_analysis)
            
            # Add recommendation timestamp
            recommendation["timestamp"] = datetime.now()
            recommendation["symbol"] = symbol
            
            # Store recommendation in database for future reference
            await self._store_recommendation(recommendation)
            
            return recommendation
            
        except Exception as e:
            logger.error(f"Error generating recommendation for {symbol}: {str(e)}")
            # Return a default "insufficient data" recommendation
            return {
                "symbol": symbol,
                "action": "HOLD",
                "confidence": 0,
                "reasons": [f"Error generating recommendation: {str(e)}", "Insufficient data to make a recommendation"],
                "target_price": None,
                "stop_loss": None, 
                "timeframe": "medium",
                "timestamp": datetime.now()
            }
    
    async def get_portfolio_recommendations(self, holdings: List[EnrichedHolding]) -> Dict[str, Any]:
        """
        Generate recommendations for all stocks in a portfolio.
        
        Args:
            holdings (List[EnrichedHolding]): List of portfolio holdings
            
        Returns:
            Dict containing:
            - recommendations: Dict mapping symbols to recommendations
            - summary: Portfolio-level summary and suggestions
        """
        recommendations = {}
        
        # Process each holding to get recommendations
        for holding in holdings:
            try:
                symbol = holding.symbol
                
                # Check if we have a recent recommendation in the database
                recent_recommendation = await self._get_recent_recommendation(symbol)
                
                if recent_recommendation:
                    # Use existing recommendation if recent (less than 7 days old)
                    recommendations[symbol] = recent_recommendation
                else:
                    # Generate new recommendation
                    recommendation = await self.get_recommendation_for_stock(symbol)
                    recommendations[symbol] = recommendation
                    
            except Exception as e:
                logger.error(f"Error processing recommendation for {holding.symbol}: {str(e)}")
                # Add a default recommendation for failed items
                recommendations[holding.symbol] = {
                    "symbol": holding.symbol,
                    "action": "HOLD",
                    "confidence": 0,
                    "reasons": ["Error processing recommendation", "Insufficient data"],
                    "target_price": None,
                    "stop_loss": None,
                    "timeframe": "medium",
                    "timestamp": datetime.now()
                }
        
        # Generate portfolio-level summary and suggestions
        summary = await self._generate_portfolio_summary(holdings, recommendations)
        
        return {
            "recommendations": recommendations,
            "summary": summary
        }
    
    async def _generate_recommendation(self, stock_details: StockResponse, 
                                      ai_analysis: Optional[Any] = None) -> Dict[str, Any]:
        """
        Core logic to generate a recommendation based on stock details and AI analysis.
        
        Args:
            stock_details: Stock details from market service
            ai_analysis: Optional AI analysis results
            
        Returns:
            Recommendation dictionary
        """
        # Default recommendation is HOLD when we don't have enough information
        action = "HOLD"
        confidence = 50  # Medium confidence
        reasons = []
        target_price = None
        stop_loss = None
        timeframe = "medium"  # Default to medium term
        
        try:
            # Extract metrics from stock details
            metrics = stock_details.formatted_metrics if hasattr(stock_details, 'formatted_metrics') else {}
            
            # Get price
            price_str = metrics.get("cmp", "0")
            current_price = float(price_str.replace("₹", "").replace("$", "").replace(",", "").strip() or 0)
            
            # Extract metrics we'll use for recommendations
            strengths_str = metrics.get("strengths", "0")
            weaknesses_str = metrics.get("weaknesses", "0")
            piotroski_score = metrics.get("piotroski_score", "0")
            growth_str = metrics.get("net_profit_growth", "0%")
            
            # Clean and parse metrics
            try:
                strengths = int(strengths_str) if strengths_str.isdigit() else 0
                weaknesses = int(weaknesses_str) if weaknesses_str.isdigit() else 0
                piotroski = int(piotroski_score) if piotroski_score.isdigit() else 0
                growth = float(growth_str.strip("%").replace(",", "")) if growth_str and growth_str != "--" else 0
            except (ValueError, TypeError):
                strengths, weaknesses, piotroski, growth = 0, 0, 5, 0
                
            # Use AI analysis if available
            sentiment_score = 0.5  # Neutral default
            if ai_analysis:
                if hasattr(ai_analysis, 'sentiment') and ai_analysis.sentiment:
                    sentiment_score = ai_analysis.sentiment.get("score", 0.5)
                recommendation_text = getattr(ai_analysis, 'recommendation', None)
                if recommendation_text:
                    if "buy" in recommendation_text.lower():
                        action = "BUY"
                        confidence += 10
                        reasons.append(f"AI Analysis Recommendation: {recommendation_text}")
                    elif "sell" in recommendation_text.lower():
                        action = "SELL" 
                        confidence += 10
                        reasons.append(f"AI Analysis Recommendation: {recommendation_text}")
                        
            # Generate recommendation based on fundamentals
            
            # Piotroski score factor (0-9 scale)
            if piotroski >= 7:
                action = "BUY"
                confidence += 15
                reasons.append(f"Strong Piotroski score: {piotroski}/9")
            elif piotroski <= 3:
                action = "SELL"
                confidence += 15
                reasons.append(f"Weak Piotroski score: {piotroski}/9")
            else:
                reasons.append(f"Average Piotroski score: {piotroski}/9")
                
            # Strengths vs Weaknesses
            strength_ratio = strengths / (weaknesses + 1)  # Avoid division by zero
            if strength_ratio > 3:
                if action != "SELL":  # Don't override a SELL from Piotroski
                    action = "BUY"
                confidence += 10
                reasons.append(f"Strong fundamentals: {strengths} strengths vs {weaknesses} weaknesses")
            elif strength_ratio < 0.5:
                if action != "BUY":  # Don't override a BUY from Piotroski
                    action = "SELL"
                confidence += 10
                reasons.append(f"Weak fundamentals: {strengths} strengths vs {weaknesses} weaknesses")
            else:
                reasons.append(f"Balanced fundamentals: {strengths} strengths vs {weaknesses} weaknesses")
                
            # Growth factor
            if growth > 25:
                if action != "SELL":  # Don't override a SELL
                    action = "BUY"
                confidence += 10
                reasons.append(f"Strong growth: {growth_str}")
            elif growth < 0:
                if action != "BUY":  # Don't override a BUY
                    action = "SELL"
                confidence += 10
                reasons.append(f"Negative growth: {growth_str}")
            else:
                reasons.append(f"Moderate growth: {growth_str}")
                
            # Sentiment factor
            if sentiment_score > 0.7:
                if action != "SELL":
                    action = "BUY"
                confidence += 10
                reasons.append("Very positive sentiment from analysis")
            elif sentiment_score < 0.3:
                if action != "BUY":
                    action = "SELL"
                confidence += 10
                reasons.append("Very negative sentiment from analysis")
            
            # Cap confidence at 100
            confidence = min(confidence, 100)
            
            # Set timeframe based on metrics
            if piotroski >= 7 and growth > 20:
                timeframe = "long"
            elif piotroski <= 3 or growth < 0:
                timeframe = "short"
                
            # Calculate target price (very simplified)
            if action == "BUY" and current_price > 0:
                # Simple target based on growth rate and confidence
                growth_factor = max(1.0, 1.0 + (growth / 100))
                target_price = round(current_price * growth_factor, 2)
            elif action == "SELL" and current_price > 0:
                # No target for sell, but set stop loss
                stop_loss = round(current_price * 0.9, 2)  # 10% below current as stop loss
                
            return {
                "action": action,
                "confidence": confidence,
                "reasons": reasons,
                "target_price": target_price,
                "stop_loss": stop_loss,
                "timeframe": timeframe
            }
                
        except Exception as e:
            logger.error(f"Error in recommendation generation: {str(e)}")
            return {
                "action": "HOLD",
                "confidence": 30,
                "reasons": ["Error in recommendation logic", "Using cautious HOLD recommendation"],
                "target_price": None,
                "stop_loss": None,
                "timeframe": "medium"
            }
    
    async def _store_recommendation(self, recommendation: Dict[str, Any]) -> None:
        """Store the recommendation in the database for future reference."""
        try:
            db = await get_database()
            collection = db["stock_recommendations"]
            
            # Insert recommendation
            await collection.insert_one(recommendation)
            
        except Exception as e:
            logger.error(f"Error storing recommendation: {str(e)}")
    
    async def _get_recent_recommendation(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get a recent recommendation for a stock if available (less than 7 days old)."""
        try:
            db = await get_database()
            collection = db["stock_recommendations"]
            
            # Find recommendations for this symbol less than 7 days old
            cutoff_date = datetime.now() - timedelta(days=7)
            
            recommendation = await collection.find_one({
                "symbol": symbol,
                "timestamp": {"$gte": cutoff_date}
            }, sort=[("timestamp", -1)])
            
            if recommendation:
                # Convert ObjectId to string for serialization
                if "_id" in recommendation:
                    recommendation["_id"] = str(recommendation["_id"])
                return recommendation
                
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving recent recommendation for {symbol}: {str(e)}")
            return None
    
    async def _generate_portfolio_summary(self, holdings: List[EnrichedHolding], 
                                         recommendations: Dict[str, Dict]) -> Dict[str, Any]:
        """Generate a summary of portfolio recommendations and suggestions."""
        try:
            # Count recommendations by type
            buy_count = sum(1 for rec in recommendations.values() if rec.get("action") == "BUY")
            sell_count = sum(1 for rec in recommendations.values() if rec.get("action") == "SELL")
            hold_count = sum(1 for rec in recommendations.values() if rec.get("action") == "HOLD")
            
            # Calculate total portfolio value
            total_value = sum(holding.current_value or (holding.average_price * holding.quantity) 
                             for holding in holdings)
            
            # Get top 3 buy recommendations by confidence
            top_buys = sorted(
                [rec for rec in recommendations.values() if rec.get("action") == "BUY"],
                key=lambda x: x.get("confidence", 0),
                reverse=True
            )[:3]
            
            # Get top 3 sell recommendations by confidence
            top_sells = sorted(
                [rec for rec in recommendations.values() if rec.get("action") == "SELL"],
                key=lambda x: x.get("confidence", 0),
                reverse=True
            )[:3]
            
            summary = {
                "recommendation_counts": {
                    "buy": buy_count,
                    "sell": sell_count,
                    "hold": hold_count,
                    "total": len(recommendations)
                },
                "top_buy_recommendations": [
                    {"symbol": rec.get("symbol"), "confidence": rec.get("confidence")} 
                    for rec in top_buys
                ],
                "top_sell_recommendations": [
                    {"symbol": rec.get("symbol"), "confidence": rec.get("confidence")} 
                    for rec in top_sells
                ],
            }
            
            # Add portfolio-level suggestions
            suggestions = []
            
            if sell_count > buy_count and sell_count > 0.3 * len(recommendations):
                suggestions.append("Consider reducing exposure as many stocks have sell recommendations")
            
            if buy_count > 0.5 * len(recommendations):
                suggestions.append("Portfolio has many promising stocks with buy recommendations")
                
            if hold_count > 0.7 * len(recommendations):
                suggestions.append("Portfolio is relatively stable with mostly hold recommendations")
                
            summary["portfolio_suggestions"] = suggestions
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating portfolio summary: {str(e)}")
            return {
                "error": f"Failed to generate portfolio summary: {str(e)}",
                "recommendation_counts": {
                    "buy": 0,
                    "sell": 0,
                    "hold": 0,
                    "total": len(recommendations)
                }
            }
