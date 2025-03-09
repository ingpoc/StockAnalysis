from typing import Optional, List, Dict, Any
from datetime import datetime
from src.models.schemas import MarketOverview, StockResponse, StockData
from src.utils.cache import cache_with_ttl
from src.utils.database import get_database
import logging
from bson import ObjectId
import asyncio
import time
import hashlib

logger = logging.getLogger(__name__)

class MarketService:
    def __init__(self):
        self._cache = {}
        self._db = None
        self._last_modified = {}  # Keep track of when data was last modified
        self._cache_invalidation_timestamps = {}  # Timestamps for cache invalidation

    async def get_db(self):
        if self._db is None:
            self._db = await get_database()
        return self._db

    # Helper method for resilient database operations
    async def _execute_with_retry(self, operation, max_retries=3, retry_delay=1):
        """Execute a database operation with retries on failure"""
        attempt = 0
        last_error = None
        
        while attempt < max_retries:
            try:
                # Try to get a fresh database connection on retries
                if attempt > 0:
                    logger.info(f"Retry attempt {attempt} for database operation")
                    self._db = None  # Force a new connection on next get_db call
                
                return await operation()
            except Exception as e:
                last_error = e
                logger.warning(f"Database operation failed (attempt {attempt+1}/{max_retries}): {str(e)}")
                attempt += 1
                if attempt < max_retries:
                    # Wait before retrying, with some jitter
                    await asyncio.sleep(retry_delay * (1 + (attempt * 0.1)))
        
        # If we get here, all retries failed
        logger.error(f"All {max_retries} retry attempts failed for database operation: {str(last_error)}")
        raise last_error

    def _extract_latest_metrics(self, stock: Dict[str, Any], quarter: Optional[str] = None) -> Dict[str, Any]:
        """Extract and process latest metrics from a stock document"""
        if stock is None or not isinstance(stock.get("financial_metrics"), list):
            return None
        
        metrics = stock["financial_metrics"]
        if not metrics:
            return None
            
        # If quarter is specified, find the metric for that quarter
        if quarter:
            matching_metrics = [m for m in metrics if m.get("quarter") == quarter]
            if not matching_metrics:
                return None
            latest_metric = matching_metrics[-1]  # Get the most recent matching metric
        else:
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

    async def get_batch_stock_details(self, symbols: List[str]) -> Dict[str, StockResponse]:
        """Get detailed stock information for multiple symbols in a single call"""
        try:
            result = {}
            # Process each symbol and collect results
            for symbol in symbols:
                try:
                    stock_data = await self.get_stock_details(symbol)
                    result[symbol] = stock_data
                except Exception as e:
                    # Store error information in the result
                    logger.warning(f"Error fetching stock details for {symbol}: {str(e)}")
                    result[symbol] = {"error": str(e)}
            
            return result
        except Exception as e:
            logger.error(f"Error in batch stock details: {str(e)}")
            raise Exception(f"Failed to fetch batch stock details: {str(e)}")

    def invalidate_market_data_cache(self, quarter: Optional[str] = None):
        """
        Invalidate the market data cache for a specific quarter or all quarters.
        This should be called when new data is added to the database.
        """
        timestamp = time.time()
        
        if quarter:
            # Invalidate cache for specific quarter
            key = f"market_data_{quarter}"
            self._cache_invalidation_timestamps[key] = timestamp
            if key in self._cache:
                del self._cache[key]
            logger.info(f"Invalidated cache for quarter: {quarter}")
        else:
            # Invalidate cache for all quarters
            for key in list(self._cache.keys()):
                if key.startswith("market_data_"):
                    del self._cache[key]
                    self._cache_invalidation_timestamps[key] = timestamp
            logger.info("Invalidated all market data cache")

    async def get_market_data(self, quarter: Optional[str] = None, force_refresh: bool = False) -> MarketOverview:
        """Get market overview data with optional quarter filter"""
        # Create a cache key based on quarter
        cache_key = f"market_data_{quarter if quarter else 'all'}"
        current_time = time.time()
        
        # Check if we need to refresh the cache
        cache_invalid = False
        if force_refresh:
            cache_invalid = True
            logger.info(f"Force refresh requested for {cache_key}")
        elif cache_key in self._cache_invalidation_timestamps:
            # Check if the cache was invalidated after our cached data was created
            if cache_key not in self._cache or self._cache_invalidation_timestamps[cache_key] > self._cache.get(f"{cache_key}_timestamp", 0):
                cache_invalid = True
                logger.info(f"Cache invalidated for {cache_key}")
        
        # If valid cached data exists and no forced refresh, return it
        if not cache_invalid and cache_key in self._cache:
            # Check if cache is still valid (less than 1 hour old)
            timestamp = self._cache.get(f"{cache_key}_timestamp", 0)
            if current_time - timestamp < 3600:  # 1 hour TTL
                logger.info(f"Returning cached data for {cache_key}")
                return self._cache[cache_key]
            else:
                logger.info(f"Cache expired for {cache_key}")
        
        # Cache miss or invalid - fetch from database
        async def fetch_market_data():
            db = await self.get_db()
            
            # Base query
            query = {}
            if quarter:
                query["financial_metrics.quarter"] = quarter

            # Get all stocks with a timeout to avoid long-running queries
            cursor = db.detailed_financials.find(query, max_time_ms=10000)
            stocks = []
            async for stock in cursor:
                processed_stock = self._extract_latest_metrics(stock, quarter)
                if processed_stock:
                    stocks.append(processed_stock)

            if not stocks:
                logger.warning(f"No stocks found for query: {query}")
                return MarketOverview(
                    top_performers=[],
                    worst_performers=[],
                    latest_results=[],
                    all_stocks=[]
                )

            # Sort by net profit growth for top/worst performers
            def parse_growth(growth_str: str) -> float:
                try:
                    # Handle case where growth_str is already a number
                    if isinstance(growth_str, (int, float)):
                        return float(growth_str)
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
                    # If date_str is not a string or is empty, return minimum date
                    if not isinstance(date_str, str) or not date_str:
                        return datetime.min
                    return datetime.strptime(date_str, '%B %d, %Y')
                except (ValueError, TypeError):
                    return datetime.min

            latest_results = sorted(
                stocks,
                key=lambda x: parse_date(x['result_date']),
                reverse=True
            )

            result = MarketOverview(
                top_performers=sorted_stocks[:10],
                worst_performers=sorted_stocks[-10:],
                latest_results=latest_results[:10],
                all_stocks=stocks
            )
            
            # Update cache
            self._cache[cache_key] = result
            self._cache[f"{cache_key}_timestamp"] = current_time
            logger.info(f"Updated cache for {cache_key} with {len(stocks)} stocks")
            
            return result
        
        try:
            # Execute the database operation with retry logic
            return await self._execute_with_retry(fetch_market_data)
        except Exception as e:
            logger.error(f"Error fetching market data: {str(e)}")
            # Return empty data structure instead of raising an exception
            # to ensure the UI has something to display
            return MarketOverview(
                top_performers=[],
                worst_performers=[],
                latest_results=[],
                all_stocks=[]
            )

    @cache_with_ttl(ttl_seconds=3600)  # Cache for 1 hour
    async def get_available_quarters(self, force_refresh: bool = False) -> List[str]:
        """Get list of available quarters from the database"""
        try:
            # If force_refresh is True, invalidate the cache for this function
            if force_refresh:
                # Get the cache key for this function
                cache_key = f"cache_get_available_quarters_{{}}"
                # Clear the cache for this function
                if cache_key in self._cache:
                    del self._cache[cache_key]
                logger.info("Forced refresh of available quarters cache")
            
            db = await self.get_db()
            # Aggregate to get unique quarters from the detailed_financials collection
            # and ensure there's at least one document with data for that quarter
            pipeline = [
                {"$unwind": "$financial_metrics"},
                {"$group": {"_id": "$financial_metrics.quarter", "count": {"$sum": 1}}},
                {"$match": {"_id": {"$ne": None}, "count": {"$gt": 0}}},
                {"$sort": {"_id": -1}}  # Sort in descending order (most recent first)
            ]
            
            cursor = db.detailed_financials.aggregate(pipeline)
            quarters = []
            async for doc in cursor:
                if doc["_id"]:  # Ensure we don't include null/empty quarters
                    quarters.append(doc["_id"])
            
            logger.info(f"Retrieved {len(quarters)} available quarters from database")
            return quarters
        except Exception as e:
            logger.error(f"Error fetching available quarters: {str(e)}")
            raise Exception("Failed to fetch available quarters")