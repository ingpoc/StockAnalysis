#!/usr/bin/env python3
"""
Script to restore detailed_financials collection from backup.
"""
import os
import sys
import json
import asyncio
import logging
from pymongo import MongoClient
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = "stock_data"
BACKUP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                          "db_backups", "detailed_financials_backup_20250301_175830.json")

def restore_database():
    """Restore detailed_financials collection from backup file"""
    try:
        # Connect to MongoDB
        logger.info(f"Connecting to MongoDB at {MONGO_URI}")
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]

        # Check if backup file exists
        if not os.path.exists(BACKUP_PATH):
            logger.error(f"Backup file not found: {BACKUP_PATH}")
            return False

        # Check the backup file size
        file_size = os.path.getsize(BACKUP_PATH)
        logger.info(f"Backup file size: {file_size / (1024 * 1024):.2f} MB")

        # Drop the existing collection if it exists
        if "detailed_financials" in db.list_collection_names():
            logger.info("Dropping existing detailed_financials collection")
            db.detailed_financials.drop()
        
        # Load the backup file
        logger.info("Loading data from backup file")
        with open(BACKUP_PATH, 'r') as f:
            backup_data = json.load(f)
        
        # Ensure backup data is a list
        if not isinstance(backup_data, list):
            logger.error("Backup data is not in the expected format (not a list)")
            return False
        
        logger.info(f"Found {len(backup_data)} documents in backup file")
        
        # Insert the data into the collection
        if backup_data:
            logger.info("Inserting data into detailed_financials collection")
            db.detailed_financials.insert_many(backup_data)
            
            # Verify the restoration
            count = db.detailed_financials.count_documents({})
            logger.info(f"Restoration complete: {count} documents restored")
            return True
        else:
            logger.warning("No documents found in backup file")
            return False
    
    except Exception as e:
        logger.error(f"Error restoring database: {str(e)}")
        return False
    finally:
        if 'client' in locals():
            client.close()
            logger.info("MongoDB connection closed")

if __name__ == "__main__":
    success = restore_database()
    if success:
        logger.info("Database restoration completed successfully")
        sys.exit(0)
    else:
        logger.error("Database restoration failed")
        sys.exit(1) 