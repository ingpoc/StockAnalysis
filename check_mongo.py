import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from src.config import settings
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_mongodb():
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
        logger.info(f"Using database: {settings.MONGODB_DB_NAME}")
        
        # List collections
        collections = await db.list_collection_names()
        logger.info(f"Available collections: {collections}")
        
        # Check holdings collection
        holdings_count = await db.holdings.count_documents({})
        logger.info(f"Number of documents in holdings collection: {holdings_count}")
        
        if holdings_count > 0:
            # Show sample holdings
            logger.info("Sample holdings:")
            async for holding in db.holdings.find().limit(5):
                logger.info(f"  - {holding}")
        
        # Check stock data collection
        stock_data_count = await db.stock_data.count_documents({})
        logger.info(f"Number of documents in stock_data collection: {stock_data_count}")
        
        if stock_data_count > 0:
            # Show available stock symbols
            logger.info("Available stock symbols:")
            symbols = []
            async for stock in db.stock_data.find({}, {"symbol": 1}):
                symbols.append(stock.get("symbol"))
            logger.info(f"  - {', '.join(symbols)}")
        
    except Exception as e:
        logger.error(f"Error connecting to MongoDB: {e}")
    finally:
        # Close the connection
        if 'client' in locals():
            client.close()
            logger.info("MongoDB connection closed")

if __name__ == "__main__":
    asyncio.run(check_mongodb()) 