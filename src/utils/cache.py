import json
import logging
from functools import wraps
from typing import Any, Callable
from datetime import timedelta
import redis.asyncio as _redis
from src.config import settings

# Initialize Redis client for async caching
redis_client = _redis.from_url(settings.REDIS_URL, db=settings.REDIS_DB)

logger = logging.getLogger(__name__)

async def clear_cache_with_prefix(prefix: str):
    """
    Clear all Redis cache entries that start with the given prefix.

    Args:
        prefix (str): The prefix to match against cache keys.
    """
    pattern = f"{prefix}*"
    keys_to_remove = []
    async for key in redis_client.scan_iter(match=pattern):
        keys_to_remove.append(key)
    if keys_to_remove:
        await redis_client.delete(*keys_to_remove)
    logger.info(f"Cleared {len(keys_to_remove)} Redis cache entries with prefix '{prefix}'")

def cache_with_ttl(ttl_seconds: int = 300):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key based on function name and args
            force_refresh = kwargs.get('force_refresh', False)
            cache_key = f"{func.__name__}:{args}:{kwargs}"

            # Try retrieving from Redis
            if not force_refresh:
                try:
                    cached = await redis_client.get(cache_key)
                    if cached:
                        return json.loads(cached)
                except Exception as e:
                    logger.warning(f"Redis GET error for {cache_key}: {e}")

            # Call the original function and cache its result
            result = await func(*args, **kwargs)
            try:
                # Prepare data for serialization
                data_to_cache = result.dict() if hasattr(result, 'dict') else result
                serialized = json.dumps(data_to_cache, default=str)
                await redis_client.set(cache_key, serialized, ex=ttl_seconds)
            except Exception as e:
                logger.warning(f"Redis SET error for {cache_key}: {e}")
            return result
        return wrapper
    return decorator