#!/usr/bin/env python3
"""
Script to fix database format issues.
This script performs various data format corrections on the stock_data database.
"""
import os
import sys
import logging
from pymongo import MongoClient
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import database utilities
from src.utils.database.validate_database import validate_collection_schema

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = "stock_data"

def fix_database_format():
    """Fix any format issues in the database"""
    try:
        print("SCRIPT_START: Database format fix beginning")
        
        # Connect to MongoDB
        logger.info(f"Connecting to MongoDB at {MONGO_URI}")
        print(f"INFO: Connecting to MongoDB at {MONGO_URI}")
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        
        # Check if the collection exists
        if "detailed_financials" not in db.list_collection_names():
            error_msg = "detailed_financials collection not found"
            logger.error(error_msg)
            print(f"ERROR: {error_msg}")
            print("SCRIPT_FAILURE: Database format fix failed - collection not found")
            return False
        
        # Count documents
        count = db.detailed_financials.count_documents({})
        logger.info(f"Found {count} documents in detailed_financials collection")
        print(f"INFO: Found {count} documents in detailed_financials collection")
        
        # Validate the collection schema
        print("INFO: Validating collection schema...")
        validation_result = validate_collection_schema(db, "detailed_financials")
        
        if not validation_result['valid']:
            print(f"WARNING: Schema validation found issues: {validation_result['errors']}")
            logger.warning(f"Schema validation found issues: {validation_result['errors']}")
        
        # Fix common format issues
        print("INFO: Fixing common format issues...")
        
        # 1. Fix missing fields by adding default values
        print("INFO: Fixing missing fields...")
        fix_missing_fields(db)
        
        # 2. Fix data type issues
        print("INFO: Fixing data type issues...")
        fix_data_types(db)
        
        # 3. Fix inconsistent date formats
        print("INFO: Fixing date formats...")
        fix_date_formats(db)
        
        # Final validation
        print("INFO: Performing final validation...")
        final_validation = validate_collection_schema(db, "detailed_financials")
        
        if final_validation['valid']:
            print("INFO: Final validation passed - all issues fixed")
            logger.info("Final validation passed - all issues fixed")
        else:
            print(f"WARNING: Some issues could not be fixed: {final_validation['errors']}")
            logger.warning(f"Some issues could not be fixed: {final_validation['errors']}")
        
        print("SCRIPT_SUCCESS: Database format fix completed")
        logger.info("Database format fix completed")
        return True
        
    except Exception as e:
        error_msg = f"Error fixing database format: {str(e)}"
        logger.error(error_msg)
        print(f"ERROR: {error_msg}")
        print("SCRIPT_FAILURE: Database format fix failed with an exception")
        return False
    finally:
        if 'client' in locals():
            client.close()
            logger.info("MongoDB connection closed")
            print("INFO: MongoDB connection closed")

def fix_missing_fields(db):
    """Add default values for missing fields"""
    try:
        # Example: Add missing 'last_updated' field
        result = db.detailed_financials.update_many(
            {"last_updated": {"$exists": False}},
            {"$set": {"last_updated": None}}
        )
        print(f"INFO: Added missing 'last_updated' field to {result.modified_count} documents")
        
        # Example: Add missing 'data_source' field
        result = db.detailed_financials.update_many(
            {"data_source": {"$exists": False}},
            {"$set": {"data_source": "manual"}}
        )
        print(f"INFO: Added missing 'data_source' field to {result.modified_count} documents")
        
        # Example: Add missing 'metrics' object if not present
        result = db.detailed_financials.update_many(
            {"metrics": {"$exists": False}},
            {"$set": {"metrics": {}}}
        )
        print(f"INFO: Added missing 'metrics' object to {result.modified_count} documents")
        
        return True
    except Exception as e:
        print(f"ERROR: Failed to fix missing fields: {str(e)}")
        logger.error(f"Failed to fix missing fields: {str(e)}")
        return False

def fix_data_types(db):
    """Fix data type issues in the database"""
    try:
        # Example: Convert string numbers to actual numbers
        pipeline = [
            {"$match": {"market_cap": {"$type": "string"}}},
            {"$addFields": {
                "market_cap": {"$toDouble": "$market_cap"}
            }},
            {"$merge": {
                "into": "detailed_financials",
                "whenMatched": "merge",
                "whenNotMatched": "discard"
            }}
        ]
        db.detailed_financials.aggregate(pipeline)
        print("INFO: Converted string market_cap values to numbers")
        
        # Example: Convert string percentages to numbers
        pipeline = [
            {"$match": {"metrics.pe_ratio": {"$type": "string"}}},
            {"$addFields": {
                "metrics.pe_ratio": {"$toDouble": "$metrics.pe_ratio"}
            }},
            {"$merge": {
                "into": "detailed_financials",
                "whenMatched": "merge",
                "whenNotMatched": "discard"
            }}
        ]
        db.detailed_financials.aggregate(pipeline)
        print("INFO: Converted string PE ratio values to numbers")
        
        return True
    except Exception as e:
        print(f"ERROR: Failed to fix data types: {str(e)}")
        logger.error(f"Failed to fix data types: {str(e)}")
        return False

def fix_date_formats(db):
    """Fix inconsistent date formats in the database"""
    try:
        # Example: Convert string dates to ISODate
        pipeline = [
            {"$match": {"report_date": {"$type": "string"}}},
            {"$addFields": {
                "report_date": {"$dateFromString": {
                    "dateString": "$report_date",
                    "onError": "$report_date"  # Keep original on error
                }}
            }},
            {"$merge": {
                "into": "detailed_financials",
                "whenMatched": "merge",
                "whenNotMatched": "discard"
            }}
        ]
        db.detailed_financials.aggregate(pipeline)
        print("INFO: Converted string dates to proper date objects")
        
        return True
    except Exception as e:
        print(f"ERROR: Failed to fix date formats: {str(e)}")
        logger.error(f"Failed to fix date formats: {str(e)}")
        return False

if __name__ == "__main__":
    success = fix_database_format()
    if success:
        print("SCRIPT_SUCCESS: Database format fix completed successfully")
        sys.exit(0)
    else:
        print("SCRIPT_FAILURE: Database format fix failed")
        sys.exit(1) 