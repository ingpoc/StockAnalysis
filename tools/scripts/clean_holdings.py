import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from src.config import settings
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def clean_holdings():
    logger.info(f"Connecting to MongoDB at {settings.MONGODB_URI}")
    try:
        # Connect to MongoDB
        client = AsyncIOMotorClient(
            settings.MONGODB_URI,
            maxPoolSize=10,
            retryWrites=True
        )
        
        # Verify the connection
        await client.admin.command('ismaster')
        logger.info("Successfully connected to MongoDB")
        
        # Get database
        db = client[settings.MONGODB_DB_NAME]
        
        # US stock symbols to remove
        us_symbols = ["AAPL", "MSFT", "GOOGL"]
        
        # Remove US stocks from holdings collection
        result = await db.holdings.delete_many({"symbol": {"$in": us_symbols}})
        logger.info(f"Removed {result.deleted_count} US stock holdings")
        
        # Display remaining holdings
        holdings_count = await db.holdings.count_documents({})
        logger.info(f"Remaining holdings: {holdings_count}")
        
        if holdings_count > 0:
            logger.info("Remaining holdings:")
            async for holding in db.holdings.find():
                logger.info(f"  - {holding['symbol']}: {holding['quantity']} shares at {holding['average_price']}")
        
    except Exception as e:
        logger.error(f"Error connecting to MongoDB: {e}")
    finally:
        # Close the connection
        if 'client' in locals():
            client.close()
            logger.info("MongoDB connection closed")

if __name__ == "__main__":
    asyncio.run(clean_holdings()) 