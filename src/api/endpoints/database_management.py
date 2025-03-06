from fastapi import APIRouter, HTTPException, BackgroundTasks
import os
import sys
import json
import logging
from datetime import datetime
import subprocess
from pathlib import Path
from bson import ObjectId

# Import the database utility functions
from src.utils.database import backup_database, restore_database
from src.utils.database.validate_database import validate_database

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

router = APIRouter()

# Path to the backups directory
DB_BACKUPS_DIR = Path(__file__).parent.parent.parent.parent / "db_backups"

@router.post("/backup", status_code=200)
async def backup_database_endpoint(background_tasks: BackgroundTasks):
    """
    Backup the database to a JSON file.
    """
    try:
        # Run the backup function as a background task
        def run_backup():
            try:
                backup_file = backup_database()
                logger.info(f"Database backup completed successfully: {backup_file}")
            except Exception as e:
                logger.error(f"Backup error: {str(e)}")
                
        background_tasks.add_task(run_backup)
        return {"message": "Database backup started"}
    except Exception as e:
        logger.error(f"Error starting backup: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error starting backup: {str(e)}")

@router.post("/restore", status_code=200)
async def restore_database_endpoint(background_tasks: BackgroundTasks, file_path: str = None):
    """
    Restore the database from a backup file.
    """
    try:
        # Run the restore function as a background task
        def run_restore():
            try:
                success = restore_database(file_path)
                if success:
                    logger.info("Database restoration completed successfully")
                else:
                    logger.error("Database restoration failed")
            except Exception as e:
                logger.error(f"Restore error: {str(e)}")
                
        background_tasks.add_task(run_restore)
        return {"message": "Database restoration started"}
    except Exception as e:
        logger.error(f"Error starting restoration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error starting restoration: {str(e)}")

@router.get("/check", status_code=200)
async def check_database():
    """
    Check the database structure and content.
    """
    try:
        # Call the validate endpoint directly
        validation_result = await validate_database_endpoint()
        
        # Extract relevant information for the frontend
        document_count = 0
        quarters = []
        
        # Get document count from detailed_financials collection
        if "summary" in validation_result and "collections_summary" in validation_result["summary"]:
            collections = validation_result["summary"]["collections_summary"]
            if "detailed_financials" in collections:
                document_count = collections["detailed_financials"].get("document_count", 0)
                quarters = collections["detailed_financials"].get("quarters", [])
        
        # Format the response for the frontend
        return {
            "success": validation_result["status"] != "error",
            "documentCount": document_count,
            "quarters": quarters,
            "errors": len(validation_result.get("errors", [])),
            "warnings": len(validation_result.get("warnings", [])),
            "details": validation_result
        }
    except Exception as e:
        logger.error(f"Error checking database: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error checking database: {str(e)}")

@router.get("/backups", status_code=200)
async def list_backups():
    """
    List all available database backups.
    """
    try:
        if not DB_BACKUPS_DIR.exists():
            return {"backups": []}
            
        backups = []
        for file in DB_BACKUPS_DIR.glob("*.json"):
            file_stats = file.stat()
            backups.append({
                "filename": file.name,
                "path": str(file),
                "size": file_stats.st_size,
                "created": datetime.fromtimestamp(file_stats.st_ctime).isoformat()
            })
            
        return {"backups": sorted(backups, key=lambda x: x["created"], reverse=True)}
    except Exception as e:
        logger.error(f"Error listing backups: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing backups: {str(e)}")

@router.get("/validate", status_code=200)
async def validate_database_endpoint():
    """
    Validate the database structure and content.
    """
    try:
        logger.info("Starting database validation")
        
        # Create a new validator instance directly
        from src.utils.database.validate_database import DatabaseValidator
        validator = DatabaseValidator()
        validation_result = await validator.validate_all()
        
        # Custom JSON serialization to handle non-serializable types
        def json_serializer(obj):
            if isinstance(obj, (datetime, ObjectId)):
                return str(obj)
            return None
        
        # Log a summary instead of the full result
        summary = {
            "status": "success",
            "errors_count": len(validation_result.get("errors", [])),
            "warnings_count": len(validation_result.get("warnings", [])),
            "collections_checked": len(validation_result.get("summary", {}).get("collections_summary", {}))
        }
        logger.info(f"Database validation completed with summary: {summary}")
        
        return validation_result
    except Exception as e:
        logger.error(f"Error validating database: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error validating database: {str(e)}") 