#!/usr/bin/env python3
"""
Script to delete specific stock data from the database.
Run this script from the project root with:
python -m src.utils.database.delete_stock
"""

import asyncio
import sys
import os
from pathlib import Path
import logging

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.utils.database import get_database
from src.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

async def delete_stock(company_name=None, symbol=None):
    """Delete a stock entry from the database by company name or symbol"""
    if not company_name and not symbol:
        logger.error("Either company_name or symbol must be provided")
        return False
        
    logger.info("Connecting to MongoDB database...")
    db = await get_database()
    
    # Get the collection with stock data
    collection = db.detailed_financials
    
    # Build the query
    query = {}
    if company_name:
        query["company_name"] = company_name
    if symbol:
        query["symbol"] = symbol
        
    # First find the document to confirm it exists
    doc = await collection.find_one(query)
    
    if not doc:
        logger.warning(f"Stock not found with query: {query}")
        return False
        
    logger.info(f"Found stock to delete: {doc.get('company_name')} (Symbol: {doc.get('symbol')})")
    
    # Ask for confirmation
    if not os.environ.get("SKIP_CONFIRMATION"):
        confirm = input(f"Are you sure you want to delete {doc.get('company_name')}? (y/N): ")
        if confirm.lower() != 'y':
            logger.info("Deletion cancelled")
            return False
    
    # Delete the document
    result = await collection.delete_one(query)
    
    if result.deleted_count > 0:
        logger.info(f"Successfully deleted stock: {doc.get('company_name')}")
        return True
    else:
        logger.warning(f"Failed to delete stock: {doc.get('company_name')}")
        return False

if __name__ == "__main__":
    # Get company name from command line args if provided
    company_name = None
    symbol = None
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg.startswith("--company="):
                company_name = arg.split("=")[1].strip()
            elif arg.startswith("--symbol="):
                symbol = arg.split("=")[1].strip()
    
    # Use defaults if not provided in command line
    if not company_name and not symbol:
        company_name = "Dr Agarwals"  # Default to Dr Agarwals
    
    try:
        success = asyncio.run(delete_stock(company_name, symbol))
        if success:
            logger.info("Stock deletion completed successfully")
        else:
            logger.warning("Stock deletion failed or was cancelled")
    except Exception as e:
        logger.error(f"Error running script: {str(e)}")
        sys.exit(1) 