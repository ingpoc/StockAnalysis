#!/usr/bin/env python3
"""
Utility to restore detailed_financials collection from backup.
"""
import os
import sys
import json
import logging
import glob
from datetime import datetime
from bson import json_util, ObjectId
from pymongo import MongoClient
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
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

def get_latest_backup():
    """
    Get the path to the latest backup file.
    
    Returns:
        str: Path to the latest backup file or None if no backups found.
    """
    backup_files = glob.glob(os.path.join(BACKUP_DIR, f"{COLLECTION_NAME}_backup_*.json"))
    if not backup_files:
        return None
    
    # Sort by modification time (newest first)
    backup_files.sort(key=os.path.getmtime, reverse=True)
    return backup_files[0]

def restore_database(backup_path=None):
    """
    Restore detailed_financials collection from backup file.
    
    Args:
        backup_path (str, optional): Path to the backup file. If not provided, the latest backup will be used.
        
    Returns:
        bool: True if restore was successful, False otherwise.
    """
    try:
        # Use the latest backup if not specified
        if not backup_path:
            backup_path = get_latest_backup()
            if not backup_path:
                logger.error("No backup files found")
                return False
        
        # Check if backup file exists
        if not os.path.exists(backup_path):
            logger.error(f"Backup file not found: {backup_path}")
            return False
        
        # Check the backup file size
        file_size = os.path.getsize(backup_path)
        logger.info(f"Backup file size: {file_size / (1024 * 1024):.2f} MB")
        
        # Connect to MongoDB
        logger.info(f"Connecting to MongoDB at {MONGO_URI}")
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        
        # Drop the existing collection if it exists
        if COLLECTION_NAME in db.list_collection_names():
            logger.info(f"Dropping existing {COLLECTION_NAME} collection")
            db[COLLECTION_NAME].drop()
        
        # Load the backup file
        logger.info(f"Loading backup from {backup_path}")
        with open(backup_path, 'r') as f:
            documents = json.load(f, object_hook=json_util.object_hook)
        
        # Check if any documents were loaded
        if not documents:
            logger.warning("No documents found in backup file")
            return False
        
        # Insert documents into the collection
        logger.info(f"Inserting {len(documents)} documents into {COLLECTION_NAME}")
        result = db[COLLECTION_NAME].insert_many(documents)
        
        # Check if all documents were inserted
        if len(result.inserted_ids) == len(documents):
            logger.info(f"Restore completed successfully. Inserted {len(result.inserted_ids)} documents.")
            return True
        else:
            logger.error(f"Only {len(result.inserted_ids)} out of {len(documents)} documents were inserted")
            return False
    except Exception as e:
        logger.error(f"Error during restore: {str(e)}")
        return False

@router.post("/restore", response_model=dict)
async def api_restore_database(backup_file: str = None):
    """
    API endpoint to restore the database from backup.
    
    Args:
        backup_file (str, optional): Path to the backup file. If not provided, the latest backup will be used.
        
    Returns:
        dict: Status of the restore operation.
    """
    try:
        success = restore_database(backup_file)
        if success:
            return {
                "success": True,
                "message": "Database restore completed successfully",
                "backup_file": backup_file or get_latest_backup(),
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="Database restore failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during restore: {str(e)}")

@router.get("/backups", response_model=list)
async def list_backups():
    """
    API endpoint to list available database backups.
    
    Returns:
        list: List of available backup files with metadata.
    """
    try:
        backup_files = glob.glob(os.path.join(BACKUP_DIR, f"{COLLECTION_NAME}_backup_*.json"))
        
        # Sort by modification time (newest first)
        backup_files.sort(key=os.path.getmtime, reverse=True)
        
        # Get metadata for each backup file
        backups = []
        for backup_file in backup_files:
            file_size = os.path.getsize(backup_file) / (1024 * 1024)  # Size in MB
            mod_time = datetime.fromtimestamp(os.path.getmtime(backup_file))
            
            backups.append({
                "file_name": os.path.basename(backup_file),
                "file_path": backup_file,
                "file_size_mb": round(file_size, 2),
                "modified_time": mod_time.isoformat(),
                "age_days": (datetime.now() - mod_time).days
            })
        
        return backups
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing backups: {str(e)}")

if __name__ == "__main__":
    success = restore_database()
    if success:
        print("Restore completed successfully")
        sys.exit(0)
    else:
        print("Restore failed")
        sys.exit(1) 