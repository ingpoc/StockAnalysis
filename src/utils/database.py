from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from src.config import settings
import logging

logger = logging.getLogger(__name__)

class Database:
    client: AsyncIOMotorClient = None

db = Database()

async def get_database():
    if db.client is None:  # Changed from 'if not db.client'
        await connect_to_mongodb()
    return db.client[settings.MONGODB_DB_NAME]

async def connect_to_mongodb():
    logger.info("Connecting to MongoDB...")
    try:
        db.client = AsyncIOMotorClient(
            settings.MONGODB_URI,
            maxPoolSize=50,
            minPoolSize=10,
            maxIdleTimeMS=45000,
            waitQueueTimeoutMS=5000,
            retryWrites=True
        )
        # Verify the connection
        await db.client.admin.command('ismaster')
        logger.info("Connected to MongoDB")
    except ConnectionFailure as e:
        logger.error(f"Could not connect to MongoDB: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error connecting to MongoDB: {e}")
        raise

async def close_mongodb_connection():
    logger.info("Closing MongoDB connection...")
    if db.client is not None:  # Changed from 'if db.client'
        db.client.close()
        logger.info("MongoDB connection closed")