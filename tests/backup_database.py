#!/usr/bin/env python3
"""
Script to backup the MongoDB database to a JSON file.
This script is called by the API endpoint and simply delegates to the actual implementation.
"""
import os
import sys
import logging
import argparse
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import the actual implementation
from src.utils.database import backup_database

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """
    Main function to backup the database.
    """
    parser = argparse.ArgumentParser(description='Backup MongoDB database to a JSON file')
    parser.add_argument('--file', type=str, help='Path to the backup file (optional)')
    args = parser.parse_args()
    
    try:
        backup_file = backup_database(args.file)
        logger.info(f"Database backup completed successfully: {backup_file}")
        return 0
    except Exception as e:
        logger.error(f"Error backing up database: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 