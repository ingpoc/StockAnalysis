"""
Database connection utilities.
This module provides functions for connecting to MongoDB.
"""

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from pymongo.server_api import ServerApi
import os
from dotenv import load_dotenv
import logging
import asyncio
import functools
import time

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class Database:
    client: AsyncIOMotorClient = None
    is_connected: bool = False
    last_connection_check: float = 0
    connection_check_interval: float = 30.0  # seconds

db = Database()

async def get_database():
    """
    Get a reference to the database with connection management.
    Includes automatic reconnection and health checks for long-running applications.
    
    Returns:
        AsyncIOMotorDatabase: Database connection.
    """
    current_time = time.time()
    
    # Initial connection if no client exists
    if db.client is None:
        await connect_to_mongodb()
    
    # Periodic connection health check
    elif not db.is_connected or (current_time - db.last_connection_check) > db.connection_check_interval:
        try:
            # Fast check if we're still connected
            await asyncio.wait_for(db.client.admin.command('ping'), timeout=2.0)
            db.is_connected = True
            db.last_connection_check = current_time
        except (ConnectionFailure, ServerSelectionTimeoutError, asyncio.TimeoutError):
            logger.warning("MongoDB connection appears to be down. Attempting to reconnect...")
            await refresh_database_connection()
        except Exception as e:
            logger.error(f"Unexpected error checking MongoDB connection: {e}")
            await refresh_database_connection()
    
    return db.client[os.getenv("MONGODB_DB_NAME", "stock_data")]

async def refresh_database_connection():
    """
    Refresh the MongoDB connection by closing the existing connection and creating a new one.
    This is useful when the database has been updated externally or the connection is stale.
    """
    logger.info("Refreshing MongoDB connection...")
    if db.client is not None:
        db.client.close()
        db.client = None
        db.is_connected = False
        logger.info("Closed existing MongoDB connection")
    
    await connect_to_mongodb()
    logger.info("MongoDB connection refreshed")
    return db.client[os.getenv("MONGODB_DB_NAME", "stock_data")]

async def connect_to_mongodb():
    """
    Connect to MongoDB with optimized connection pooling parameters.
    
    Parameters are carefully tuned for balance between performance and resource usage:
    - maxPoolSize: Maximum number of connections in the pool (adjusted based on workload)
    - minPoolSize: Minimum number of connections to maintain
    - maxIdleTimeMS: How long a connection can remain idle before being closed
    - waitQueueTimeoutMS: How long a thread will wait for a connection
    - connectTimeoutMS: Timeout for initial connection
    - serverSelectionTimeoutMS: Timeout for selecting a server
    - retryWrites: Whether to retry write operations
    """
    logger.info("Connecting to MongoDB...")
    try:
        mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        # Configure optimal connection pooling settings
        db.client = AsyncIOMotorClient(
            mongo_uri,
            server_api=ServerApi('1'),
            maxPoolSize=50,  # Adjust based on expected concurrent operations
            minPoolSize=5,   # Maintain minimum connections for quick response
            maxIdleTimeMS=60000,  # Close idle connections after 60 seconds
            waitQueueTimeoutMS=5000,  # Maximum time operations wait for a connection
            connectTimeoutMS=10000,  # Connection timeout
            serverSelectionTimeoutMS=10000,  # Server selection timeout
            retryWrites=True,  # Automatically retry write operations
            socketTimeoutMS=20000,  # Socket timeout
        )
        
        # Verify the connection
        await asyncio.wait_for(db.client.admin.command('ismaster'), timeout=5.0)
        db.is_connected = True
        db.last_connection_check = time.time()
        logger.info("Connected to MongoDB successfully")
    except ConnectionFailure as e:
        db.is_connected = False
        logger.error(f"Could not connect to MongoDB: {e}")
        raise
    except Exception as e:
        db.is_connected = False
        logger.error(f"Unexpected error connecting to MongoDB: {e}")
        raise

async def close_mongodb_connection():
    """
    Close the MongoDB connection.
    """
    logger.info("Closing MongoDB connection...")
    if db.client is not None:
        db.client.close()
        db.client = None
        db.is_connected = False
        logger.info("MongoDB connection closed successfully")

# Connection monitoring decorator (optional)
def with_database_monitoring(func):
    """Decorator to monitor database operations and reconnect if needed."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.warning(f"Database operation failed, attempting to reconnect: {e}")
            await refresh_database_connection()
            return await func(*args, **kwargs)
    return wrapper

async def ensure_indexes():
    """
    Create necessary indexes for collections to optimize query performance.
    Should be called during application startup after the database connection is established.
    """
    logger.info("Creating database indexes...")
    db_instance = await get_database()
    
    try:
        # Indexes for detailed_financials collection
        await db_instance.detailed_financials.create_index([("symbol", 1)], background=True)
        await db_instance.detailed_financials.create_index([("company_name", 1)], background=True)
        await db_instance.detailed_financials.create_index([("financial_metrics.quarter", 1)], background=True)
        await db_instance.detailed_financials.create_index([("symbol", 1), ("financial_metrics.quarter", 1)], background=True)
        
        # Indexes for holdings collection
        await db_instance.holdings.create_index([("symbol", 1)], background=True)
        await db_instance.holdings.create_index([("company_name", 1)], background=True)
        
        # Indexes for analysis collection
        await db_instance.analysis.create_index([("symbol", 1)], background=True)
        await db_instance.analysis.create_index([("timestamp", -1)], background=True)
        await db_instance.analysis.create_index([("symbol", 1), ("timestamp", -1)], background=True)
        
        logger.info("Database indexes created successfully")
    except Exception as e:
        logger.error(f"Error creating database indexes: {e}")
        # Don't raise exception to allow application to start even if index creation fails
        logger.warning("Application will continue without optimized indexes") 