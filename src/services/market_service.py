from typing import Optional, List, Dict, Any
from datetime import datetime
from src.models.schemas import MarketOverview, StockResponse, StockData
from src.utils.cache import cache_with_ttl
from src.utils.database import get_database
import logging
from bson import ObjectId

logger = logging.getLogger(__name__)

class MarketService:
    def __init__(self):
        self.db = None

    async def get_db(self):
        if self.db is None:
            self.db = await get_database()
        return self.db

    def _extract_latest_metrics(self, stock: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and process latest metrics from a stock document"""
        if stock is None or not isinstance(stock.get("financial_metrics"), list):
            return None
        
        metrics = stock["financial_metrics"]
        if not metrics:
            return None
            
        latest_metric = metrics[-1]  # Get the most recent metrics
        
        # Extract counts from strings like "Strengths (12)" and "Weaknesses (5)"
        def extract_count(text: str) -> str:
            if text is None or not isinstance(text, str) or "(" not in text:
                return "0"
            try:
                count = text.split("(")[1].split(")")[0]
                return count if count.isdigit() else "0"
            except (IndexError, ValueError):
                return "0"

        # Clean CMP value - extract just the price
        cmp_raw = latest_metric.get("cmp", "")
        cmp_value = cmp_raw.split()[0] if cmp_raw else ""

        # Clean growth value
        growth_value = latest_metric.get("net_profit_growth", "0%")
        if growth_value == "--" or not growth_value:
            growth_value = "0%"
        elif "%" not in growth_value:
            growth_value = f"{growth_value}%"

        # Clean and extract all metrics with proper null handling
        strengths = extract_count(latest_metric.get("strengths", None))
        weaknesses = extract_count(latest_metric.get("weaknesses", None))
        piotroski_score = str(latest_metric.get("piotroski_score", "0"))
        fundamental_insights = latest_metric.get("fundamental_insights", "")
        estimates = latest_metric.get("estimates", "")

        # Check if strengths/weaknesses are actually available
        has_strengths = "strengths" in latest_metric and latest_metric["strengths"] is not None
        has_weaknesses = "weaknesses" in latest_metric and latest_metric["weaknesses"] is not None

        return {
            "company_name": stock.get("company_name", "Unknown"),
            "symbol": stock.get("symbol", ""),
            "cmp": cmp_value,
            "net_profit_growth": growth_value,
            "strengths": strengths if has_strengths else "NA",
            "weaknesses": weaknesses if has_weaknesses else "NA",
            "piotroski_score": piotroski_score,
            "estimates": estimates if estimates else "--",
            "result_date": latest_metric.get("result_date", ""),
            "recommendation": fundamental_insights if fundamental_insights else "--"
        }

    async def get_stock_details(self, symbol: str) -> StockResponse:
        """Get detailed stock information including financials"""
        try:
            db = await self.get_db()
            stock = await db.detailed_financials.find_one({"symbol": symbol})
            
            if not stock:
                raise Exception(f"Stock with symbol {symbol} not found")
                
            # Convert to StockData model
            stock_data = StockData(
                company_name=stock["company_name"],
                symbol=stock["symbol"],
                financial_metrics=stock["financial_metrics"],
                timestamp=stock.get("timestamp", datetime.now())
            )
            
            # Extract formatted metrics
            formatted_metrics = self._extract_latest_metrics(stock)
            
            return StockResponse(
                stock=stock_data,
                formatted_metrics=formatted_metrics or {}
            )
            
        except Exception as e:
            logger.error(f"Error fetching stock details for {symbol}: {str(e)}")
            raise Exception(f"Failed to fetch stock details: {str(e)}")

    @cache_with_ttl(ttl_seconds=3600)  # Cache for 1 hour
    async def get_market_data(self, quarter: Optional[str] = None, force_refresh: bool = False) -> MarketOverview:
        """Get market overview data with optional quarter filter"""
        try:
            db = await self.get_db()
            
            # Base query
            query = {}
            if quarter:
                query["financial_metrics.quarter"] = quarter

            # Get all stocks
            cursor = db.detailed_financials.find(query)
            stocks = []
            async for stock in cursor:
                processed_stock = self._extract_latest_metrics(stock)
                if processed_stock:
                    stocks.append(processed_stock)

            if not stocks:
                return MarketOverview(
                    top_performers=[],
                    worst_performers=[],
                    latest_results=[],
                    all_stocks=[]
                )

            # Sort by net profit growth for top/worst performers
            def parse_growth(growth_str: str) -> float:
                try:
                    return float(growth_str.strip('%').replace(',', ''))
                except (ValueError, AttributeError):
                    return 0.0

            sorted_stocks = sorted(
                stocks,
                key=lambda x: parse_growth(x['net_profit_growth']),
                reverse=True
            )

            # Sort by result date for latest results
            def parse_date(date_str: str) -> datetime:
                try:
                    return datetime.strptime(date_str, '%B %d, %Y')
                except (ValueError, TypeError):
                    return datetime.min

            latest_results = sorted(
                stocks,
                key=lambda x: parse_date(x['result_date']),
                reverse=True
            )

            return MarketOverview(
                top_performers=sorted_stocks[:10],
                worst_performers=sorted_stocks[-10:],
                latest_results=latest_results[:10],
                all_stocks=stocks
            )

        except Exception as e:
            logger.error(f"Error fetching market data: {str(e)}")
            raise Exception(f"Failed to fetch market data: {str(e)}")

    @cache_with_ttl(ttl_seconds=3600)  # Cache for 1 hour
    async def get_available_quarters(self) -> List[str]:
        """Get list of available quarters from the database"""
        try:
            db = await self.get_db()
            # Aggregate to get unique quarters from the detailed_financials collection
            pipeline = [
                {"$unwind": "$financial_metrics"},
                {"$group": {"_id": "$financial_metrics.quarter"}},
                {"$match": {"_id": {"$ne": None}}},
                {"$sort": {"_id": -1}}  # Sort in descending order (most recent first)
            ]
            
            cursor = db.detailed_financials.aggregate(pipeline)
            quarters = []
            async for doc in cursor:
                if doc["_id"]:  # Ensure we don't include null/empty quarters
                    quarters.append(doc["_id"])
            
            return quarters
        except Exception as e:
            logger.error(f"Error fetching available quarters: {str(e)}")
            raise Exception("Failed to fetch available quarters")