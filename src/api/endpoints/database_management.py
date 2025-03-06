from fastapi import APIRouter, HTTPException, BackgroundTasks
import os
import sys
import json
import logging
from datetime import datetime
import subprocess
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

router = APIRouter()

# Get the path to the tests directory
TESTS_DIR = Path(__file__).parent.parent.parent.parent / "tests"
BACKUP_SCRIPT = TESTS_DIR / "backup_database.py"
RESTORE_SCRIPT = TESTS_DIR / "restore_database.py"
CHECK_SCRIPT = TESTS_DIR / "check_database.py"
DB_BACKUPS_DIR = Path(__file__).parent.parent.parent.parent / "db_backups"

@router.post("/backup", status_code=200)
async def backup_database(background_tasks: BackgroundTasks):
    """
    Backup the database to a JSON file.
    """
    try:
        # Run the backup script as a background task
        def run_backup():
            result = subprocess.run(
                [sys.executable, str(BACKUP_SCRIPT)],
                capture_output=True,
                text=True
            )
            logger.info(f"Backup script output: {result.stdout}")
            if result.returncode != 0:
                logger.error(f"Backup script error: {result.stderr}")
                
        background_tasks.add_task(run_backup)
        return {"message": "Database backup started"}
    except Exception as e:
        logger.error(f"Error starting backup: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error starting backup: {str(e)}")

@router.post("/restore", status_code=200)
async def restore_database(background_tasks: BackgroundTasks, file_path: str = None):
    """
    Restore the database from a backup file.
    """
    try:
        # Run the restore script as a background task
        def run_restore():
            cmd = [sys.executable, str(RESTORE_SCRIPT)]
            if file_path:
                cmd.extend(["--file", file_path])
                
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )
            logger.info(f"Restore script output: {result.stdout}")
            if result.returncode != 0:
                logger.error(f"Restore script error: {result.stderr}")
                
        background_tasks.add_task(run_restore)
        return {"message": "Database restoration started"}
    except Exception as e:
        logger.error(f"Error starting restoration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error starting restoration: {str(e)}")

@router.get("/check", status_code=200)
async def check_database(background_tasks: BackgroundTasks):
    """
    Check the database structure and content.
    """
    try:
        # Run the check script as a background task
        def run_check():
            result = subprocess.run(
                [sys.executable, str(CHECK_SCRIPT)],
                capture_output=True,
                text=True
            )
            logger.info(f"Check script output: {result.stdout}")
            if result.returncode != 0:
                logger.error(f"Check script error: {result.stderr}")
                
        background_tasks.add_task(run_check)
        return {"message": "Database check started"}
    except Exception as e:
        logger.error(f"Error starting database check: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error starting database check: {str(e)}")

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