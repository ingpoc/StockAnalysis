from typing import Dict, List, Optional, Any, Tuple
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
            
            # Generate recommendation based on available data (which might include old or no AI analysis)
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
    
    def _parse_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and clean raw metrics from stock details."""
        price_str = metrics.get("cmp", "0")
        current_price = float(price_str.replace("₹", "").replace("$", "").replace(",", "").strip() or 0)
        
        strengths_str = metrics.get("strengths", "0")
        weaknesses_str = metrics.get("weaknesses", "0")
        piotroski_score = metrics.get("piotroski_score", "0")
        growth_str = metrics.get("net_profit_growth", "0%")
        
        try:
            strengths = int(strengths_str) if strengths_str.isdigit() else 0
            weaknesses = int(weaknesses_str) if weaknesses_str.isdigit() else 0
            piotroski = int(piotroski_score) if piotroski_score.isdigit() else 0
            growth = float(growth_str.strip("%").replace(",", "")) if growth_str and growth_str != "--" else 0
        except (ValueError, TypeError):
            logger.warning("Error parsing metrics, using defaults.")
            strengths, weaknesses, piotroski, growth = 0, 0, 5, 0 # Default to neutral values on error
            
        return {
            "current_price": current_price,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "piotroski": piotroski,
            "growth": growth,
            "growth_str": growth_str # Keep original string for reasons
        }

    def _evaluate_ai_analysis(self, ai_analysis: Optional[Any], current_action: str, current_confidence: int, reasons: List[str]) -> Tuple[str, int, float]:
        """Evaluate AI analysis results and update recommendation."""
        sentiment_score = 0.5 # Neutral default
        action = current_action
        confidence = current_confidence

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
        
        # Also add sentiment factor based on score
        if sentiment_score > 0.7:
            if action != "SELL": # Don't override strong sell signals based solely on sentiment
                action = "BUY"
            confidence += 10
            reasons.append("Very positive sentiment from analysis")
        elif sentiment_score < 0.3:
            if action != "BUY": # Don't override strong buy signals based solely on sentiment
                action = "SELL"
            confidence += 10
            reasons.append("Very negative sentiment from analysis")
            
        return action, confidence, sentiment_score
        
    def _evaluate_piotroski(self, piotroski: int, current_action: str, current_confidence: int, reasons: List[str]) -> Tuple[str, int]:
        """Evaluate Piotroski score and update recommendation."""
        action = current_action
        confidence = current_confidence
        if piotroski >= 7:
            action = "BUY" # Strong signal, overrides previous
            confidence += 15
            reasons.append(f"Strong Piotroski score: {piotroski}/9")
        elif piotroski <= 3:
            action = "SELL" # Strong signal, overrides previous
            confidence += 15
            reasons.append(f"Weak Piotroski score: {piotroski}/9")
        else:
            reasons.append(f"Average Piotroski score: {piotroski}/9")
        return action, confidence

    def _evaluate_fundamentals(self, strengths: int, weaknesses: int, current_action: str, current_confidence: int, reasons: List[str]) -> Tuple[str, int]:
        """Evaluate strengths vs weaknesses and update recommendation."""
        action = current_action
        confidence = current_confidence
        strength_ratio = strengths / (weaknesses + 1) # Avoid division by zero
        if strength_ratio > 3:
            if action != "SELL": # Don't override a strong SELL signal
                action = "BUY"
            confidence += 10
            reasons.append(f"Strong fundamentals: {strengths} strengths vs {weaknesses} weaknesses")
        elif strength_ratio < 0.5:
            if action != "BUY": # Don't override a strong BUY signal
                action = "SELL"
            confidence += 10
            reasons.append(f"Weak fundamentals: {strengths} strengths vs {weaknesses} weaknesses")
        else:
            reasons.append(f"Balanced fundamentals: {strengths} strengths vs {weaknesses} weaknesses")
        return action, confidence
        
    def _evaluate_growth(self, growth: float, growth_str: str, current_action: str, current_confidence: int, reasons: List[str]) -> Tuple[str, int]:
        """Evaluate growth factor and update recommendation."""
        action = current_action
        confidence = current_confidence
        if growth > 25:
            if action != "SELL": # Don't override a strong SELL signal
                action = "BUY"
            confidence += 10
            reasons.append(f"Strong growth: {growth_str}")
        elif growth < 0:
            if action != "BUY": # Don't override a strong BUY signal
                action = "SELL"
            confidence += 10
            reasons.append(f"Negative growth: {growth_str}")
        else:
            reasons.append(f"Moderate growth: {growth_str}")
        return action, confidence

    def _determine_timeframe(self, piotroski: int, growth: float) -> str:
        """Determine recommendation timeframe based on metrics."""
        if piotroski >= 7 and growth > 20:
            return "long"
        elif piotroski <= 3 or growth < 0:
            return "short"
        else:
            return "medium"
            
    def _calculate_prices(self, action: str, current_price: float, growth: float) -> Tuple[Optional[float], Optional[float]]:
        """Calculate target price and stop loss based on action and metrics."""
        target_price = None
        stop_loss = None
        if action == "BUY" and current_price > 0:
            growth_factor = max(1.0, 1.0 + (growth / 100))
            target_price = round(current_price * growth_factor * 1.1, 2) # Add 10% buffer
        elif action == "SELL" and current_price > 0:
            stop_loss = round(current_price * 0.95, 2) # 5% below current as stop loss
        return target_price, stop_loss

    async def _generate_recommendation(self, stock_details: StockResponse, 
                                      ai_analysis: Optional[Any] = None) -> Dict[str, Any]:
        """Core logic to generate a recommendation based on stock details and AI analysis."""
        action = "HOLD"
        confidence = 30 # Start with lower base confidence
        reasons = []
        
        try:
            raw_metrics = stock_details.formatted_metrics if hasattr(stock_details, 'formatted_metrics') else {}
            if not raw_metrics:
                raise ValueError("No formatted metrics found in stock details")
                
            parsed_metrics = self._parse_metrics(raw_metrics)

            # 1. Evaluate AI Analysis & Sentiment First (if available)
            action, confidence, _ = self._evaluate_ai_analysis(ai_analysis, action, confidence, reasons)

            # 2. Evaluate Piotroski Score (can override AI action)
            action, confidence = self._evaluate_piotroski(parsed_metrics["piotroski"], action, confidence, reasons)

            # 3. Evaluate Fundamentals (strengths/weaknesses)
            action, confidence = self._evaluate_fundamentals(parsed_metrics["strengths"], parsed_metrics["weaknesses"], action, confidence, reasons)

            # 4. Evaluate Growth
            action, confidence = self._evaluate_growth(parsed_metrics["growth"], parsed_metrics["growth_str"], action, confidence, reasons)
            
            # Final Adjustments
            confidence = min(confidence, 100) # Cap confidence
            timeframe = self._determine_timeframe(parsed_metrics["piotroski"], parsed_metrics["growth"])
            target_price, stop_loss = self._calculate_prices(action, parsed_metrics["current_price"], parsed_metrics["growth"])
                
            return {
                "action": action,
                "confidence": confidence,
                "reasons": reasons,
                "target_price": target_price,
                "stop_loss": stop_loss,
                "timeframe": timeframe
            }
                
        except Exception as e:
            logger.error(f"Error in recommendation generation logic: {str(e)}")
            # Return a safe default on error
            return {
                "action": "HOLD",
                "confidence": 0,
                "reasons": [f"Error in recommendation logic: {str(e)}", "Using cautious HOLD recommendation"],
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
