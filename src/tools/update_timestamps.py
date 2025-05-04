import asyncio
import logging
from datetime import datetime
from src.utils.database import get_database

logger = logging.getLogger(__name__)

async def update_timestamp_format_in_db():
    """Update all string timestamps in the stock_recommendations collection to datetime objects."""
    try:
        db = await get_database()
        collection = db["stock_recommendations"]
        
        # Find all documents with string timestamps
        cursor = collection.find({"timestamp": {"$type": "string"}})
        
        async for doc in cursor:
            try:
                # Convert string timestamp to datetime object
                ts_str = doc["timestamp"]
                if ts_str.endswith('Z'):
                    ts_str = ts_str[:-1] + '+00:00'
                new_timestamp = datetime.fromisoformat(ts_str)
                
                # Update the document with the new timestamp
                await collection.update_one(
                    {"_id": doc["_id"]}, 
                    {"$set": {"timestamp": new_timestamp}}
                )
                
                logger.info(f"Updated timestamp for recommendation {doc['_id']}")
            except Exception as e:
                logger.error(f"Error updating timestamp for document {doc['_id']}: {str(e)}")
    except Exception as e:
        logger.error(f"Error accessing database for timestamp update: {str(e)}")

if __name__ == "__main__":
    asyncio.run(update_timestamp_format_in_db()) 