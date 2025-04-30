"""
Cache utilities for storing and retrieving data to improve performance.
This module provides functions for caching expensive API responses.
"""
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional
import redis.asyncio as redis

# Configure logging
logger = logging.getLogger(__name__)

# Redis connection (use environment variable or default to localhost)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# Cache expiration times (in seconds)
CACHE_EXPIRY_SHORT = 60 * 5  # 5 minutes for short-lived cache
CACHE_EXPIRY_MEDIUM = 60 * 30  # 30 minutes for medium-lived cache
CACHE_EXPIRY_LONG = 60 * 60 * 24  # 24 hours for long-lived cache

def get_cache_key(prefix: str, key: str) -> str:
    """
    Generate a unique cache key based on prefix and key.
    
    Args:
        prefix (str): Prefix for the cache key (e.g., endpoint name).
        key (str): Unique identifier for the cached item.
        
    Returns:
        str: Combined cache key.
    """
    return f"{prefix}:{key}"

async def get_from_cache(cache_key: str) -> Optional[Any]:
    """
    Retrieve data from cache using the provided key.
    
    Args:
        cache_key (str): Key to look up in cache.
        
    Returns:
        Optional[Any]: Cached data if found and valid, None otherwise.
    """
    try:
        cached_data = await redis_client.get(cache_key)
        if cached_data:
            logger.info(f"Cache hit for key: {cache_key}")
            return json.loads(cached_data)
        logger.info(f"Cache miss for key: {cache_key}")
        return None
    except Exception as e:
        logger.error(f"Error retrieving from cache for key {cache_key}: {str(e)}")
        return None

async def set_to_cache(cache_key: str, data: Any, expiry_seconds: int) -> bool:
    """
    Store data in cache with the specified key and expiration time.
    
    Args:
        cache_key (str): Key to store data under.
        data (Any): Data to cache.
        expiry_seconds (int): Cache expiration time in seconds.
        
    Returns:
        bool: True if caching was successful, False otherwise.
    """
    try:
        serialized_data = json.dumps(data)
        await redis_client.setex(cache_key, expiry_seconds, serialized_data)
        logger.info(f"Cached data for key: {cache_key} with expiry {expiry_seconds}s")
        return True
    except Exception as e:
        logger.error(f"Error setting cache for key {cache_key}: {str(e)}")
        return False

async def clear_cache_with_prefix(prefix: str) -> bool:
    """
    Clear all cache entries with the specified prefix without using KEYS operation.
    
    Args:
        prefix (str): Prefix to match cache keys for deletion.
        
    Returns:
        bool: True if cache clearing was successful, False otherwise.
    """
    try:
        cursor = 0
        count = 0
        while True:
            cursor, keys = await redis_client.scan(cursor, match=f"{prefix}:*", count=100)
            if keys:
                await redis_client.delete(*keys)
                count += len(keys)
            if cursor == 0:
                break
        logger.info(f"Cleared {count} cache entries with prefix: {prefix}")
        return True
    except Exception as e:
        logger.error(f"Error clearing cache with prefix {prefix}: {str(e)}")
        return False

async def init_redis():
    """
    Initialize Redis connection and check if it's working.
    """
    try:
        await redis_client.ping()
        logger.info("Redis connection initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Redis connection: {str(e)}")