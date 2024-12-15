from functools import wraps
from datetime import datetime, timedelta
from typing import Any, Callable

# Simple in-memory cache
cache_store = {}
cache_timestamps = {}

def cache_with_ttl(ttl_seconds: int = 300):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            force_refresh = kwargs.get('force_refresh', False)
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"

            # Check if cached and not expired
            if not force_refresh and cache_key in cache_store:
                timestamp = cache_timestamps[cache_key]
                if datetime.now() - timestamp < timedelta(seconds=ttl_seconds):
                    return cache_store[cache_key]

            # Execute function and cache result
            result = await func(*args, **kwargs)
            cache_store[cache_key] = result
            cache_timestamps[cache_key] = datetime.now()

            return result
        return wrapper
    return decorator