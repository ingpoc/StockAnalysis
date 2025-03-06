#!/usr/bin/env python3
"""
Utility to backup the detailed_financials collection to a JSON file.
"""
import os
import sys
import json
import logging
from datetime import datetime
from bson import json_util
from pymongo import MongoClient
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
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

# Create backup directory if it doesn't exist
BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "db_backups")
os.makedirs(BACKUP_DIR, exist_ok=True)

# Create router for API endpoints
router = APIRouter(
    prefix="/database",
    tags=["database"],
    responses={404: {"description": "Not found"}},
)

def backup_database(backup_file=None):
    """
    Backup the detailed_financials collection to a JSON file.
    
    Args:
        backup_file (str, optional): Path to the backup file. If not provided, a timestamped file will be created.
        
    Returns:
        str: Path to the backup file.
    """
    try:
        # Generate backup filename with timestamp if not provided
        if not backup_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(BACKUP_DIR, f"{COLLECTION_NAME}_backup_{timestamp}.json")
        
        # Connect to MongoDB
        logger.info(f"Connecting to MongoDB at {MONGO_URI}")
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        
        # Check if the collection exists
        if COLLECTION_NAME not in db.list_collection_names():
            error_msg = f"{COLLECTION_NAME} collection does not exist"
            logger.error(error_msg)
            return None
        
        # Get all documents from the collection
        logger.info(f"Retrieving documents from {COLLECTION_NAME}")
        documents = list(db[COLLECTION_NAME].find())
        
        # Check if any documents were found
        if not documents:
            logger.warning(f"No documents found in {COLLECTION_NAME}")
            return None
        
        # Create backup directory if it doesn't exist
        os.makedirs(os.path.dirname(backup_file), exist_ok=True)
        
        # Write documents to the backup file
        logger.info(f"Writing {len(documents)} documents to {backup_file}")
        with open(backup_file, 'w') as f:
            json.dump(documents, f, default=json_util.default, indent=2)
        
        # Check if the backup file was created successfully
        if os.path.exists(backup_file):
            file_size = os.path.getsize(backup_file) / (1024 * 1024)  # Size in MB
            logger.info(f"Backup completed successfully. File size: {file_size:.2f} MB")
            return backup_file
        else:
            logger.error("Backup file was not created")
            return None
    except Exception as e:
        logger.error(f"Error during backup: {str(e)}")
        return None

@router.post("/backup", response_model=dict)
async def api_backup_database():
    """
    API endpoint to backup the database.
    
    Returns:
        dict: Status of the backup operation.
    """
    try:
        backup_file = backup_database()
        if backup_file:
            return {
                "success": True,
                "message": f"Database backup completed successfully",
                "backup_file": backup_file,
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="Database backup failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during backup: {str(e)}")

if __name__ == "__main__":
    backup_file = backup_database()
    if backup_file:
        print(f"Backup completed successfully: {backup_file}")
        sys.exit(0)
    else:
        print("Backup failed")
        sys.exit(1) 