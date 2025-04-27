from typing import Optional, List, Dict, Any
from datetime import datetime
import re
from src.models.schemas import MarketOverview, StockResponse, StockData
from src.utils.cache import get_from_cache, set_to_cache, CACHE_EXPIRY_MEDIUM, CACHE_EXPIRY_LONG, get_cache_key
from src.utils.database import get_database
import logging
from bson import ObjectId

logger = logging.getLogger(__name__)

class MarketService:
    def __init__(self):
        self._cache = {}

    # Compile regex pattern once for repeated use
    _count_pattern = re.compile(r'\((\d+)\)')
    
    def _extract_latest_metrics(self, stock: Dict[str, Any], quarter: Optional[str] = None) -> Dict[str, Any]:
        """Extract and process latest metrics from a stock document (optimized)"""
        # Early returns for invalid input
        if not stock or not isinstance(stock.get("financial_metrics"), list) or not stock["financial_metrics"]:
            return None
        
        metrics = stock["financial_metrics"]
        
        # More efficient filtering approach
        if quarter:
            # Use list comprehension once instead of checking length separately
            matching_metrics = [m for m in metrics if m.get("quarter") == quarter]
            if not matching_metrics:
                return None
            latest_metric = matching_metrics[-1]
        else:
            # Direct access is faster than filtering when no quarter is specified
            latest_metric = metrics[-1]
        
        # Extract counts using compiled regex pattern - much faster for repeated use
        def extract_count(text: str) -> str:
            if not text or not isinstance(text, str):
                return "0"
            
            match = self._count_pattern.search(text)
            return match.group(1) if match else "0"
        
        # Check availability first to avoid redundant checks later
        has_strengths = "strengths" in latest_metric and latest_metric["strengths"] is not None
        has_weaknesses = "weaknesses" in latest_metric and latest_metric["weaknesses"] is not None
        
        # More efficient string processing
        cmp_raw = latest_metric.get("cmp", "")
        # Split only if needed
        cmp_value = cmp_raw.split()[0] if cmp_raw and " " in cmp_raw else cmp_raw
        
        # Simplified conditional logic for growth value
        growth_value = latest_metric.get("net_profit_growth", "0%")
        if not growth_value or growth_value == "--":
            growth_value = "0%"
        elif "%" not in growth_value:
            growth_value = f"{growth_value}%"
        
        # Pre-process values that require computation
        strengths_value = extract_count(latest_metric.get("strengths")) if has_strengths else "NA"
        weaknesses_value = extract_count(latest_metric.get("weaknesses")) if has_weaknesses else "NA"
        
        # Use direct conditional expressions for optional values
        estimates = latest_metric.get("estimates") or "--"
        recommendation = latest_metric.get("fundamental_insights") or "--"
        
        # Return dict construction is now more direct
        return {
            "company_name": stock.get("company_name", "Unknown"),
            "symbol": stock.get("symbol", ""),
            "cmp": cmp_value,
            "net_profit_growth": growth_value,
            "strengths": strengths_value,
            "weaknesses": weaknesses_value,
            "piotroski_score": str(latest_metric.get("piotroski_score", "0")),
            "estimates": estimates,
            "result_date": latest_metric.get("result_date", ""),
            "recommendation": recommendation
        }

    async def get_stock_details(self, symbol: str) -> StockResponse:
        """Get detailed stock information including financials"""
        try:
            db = await get_database()
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
        """Get detailed stock information for multiple symbols with optimized concurrent processing"""
        try:
            import asyncio
            from asyncio import TimeoutError as AsyncTimeoutError
            
            # Process symbols in parallel for better performance
            async def get_stock_with_timeout(symbol, timeout=5):
                try:
                    # Apply timeout to prevent slow queries from blocking
                    return symbol, await asyncio.wait_for(
                        self.get_stock_details(symbol),
                        timeout=timeout
                    )
                except AsyncTimeoutError:
                    logger.warning(f"Timeout fetching details for {symbol}")
                    return symbol, {"error": f"Operation timed out after {timeout} seconds"}
                except Exception as e:
                    logger.warning(f"Error fetching stock details for {symbol}: {str(e)}")
                    return symbol, {"error": str(e)}
            
            # Create concurrent tasks for all symbols - improved performance
            tasks = [get_stock_with_timeout(symbol) for symbol in symbols]
            results = await asyncio.gather(*tasks)
            
            # Convert results to dictionary with better error handling
            result_dict = {symbol: data for symbol, data in results}
            
            return result_dict
        except Exception as e:
            logger.error(f"Error in batch stock details: {str(e)}")
            raise Exception(f"Failed to fetch batch stock details: {str(e)}")

    async def get_market_data(self, quarter: Optional[str] = None, force_refresh: bool = False) -> MarketOverview:
        """Get market overview data with optional quarter filter"""
        try:
            db = await get_database()
            
            # Optimized query with projection to fetch only needed fields
            query = {}
            if quarter:
                query["financial_metrics.quarter"] = quarter
                
            # Only fetch the fields we actually need to reduce data transfer
            projection = {
                "company_name": 1,
                "symbol": 1,
                "financial_metrics": 1
            }
            
            # Use cursor with optimized batch size
            cursor = db.detailed_financials.find(query, projection).batch_size(50)
            
            # Pre-allocate array for better memory usage
            stocks = []
            async for stock in cursor:
                processed_stock = self._extract_latest_metrics(stock, quarter)
                if processed_stock:
                    stocks.append(processed_stock)

            if not stocks:
                return MarketOverview(
                    top_performers=[],
                    worst_performers=[],
                    latest_results=[],
                    all_stocks=[]
                )

            # Pre-compiled regex and cached date format for better performance
            date_format = '%B %d, %Y'
            comma_pattern = re.compile(r',')
            percent_pattern = re.compile(r'%')
            
            # Sort by net profit growth for top/worst performers - optimized
            def parse_growth(growth_str: str) -> float:
                # Fast path for numeric types
                if isinstance(growth_str, (int, float)):
                    return float(growth_str)
                
                # Fast path for empty or None values
                if not growth_str or not isinstance(growth_str, str):
                    return 0.0
                    
                try:
                    # Use regex sub instead of multiple string operations
                    cleaned = comma_pattern.sub('', growth_str)
                    cleaned = percent_pattern.sub('', cleaned)
                    return float(cleaned.strip())
                except (ValueError, AttributeError):
                    return 0.0

            # Cache for parsed dates to avoid re-parsing the same date strings
            date_cache = {}
            
            # Optimized date parsing with caching
            def parse_date(date_str: str) -> datetime:
                # Fast path for empty values
                if not isinstance(date_str, str) or not date_str:
                    return datetime.min
                    
                # Check cache first
                if date_str in date_cache:
                    return date_cache[date_str]
                    
                # Parse and cache the result
                try:
                    parsed_date = datetime.strptime(date_str, date_format)
                    date_cache[date_str] = parsed_date
                    return parsed_date
                except (ValueError, TypeError):
                    date_cache[date_str] = datetime.min
                    return datetime.min
                    
            # Optimize sorting by pre-computing keys
            growth_keys = {stock['symbol']: parse_growth(stock['net_profit_growth']) for stock in stocks}
            sorted_stocks = sorted(
                stocks,
                key=lambda x: growth_keys.get(x['symbol'], 0.0),
                reverse=True
            )

            # Pre-compute date keys for faster sorting
            date_keys = {stock['symbol']: parse_date(stock['result_date']) for stock in stocks}
            latest_results = sorted(
                stocks,
                key=lambda x: date_keys.get(x['symbol'], datetime.min),
                reverse=True
            )

            market_data = MarketOverview(
                top_performers=sorted_stocks[:10],
                worst_performers=sorted_stocks[-10:],
                latest_results=latest_results[:10],
                all_stocks=stocks
            )

            cache_key = get_cache_key("market_data", quarter or "latest")
            if not force_refresh:
                cached_data = get_from_cache(cache_key)
                if cached_data:
                    return MarketOverview(**cached_data)

            set_to_cache(cache_key, market_data.dict(), CACHE_EXPIRY_MEDIUM)
            return market_data

        except Exception as e:
            logger.error(f"Error fetching market data: {str(e)}")
            raise Exception(f"Failed to fetch market data: {str(e)}")

    async def get_available_quarters(self, force_refresh: bool = False) -> List[str]:
        """Get list of available quarters from the database (optimized)"""
        try:
            # If force_refresh is True, invalidate the cache for this function
            if force_refresh:
                # Use the clear_cache_with_prefix function to properly invalidate cache
                await clear_cache_with_prefix("get_available_quarters")
                logger.info("Forced refresh of available quarters cache")
            
            db = await get_database()
            
            # Optimized pipeline with better filtering
            pipeline = [
                # Pre-filter to only process documents with financial_metrics
                {"$match": {"financial_metrics.0": {"$exists": True}}},
                
                # Unwind the array to process each metric separately
                {"$unwind": "$financial_metrics"},
                
                # Filter out empty quarters immediately
                {"$match": {"financial_metrics.quarter": {"$nin": [None, ""]}}},
                
                # Group by quarter with more efficient counting
                {"$group": {
                    "_id": "$financial_metrics.quarter", 
                    "count": {"$sum": 1},
                    # Capture year for better sorting
                    "year": {"$first": {"$substr": ["$financial_metrics.quarter", 0, 4]}},
                    "q": {"$first": {"$substr": ["$financial_metrics.quarter", 5, 2]}}
                }},
                
                # Ensure we have data for this quarter
                {"$match": {"count": {"$gt": 0}}},
                
                # Sort by year and quarter for chronological ordering
                {"$sort": {"year": -1, "q": -1}}
            ]
            
            # More efficient cursor processing
            cursor = db.detailed_financials.aggregate(
                pipeline,
                # Add cursor options for better performance
                allowDiskUse=True,
                batchSize=100
            )
            
            # Pre-allocate array with a reasonable size estimate
            quarters = []
            
            # Fast path for most common case - just extract quarter ID
            async for doc in cursor:
                if doc["_id"]:
                    quarters.append(doc["_id"])
            
            logger.info(f"Retrieved {len(quarters)} available quarters from database")

            cache_key = get_cache_key("quarters", "all")
            if not force_refresh:
                cached_data = get_from_cache(cache_key)
                if cached_data:
                    return cached_data.get("quarters", [])

            response = {"quarters": quarters}
            set_to_cache(cache_key, response, CACHE_EXPIRY_LONG)
            return quarters
        except Exception as e:
            logger.error(f"Error fetching available quarters: {str(e)}")
            # Add error details for better debugging
            raise Exception(f"Failed to fetch available quarters: {str(e)}")