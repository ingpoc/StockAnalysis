#!/usr/bin/env python3
"""
Script to verify deletion of a stock entry from the database.
Run this script from the project root with:
python -m src.utils.database.verify_deletion
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

async def verify_deletion(company_name=None, symbol=None):
    """Verify that a stock entry has been deleted from the database"""
    if not company_name and not symbol:
        logger.error("Either company_name or symbol must be provided")
        return
        
    logger.info("Connecting to MongoDB database...")
    db = await get_database()
    
    # Get the collection with stock data
    collection = db.detailed_financials
    
    # Check for company name if provided
    if company_name:
        doc = await collection.find_one({"company_name": company_name})
        if doc:
            logger.warning(f"Entry with company name '{company_name}' still exists in the database")
            logger.info(f"Entry details: Symbol={doc.get('symbol')}, ID={doc.get('_id')}")
        else:
            logger.info(f"No entry found with company name '{company_name}' - confirming deletion")
    
    # Check for symbol if provided
    if symbol:
        doc = await collection.find_one({"symbol": symbol})
        if doc:
            logger.warning(f"Entry with symbol '{symbol}' still exists in the database")
            logger.info(f"Entry details: Company={doc.get('company_name')}, ID={doc.get('_id')}")
        else:
            logger.info(f"No entry found with symbol '{symbol}' - confirming deletion")

if __name__ == "__main__":
    # Default values to check
    company_name = "Dr Agarwals"
    symbol = "DRAGARWAL"
    
    try:
        asyncio.run(verify_deletion(company_name, symbol))
        logger.info("Verification completed")
    except Exception as e:
        logger.error(f"Error running verification: {str(e)}")
        sys.exit(1) 