#!/usr/bin/env python3
"""
Script to fix missing symbols in the database.
Run this script from the project root with:
python -m src.utils.database.fix_missing_symbols
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

async def fix_missing_symbols():
    """Fix missing symbols in the database"""
    logger.info("Connecting to MongoDB database...")
    db = await get_database()
    
    # Get the collection with stock data
    collection = db.detailed_financials
    
    # Define the companies and their symbols to fix
    fixes = [
        {"company_name": "Dr Agarwals", "symbol": "DRAGARWAL"}
    ]
    
    for fix in fixes:
        company_name = fix["company_name"]
        new_symbol = fix["symbol"]
        
        # Find the document by company name
        doc = await collection.find_one({"company_name": company_name})
        
        if not doc:
            logger.warning(f"Company not found: {company_name}")
            continue
        
        # Update the document with the new symbol
        result = await collection.update_one(
            {"company_name": company_name},
            {"$set": {"symbol": new_symbol}}
        )
        
        if result.modified_count > 0:
            logger.info(f"Updated symbol for {company_name} to {new_symbol}")
        else:
            logger.warning(f"Failed to update symbol for {company_name}")
    
    # Verify the fixes
    for fix in fixes:
        company_name = fix["company_name"]
        doc = await collection.find_one({"company_name": company_name})
        
        if doc and doc.get("symbol") == fix["symbol"]:
            logger.info(f"Verification successful for {company_name}: symbol is now {doc.get('symbol')}")
        else:
            logger.warning(f"Verification failed for {company_name}")

if __name__ == "__main__":
    try:
        asyncio.run(fix_missing_symbols())
        logger.info("Script completed successfully")
    except Exception as e:
        logger.error(f"Error running script: {str(e)}")
        sys.exit(1) 