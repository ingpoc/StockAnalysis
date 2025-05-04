#!/usr/bin/env python
"""
Script to normalize timestamps in stock_recommendations collection.
This fixes existing records with inconsistent timestamp formats.
"""
import asyncio
import logging
from datetime import datetime
import sys
import os

# Add the parent directory to the path so we can import project modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.database import get_database, refresh_database_connection

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def normalize_timestamps():
    """Convert all timestamps in stock_recommendations collection to datetime objects."""
    db = await get_database()
    collection = db["stock_recommendations"]
    
    # Create index on timestamp if it doesn't exist
    await collection.create_index([("timestamp", -1)], background=True)
    logger.info("Created index on timestamp field")
    
    # Get count of documents for progress tracking
    total_docs = await collection.count_documents({})
    logger.info(f"Found {total_docs} documents to process")
    
    # Track stats
    processed = 0
    updated = 0
    errors = 0
    
    async for doc in collection.find({}):
        processed += 1
        try:
            symbol = doc.get("symbol", "unknown")
            need_update = False
            
            # Check if timestamp needs conversion
            if "timestamp" in doc:
                if not isinstance(doc["timestamp"], datetime):
                    try:
                        # Convert string timestamp to datetime
                        ts_str = doc["timestamp"]
                        if isinstance(ts_str, str):
                            # Replace Z with +00:00 for Python compatibility
                            if ts_str.endswith('Z'):
                                ts_str = ts_str[:-1] + '+00:00'
                            new_timestamp = datetime.fromisoformat(ts_str)
                            need_update = True
                        else:
                            # If not a string or datetime, set to now
                            logger.warning(f"Invalid timestamp type for {symbol}: {type(doc['timestamp'])}")
                            new_timestamp = datetime.now()
                            need_update = True
                    except Exception as e:
                        logger.error(f"Error parsing timestamp for {symbol}: {e}")
                        new_timestamp = datetime.now()
                        need_update = True
            else:
                # If no timestamp, add one
                logger.warning(f"No timestamp found for {symbol}")
                new_timestamp = datetime.now()
                need_update = True
                
            # Update the document if needed
            if need_update:
                result = await collection.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"timestamp": new_timestamp}}
                )
                if result.modified_count > 0:
                    updated += 1
                    logger.info(f"Updated timestamp for {symbol}")
                else:
                    logger.warning(f"Failed to update timestamp for {symbol}")
            
            # Log progress periodically
            if processed % 10 == 0:
                logger.info(f"Processed {processed}/{total_docs} documents, updated {updated}")
                
        except Exception as e:
            errors += 1
            logger.error(f"Error processing document {doc.get('_id')}: {e}")
    
    logger.info(f"Finished processing {processed} documents. Updated: {updated}, Errors: {errors}")

async def main():
    """Main entry point for the script."""
    try:
        logger.info("Starting timestamp normalization...")
        await normalize_timestamps()
        logger.info("Timestamp normalization complete!")
    except Exception as e:
        logger.error(f"Error in main function: {e}")
    finally:
        # Close database connection
        from src.utils.database import close_mongodb_connection
        await close_mongodb_connection()

if __name__ == "__main__":
    asyncio.run(main())
