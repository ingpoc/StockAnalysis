#!/usr/bin/env python3
"""
Master script to restore the database from backup and fix any data format issues.
"""
import os
import sys
import logging
import subprocess
import asyncio
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import the database utilities
from src.utils.database import restore_database, get_latest_backup

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get the path to the fix_db_format script
TOOLS_DIR = Path(__file__).parent.absolute()
FIX_SCRIPT = TOOLS_DIR / "fix_db_format.py"

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
        print(result.stdout)
        
        if result.stderr:
            print(f"SCRIPT_WARNING: Script produced stderr output: {result.stderr}")
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"SCRIPT_ERROR: Script failed with exit code {e.returncode}")
        print(f"SCRIPT_ERROR: stdout: {e.stdout}")
        print(f"SCRIPT_ERROR: stderr: {e.stderr}")
        return False
    except Exception as e:
        print(f"SCRIPT_ERROR: Failed to run script: {str(e)}")
        return False

async def reset_database(backup_file=None):
    """
    Reset the database by restoring from backup and fixing data format issues.
    
    Args:
        backup_file (str, optional): Path to the backup file. If not provided, the latest backup will be used.
        
    Returns:
        bool: True if reset was successful, False otherwise.
    """
    print("SCRIPT_START: Database reset beginning")
    logger.info("Starting database reset process")
    
    # Step 1: Restore the database from backup
    print("SCRIPT_INFO: Step 1 - Restoring database from backup")
    logger.info("Step 1: Restoring database from backup")
    
    # Use the latest backup if not specified
    if not backup_file:
        backup_file = get_latest_backup()
        if not backup_file:
            error_msg = "No backup files found"
            print(f"SCRIPT_ERROR: {error_msg}")
            logger.error(error_msg)
            return False
    
    # Restore the database
    restore_success = restore_database(backup_file)
    
    if not restore_success:
        error_msg = "Database restore failed"
        print(f"SCRIPT_ERROR: {error_msg}")
        logger.error(error_msg)
        return False
    
    print("SCRIPT_INFO: Database restore completed successfully")
    logger.info("Database restore completed successfully")
    
    # Step 2: Fix database format issues
    print("SCRIPT_INFO: Step 2 - Fixing database format issues")
    logger.info("Step 2: Fixing database format issues")
    
    fix_success = run_script(FIX_SCRIPT)
    
    if not fix_success:
        error_msg = "Database format fix failed"
        print(f"SCRIPT_ERROR: {error_msg}")
        logger.error(error_msg)
        return False
    
    print("SCRIPT_INFO: Database format fix completed successfully")
    logger.info("Database format fix completed successfully")
    
    print("SCRIPT_SUCCESS: Database reset completed successfully")
    logger.info("Database reset completed successfully")
    return True

def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Reset the database from backup")
    parser.add_argument("--backup", help="Path to the backup file (optional)")
    args = parser.parse_args()
    
    success = asyncio.run(reset_database(args.backup))
    
    if success:
        print("Database reset completed successfully")
        sys.exit(0)
    else:
        print("Database reset failed")
        sys.exit(1)

if __name__ == "__main__":
    main() 