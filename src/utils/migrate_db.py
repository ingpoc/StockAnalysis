from pymongo import MongoClient
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate_data():
    try:
        # Connect to old database
        source_client = MongoClient('mongodb://localhost:27017/')
        source_db = source_client['stock_data']
        
        # Connect to new database
        dest_client = AsyncIOMotorClient('mongodb://localhost:27017/')
        dest_db = dest_client['stock_data']
        
        # Migrate detailed_financials collection
        logger.info("Starting migration of detailed_financials collection...")
        documents = list(source_db.detailed_financials.find({}))
        if documents:
            await dest_db.detailed_financials.delete_many({})
            await dest_db.detailed_financials.insert_many(documents)
            logger.info(f"Successfully migrated {len(documents)} documents from detailed_financials")
        else:
            logger.warning("No documents found in detailed_financials collection")
        
        # Close connections
        source_client.close()
        dest_client.close()
        logger.info("Migration completed successfully")
        
    except Exception as e:
        logger.error(f"Error during migration: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(migrate_data())