#!/usr/bin/env python3
"""
Script to fix database format issues.
This is a placeholder script that will be called by reset_database.py.
"""
import os
import sys
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

def fix_database_format():
    """Fix any format issues in the database"""
    try:
        print("SCRIPT_START: Database format fix beginning")
        
        # Connect to MongoDB
        logger.info(f"Connecting to MongoDB at {MONGO_URI}")
        print(f"INFO: Connecting to MongoDB at {MONGO_URI}")
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        
        # Check if the collection exists
        if "detailed_financials" not in db.list_collection_names():
            error_msg = "detailed_financials collection not found"
            logger.error(error_msg)
            print(f"ERROR: {error_msg}")
            print("SCRIPT_FAILURE: Database format fix failed - collection not found")
            return False
        
        # Count documents
        count = db.detailed_financials.count_documents({})
        logger.info(f"Found {count} documents in detailed_financials collection")
        print(f"INFO: Found {count} documents in detailed_financials collection")
        
        # For now, just log that we're checking the format
        # In a real implementation, you would check and fix format issues here
        logger.info("Checking document formats...")
        print("INFO: Checking document formats...")
        
        # Placeholder for format checking logic
        print("INFO: No format issues found or fixed (placeholder)")
        
        print("SCRIPT_SUCCESS: Database format check completed")
        logger.info("Database format check completed")
        return True
        
    except Exception as e:
        error_msg = f"Error fixing database format: {str(e)}"
        logger.error(error_msg)
        print(f"ERROR: {error_msg}")
        print("SCRIPT_FAILURE: Database format fix failed with an exception")
        return False
    finally:
        if 'client' in locals():
            client.close()
            logger.info("MongoDB connection closed")
            print("INFO: MongoDB connection closed")

if __name__ == "__main__":
    success = fix_database_format()
    if success:
        print("SCRIPT_SUCCESS: Database format fix completed successfully")
        sys.exit(0)
    else:
        print("SCRIPT_FAILURE: Database format fix failed")
        sys.exit(1) 