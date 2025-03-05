#!/usr/bin/env python3
"""
Script to backup the detailed_financials collection to a JSON file.
"""
import os
import sys
import json
import logging
from datetime import datetime
from bson import json_util
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
COLLECTION_NAME = "detailed_financials"

# Generate backup filename with timestamp
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db_backups")
BACKUP_FILE = os.path.join(BACKUP_DIR, f"{COLLECTION_NAME}_backup_{timestamp}.json")

def backup_database():
    """Backup the detailed_financials collection to a JSON file."""
    try:
        # Print marker for script start (helps with debugging)
        print("SCRIPT_START: Database backup beginning")
        
        # Connect to MongoDB
        logger.info(f"Connecting to MongoDB at {MONGO_URI}")
        print(f"INFO: Connecting to MongoDB at {MONGO_URI}")
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        
        # Check if the collection exists
        if COLLECTION_NAME not in db.list_collection_names():
            error_msg = f"{COLLECTION_NAME} collection does not exist"
            logger.error(error_msg)
            print(f"ERROR: {error_msg}")
            print("SCRIPT_FAILURE: Database backup failed - collection not found")
            return False
        
        # Get all documents from the collection
        cursor = db[COLLECTION_NAME].find({})
        documents = list(cursor)
        document_count = len(documents)
        logger.info(f"Retrieved {document_count} documents from {COLLECTION_NAME}")
        print(f"INFO: Retrieved {document_count} documents from {COLLECTION_NAME}")
        
        if document_count == 0:
            logger.warning(f"No documents found in {COLLECTION_NAME}")
            print(f"WARNING: No documents found in {COLLECTION_NAME}")
            print("SCRIPT_FAILURE: Database backup failed - no documents found")
            return False
        
        # Ensure backup directory exists
        os.makedirs(BACKUP_DIR, exist_ok=True)
        print(f"INFO: Backup directory: {BACKUP_DIR}")
        
        # Convert MongoDB documents to JSON
        logger.info(f"Converting documents to JSON")
        print("INFO: Converting documents to JSON")
        json_data = json_util.dumps(documents, indent=2)
        
        # Save to file
        logger.info(f"Saving backup to {BACKUP_FILE}")
        print(f"INFO: Saving backup to {BACKUP_FILE}")
        with open(BACKUP_FILE, 'w') as f:
            f.write(json_data)
        
        # Check the backup file size
        file_size = os.path.getsize(BACKUP_FILE)
        logger.info(f"Backup file size: {file_size / (1024 * 1024):.2f} MB")
        print(f"INFO: Backup file size: {file_size / (1024 * 1024):.2f} MB")
        
        # Add specific success marker
        print(f"SCRIPT_SUCCESS: Backup created successfully at {BACKUP_FILE}")
        logger.info(f"Backup completed successfully to {BACKUP_FILE}")
        return True
    
    except Exception as e:
        error_message = f"Error backing up database: {str(e)}"
        logger.error(error_message)
        print(f"ERROR: {error_message}")
        print("SCRIPT_FAILURE: Database backup failed with an exception")
        return False
    finally:
        if 'client' in locals():
            client.close()
            logger.info("MongoDB connection closed")
            print("INFO: MongoDB connection closed")

if __name__ == "__main__":
    success = backup_database()
    if success:
        print("BACKUP_COMPLETED: Database backup completed successfully")
        sys.exit(0)
    else:
        print("BACKUP_FAILED: Database backup failed")
        sys.exit(1) 