#!/usr/bin/env python3
"""
Script to check for entries with Q3 data and identify those missing symbols.
Run this script from the project root with:
python -m src.utils.database.check_q3_data
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

async def check_q3_data():
    """Check for entries with Q3 data and missing symbols"""
    logger.info("Connecting to MongoDB database...")
    db = await get_database()
    
    # Get the collection with stock data
    collection = db.detailed_financials
    
    # First, count all documents in the collection
    total_docs = await collection.count_documents({})
    logger.info(f"Total documents in collection: {total_docs}")
    
    # Count documents with Q3 data (in any of their financial_metrics)
    q3_pipeline = [
        {
            "$match": {
                "financial_metrics": {
                    "$elemMatch": {
                        "quarter": {"$regex": "Q3", "$options": "i"}
                    }
                }
            }
        },
        {"$count": "q3_count"}
    ]
    
    q3_result = await collection.aggregate(q3_pipeline).to_list(length=1)
    q3_count = q3_result[0]["q3_count"] if q3_result else 0
    logger.info(f"Documents with Q3 data: {q3_count}")
    
    # Find documents with Q3 data but missing or empty symbol
    missing_symbol_pipeline = [
        {
            "$match": {
                "$and": [
                    {
                        "financial_metrics": {
                            "$elemMatch": {
                                "quarter": {"$regex": "Q3", "$options": "i"}
                            }
                        }
                    },
                    {
                        "$or": [
                            {"symbol": {"$exists": False}},
                            {"symbol": None},
                            {"symbol": ""}
                        ]
                    }
                ]
            }
        },
        {
            "$project": {
                "_id": 1,
                "company_name": 1,
                "symbol": 1
            }
        }
    ]
    
    missing_symbol_docs = await collection.aggregate(missing_symbol_pipeline).to_list(length=None)
    logger.info(f"Documents with Q3 data but missing symbol: {len(missing_symbol_docs)}")
    
    # Print the company names with missing symbols
    if missing_symbol_docs:
        logger.info("Companies with missing symbols:")
        for doc in missing_symbol_docs:
            logger.info(f"Company: {doc.get('company_name', 'Unknown')}, Symbol: {doc.get('symbol', 'None')}")
    
    return {
        "total_docs": total_docs,
        "q3_count": q3_count,
        "missing_symbols": len(missing_symbol_docs),
        "missing_symbol_docs": missing_symbol_docs
    }

if __name__ == "__main__":
    try:
        results = asyncio.run(check_q3_data())
        logger.info("Script completed successfully")
    except Exception as e:
        logger.error(f"Error running script: {str(e)}")
        sys.exit(1) 