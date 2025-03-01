"""
Script to backup the database before making changes.
"""
import asyncio
import os
import logging
import json
from datetime import datetime
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("backup_db.log")
    ]
)

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

async def backup_database():
    """
    Backup the database before making changes.
    """
    # Set up MongoDB connection
    mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(mongo_uri)
    db = client.stock_data
    collection = db.detailed_financials
    
    try:
        # Create backup directory if it doesn't exist
        backup_dir = "db_backups"
        os.makedirs(backup_dir, exist_ok=True)
        
        # Create backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"detailed_financials_backup_{timestamp}.json")
        
        # Count total documents
        count = await collection.count_documents({})
        logger.info(f"Backing up {count} documents from detailed_financials collection")
        
        # Fetch all documents
        documents = await collection.find({}).to_list(length=None)
        
        # Convert ObjectId to string for JSON serialization
        for doc in documents:
            doc["_id"] = str(doc["_id"])
        
        # Write to backup file
        with open(backup_file, 'w') as f:
            json.dump(documents, f, indent=2, default=str)
        
        logger.info(f"Backup completed successfully. Saved to {backup_file}")
        logger.info(f"Backed up {len(documents)} documents")
        
    except Exception as e:
        logger.error(f"Error backing up database: {str(e)}")
    finally:
        # Close MongoDB connection
        client.close()
        logger.info("MongoDB connection closed")

if __name__ == "__main__":
    asyncio.run(backup_database()) 