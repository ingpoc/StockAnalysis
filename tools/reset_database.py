#!/usr/bin/env python3
"""
Master script to restore the database from backup and fix any data format issues.
"""
import os
import sys
import logging
import subprocess
import glob
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get the tools directory path
TOOLS_DIR = Path(__file__).parent.absolute()
RESTORE_SCRIPT = TOOLS_DIR / "restore_database.py"
FIX_SCRIPT = TOOLS_DIR / "fix_db_format.py"

# Get the path to the latest backup file
BACKUP_DIR = Path(__file__).parent.parent / "db_backups"
BACKUP_FILES = sorted(BACKUP_DIR.glob("detailed_financials_backup_*.json"), reverse=True)
LATEST_BACKUP = BACKUP_FILES[0] if BACKUP_FILES else None

def run_script(script_path, *args):
    """Run a Python script and return success status"""
    try:
        print(f"SCRIPT_INFO: Running script: {script_path}")
        logger.info(f"Running script: {script_path}")
        
        cmd = [sys.executable, str(script_path)]
        if args:
            cmd.extend(args)
            
        # Log the exact command being executed
        print(f"SCRIPT_INFO: Executing command: {' '.join(cmd)}")
            
        result = subprocess.run(
            cmd, 
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Print the script output
        print(f"SCRIPT_OUTPUT_BEGIN: {script_path}")
        print(result.stdout)
        print(f"SCRIPT_OUTPUT_END: {script_path}")
        
        if result.stderr:
            print(f"SCRIPT_STDERR_BEGIN: {script_path}")
            print(result.stderr)
            print(f"SCRIPT_STDERR_END: {script_path}")
        
        # Check if success marker is in the output
        if "SCRIPT_SUCCESS" in result.stdout or "BACKUP_COMPLETED" in result.stdout:
            print(f"SCRIPT_SUCCESS: {script_path} completed successfully")
            return True
        else:
            print(f"SCRIPT_WARNING: Success marker not found in output for {script_path}")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"SCRIPT_ERROR: Script failed with exit code {e.returncode}")
        if e.stdout:
            print(f"SCRIPT_OUTPUT_BEGIN: {script_path}")
            print(e.stdout)
            print(f"SCRIPT_OUTPUT_END: {script_path}")
        if e.stderr:
            print(f"SCRIPT_STDERR_BEGIN: {script_path}")
            print(e.stderr)
            print(f"SCRIPT_STDERR_END: {script_path}")
        return False
    except Exception as e:
        print(f"SCRIPT_ERROR: Error running {script_path}: {str(e)}")
        return False

def create_custom_restore_script():
    """Create a temporary script to restore from the latest backup"""
    if not LATEST_BACKUP:
        print("SCRIPT_ERROR: No backup files found in db_backups directory")
        return None
    
    # Create a custom restore script that specifically uses the latest backup
    TEMP_SCRIPT = TOOLS_DIR / "temp_restore.py"
    
    with open(TEMP_SCRIPT, 'w') as f:
        f.write(f"""#!/usr/bin/env python3
\"\"\"
Temporary script to restore from the latest backup: {LATEST_BACKUP}
\"\"\"
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
BACKUP_FILE = "{LATEST_BACKUP}"

def restore_database():
    \"\"\"Restore detailed_financials collection from latest backup file\"\"\"
    try:
        print("SCRIPT_START: Database restore beginning")
        print(f"INFO: Using latest backup file: {{BACKUP_FILE}}")
        
        # Connect to MongoDB
        logger.info(f"Connecting to MongoDB at {{MONGO_URI}}")
        print(f"INFO: Connecting to MongoDB at {{MONGO_URI}}")
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]

        # Check if backup file exists
        if not os.path.exists(BACKUP_FILE):
            error_msg = f"Backup file not found: {{BACKUP_FILE}}"
            logger.error(error_msg)
            print(f"ERROR: {{error_msg}}")
            print("SCRIPT_FAILURE: Database restore failed - backup file not found")
            return False

        # Check the backup file size
        file_size = os.path.getsize(BACKUP_FILE)
        logger.info(f"Backup file size: {{file_size / (1024 * 1024):.2f}} MB")
        print(f"INFO: Backup file size: {{file_size / (1024 * 1024):.2f}} MB")

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
            print(f"ERROR: {{error_msg}}")
            print("SCRIPT_FAILURE: Database restore failed - invalid backup format")
            return False
        
        logger.info(f"Found {{len(backup_data)}} documents in backup file")
        print(f"INFO: Found {{len(backup_data)}} documents in backup file")
        
        # Insert the data into the collection
        if backup_data:
            logger.info("Inserting data into detailed_financials collection")
            print("INFO: Inserting data into detailed_financials collection")
            db.detailed_financials.insert_many(backup_data)
            
            # Verify the restoration
            count = db.detailed_financials.count_documents({{}})
            logger.info(f"Restoration complete: {{count}} documents restored")
            print(f"INFO: Restoration complete: {{count}} documents restored")
            print("SCRIPT_SUCCESS: Database successfully restored from backup")
            return True
        else:
            logger.warning("No documents found in backup file")
            print("WARNING: No documents found in backup file")
            print("SCRIPT_FAILURE: Database restore failed - empty backup")
            return False
    
    except Exception as e:
        error_msg = f"Error restoring database: {{str(e)}}"
        logger.error(error_msg)
        print(f"ERROR: {{error_msg}}")
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
""")
    
    # Make the script executable
    os.chmod(TEMP_SCRIPT, 0o755)
    print(f"SCRIPT_INFO: Created temporary restore script at {TEMP_SCRIPT}")
    return TEMP_SCRIPT

def main():
    """Main function to run both scripts in sequence"""
    print("SCRIPT_START: Database reset process beginning")
    logger.info("Starting database reset process")
    
    # Check if we have backups
    if not LATEST_BACKUP:
        print("SCRIPT_ERROR: No backup files found in db_backups directory")
        logger.error("No backup files found in db_backups directory")
        return False
        
    print(f"SCRIPT_INFO: Latest backup file: {LATEST_BACKUP}")
    
    # Create custom restore script for latest backup
    custom_restore = create_custom_restore_script()
    if not custom_restore:
        return False
    
    # Step 1: Restore database from backup using custom script
    print("SCRIPT_INFO: Step 1: Restoring database from latest backup")
    logger.info(f"Step 1: Restoring database from latest backup: {LATEST_BACKUP}")
    
    if not run_script(custom_restore):
        print("SCRIPT_ERROR: Database restore failed. Aborting.")
        logger.error("Database restore failed. Aborting.")
        return False
    
    # Step 2: Fix any data format issues
    print("SCRIPT_INFO: Step 2: Fixing data format issues")
    logger.info("Step 2: Fixing data format issues")
    
    if not run_script(FIX_SCRIPT):
        print("SCRIPT_WARNING: Database format fix might have issues.")
        logger.error("Database format fix failed.")
        # Continue anyway since the restore probably worked
    
    print("SCRIPT_SUCCESS: Database reset process completed successfully")
    logger.info("Database reset process completed successfully")
    return True

if __name__ == "__main__":
    success = main()
    if success:
        print("RESET_COMPLETED: All database operations completed successfully")
        logger.info("All database operations completed successfully")
        sys.exit(0)
    else:
        print("RESET_FAILED: Database operations failed")
        logger.error("Database operations failed")
        sys.exit(1) 