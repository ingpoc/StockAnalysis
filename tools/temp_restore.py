#!/usr/bin/env python3
"""
Temporary script to restore from the latest backup: /Users/gurusharan/Documents/Projects/StockDashboard/cursor-project/StockAnalysis/db_backups/detailed_financials_backup_20250302_172639.json
"""
import os
import sys
import json
import logging
from pymongo import MongoClient
from bson import json_util
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = "stock_data"
BACKUP_FILE = "/Users/gurusharan/Documents/Projects/StockDashboard/cursor-project/StockAnalysis/db_backups/detailed_financials_backup_20250302_172639.json"

def restore_database():
    """Restore detailed_financials collection from latest backup file"""
    try:
        print("SCRIPT_START: Database restore beginning")
        print(f"INFO: Using latest backup file: {BACKUP_FILE}")
        
        # Connect to MongoDB
        logger.info(f"Connecting to MongoDB at {MONGO_URI}")
        print(f"INFO: Connecting to MongoDB at {MONGO_URI}")
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]

        # Check if backup file exists
        if not os.path.exists(BACKUP_FILE):
            error_msg = f"Backup file not found: {BACKUP_FILE}"
            logger.error(error_msg)
            print(f"ERROR: {error_msg}")
            print("SCRIPT_FAILURE: Database restore failed - backup file not found")
            return False

        # Check the backup file size
        file_size = os.path.getsize(BACKUP_FILE)
        logger.info(f"Backup file size: {file_size / (1024 * 1024):.2f} MB")
        print(f"INFO: Backup file size: {file_size / (1024 * 1024):.2f} MB")

        # Drop the existing collection if it exists
        if "detailed_financials" in db.list_collection_names():
            logger.info("Dropping existing detailed_financials collection")
            print("INFO: Dropping existing detailed_financials collection")
            db.detailed_financials.drop()
        
        # Load the backup file
        logger.info("Loading data from backup file")
        print("INFO: Loading data from backup file")
        with open(BACKUP_FILE, 'r') as f:
            backup_data_str = f.read()
            
        # Parse the JSON
        print("INFO: Parsing JSON data")
        backup_data = json_util.loads(backup_data_str)
        
        # Ensure backup data is a list
        if not isinstance(backup_data, list):
            error_msg = "Backup data is not in the expected format (not a list)"
            logger.error(error_msg)
            print(f"ERROR: {error_msg}")
            print("SCRIPT_FAILURE: Database restore failed - invalid backup format")
            return False
        
        logger.info(f"Found {len(backup_data)} documents in backup file")
        print(f"INFO: Found {len(backup_data)} documents in backup file")
        
        # Insert the data into the collection
        if backup_data:
            logger.info("Inserting data into detailed_financials collection")
            print("INFO: Inserting data into detailed_financials collection")
            db.detailed_financials.insert_many(backup_data)
            
            # Verify the restoration
            count = db.detailed_financials.count_documents({})
            logger.info(f"Restoration complete: {count} documents restored")
            print(f"INFO: Restoration complete: {count} documents restored")
            print("SCRIPT_SUCCESS: Database successfully restored from backup")
            return True
        else:
            logger.warning("No documents found in backup file")
            print("WARNING: No documents found in backup file")
            print("SCRIPT_FAILURE: Database restore failed - empty backup")
            return False
    
    except Exception as e:
        error_msg = f"Error restoring database: {str(e)}"
        logger.error(error_msg)
        print(f"ERROR: {error_msg}")
        print("SCRIPT_FAILURE: Database restore failed with an exception")
        return False
    finally:
        if 'client' in locals():
            client.close()
            logger.info("MongoDB connection closed")
            print("INFO: MongoDB connection closed")

if __name__ == "__main__":
    success = restore_database()
    if success:
        print("RESTORE_COMPLETED: Database successfully restored from backup")
        sys.exit(0)
    else:
        print("RESTORE_FAILED: Database restore failed")
        sys.exit(1)
