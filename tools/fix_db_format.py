#!/usr/bin/env python3
"""
Script to check and fix any data format inconsistencies in the database.
This will ensure all documents follow the expected structure required by the application.
"""
import os
import sys
import logging
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv
import asyncio
from typing import Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.database import get_database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = "stock_data"

# Fields that should be stored as strings
STRING_FIELDS = [
    'revenue', 'revenue_growth', 'gross_profit', 'gross_profit_growth',
    'net_profit', 'net_profit_growth', 'market_cap', 'face_value',
    'book_value', 'dividend_yield', 'ttm_eps', 'ttm_pe', 'pb_ratio',
    'sector_pe', 'piotroski_score'
]

async def fix_numeric_values():
    """Fix numeric values in financial_metrics to ensure they are all stored as strings."""
    db = await get_database()
    collection = db.detailed_financials
    
    # Find all documents
    cursor = collection.find({})
    count = 0
    fixed_count = 0
    
    async for doc in cursor:
        count += 1
        doc_updated = False
        
        if "financial_metrics" in doc and isinstance(doc["financial_metrics"], list):
            for i, metrics in enumerate(doc["financial_metrics"]):
                metrics_updated = False
                
                # Check each field that should be a string
                for field in STRING_FIELDS:
                    if field in metrics and isinstance(metrics[field], (int, float)):
                        # Convert to string
                        doc["financial_metrics"][i][field] = str(metrics[field])
                        metrics_updated = True
                        logger.info(f"Converting {field} from {type(metrics[field])} to string for {doc['company_name']}")
                
                if metrics_updated:
                    doc_updated = True
            
            if doc_updated:
                # Update the document
                await collection.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"financial_metrics": doc["financial_metrics"]}}
                )
                fixed_count += 1
    
    logger.info(f"Processed {count} documents, fixed {fixed_count} documents with numeric values")

async def fix_db_format():
    """Fix the database format to ensure all documents have financial_metrics as an array."""
    db = await get_database()
    collection = db.detailed_financials
    
    # Stats
    stats = {
        "total": 0,
        "correct_format": 0,  # Has financial_metrics as array
        "old_format": 0,      # Has financial_data but no financial_metrics
        "fixed": 0            # Documents that were fixed
    }
    
    # Process all documents
    cursor = collection.find({})
    async for doc in cursor:
        stats["total"] += 1
        
        # Check if document has financial_metrics as array
        if "financial_metrics" in doc and isinstance(doc["financial_metrics"], list):
            stats["correct_format"] += 1
            continue
        
        # Check if document has financial_data but no financial_metrics
        if "financial_data" in doc and not "financial_metrics" in doc:
            stats["old_format"] += 1
            
            # Create financial_metrics array with the financial_data
            financial_metrics = [doc["financial_data"]]
            
            # Update the document
            await collection.update_one(
                {"_id": doc["_id"]},
                {
                    "$set": {
                        "financial_metrics": financial_metrics,
                        "timestamp": doc.get("timestamp", datetime.now())
                    },
                    "$unset": {"financial_data": ""}
                }
            )
            
            stats["fixed"] += 1
    
    logger.info(f"Database format fix stats: {stats}")

async def main():
    """Main function to run the database fixes."""
    logger.info("Starting database format fix...")
    
    # Fix database format
    await fix_db_format()
    
    # Fix numeric values
    await fix_numeric_values()
    
    logger.info("Database format fix completed.")

if __name__ == "__main__":
    asyncio.run(main()) 