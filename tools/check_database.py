#!/usr/bin/env python3
"""
Script to check the database structure and verify the restoration was successful.
"""
import os
import sys
import logging
from pymongo import MongoClient
from dotenv import load_dotenv

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

def check_database():
    """Check the database structure and content"""
    try:
        # Print marker for script start (helps with debugging)
        print("SCRIPT_START: Database check beginning")
        
        # Connect to MongoDB
        logger.info(f"Connecting to MongoDB at {MONGO_URI}")
        print(f"INFO: Connecting to MongoDB at {MONGO_URI}")
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        
        # Check if the collection exists
        if "detailed_financials" not in db.list_collection_names():
            error_msg = "detailed_financials collection does not exist"
            logger.error(error_msg)
            print(f"ERROR: {error_msg}")
            print("SCRIPT_FAILURE: Database check failed - collection not found")
            return False
        
        # Get document count
        doc_count = db.detailed_financials.count_documents({})
        logger.info(f"Found {doc_count} documents in detailed_financials collection")
        print(f"INFO: Found {doc_count} documents in detailed_financials collection")
        
        # Count documents with different structures
        correct_format_count = db.detailed_financials.count_documents({"financial_metrics": {"$exists": True, "$type": "array"}})
        old_format_count = db.detailed_financials.count_documents({"financial_data": {"$exists": True}})
        
        logger.info(f"Documents with correct format (financial_metrics array): {correct_format_count}")
        logger.info(f"Documents with old format (financial_data field): {old_format_count}")
        print(f"INFO: Documents with correct format (financial_metrics array): {correct_format_count}")
        print(f"INFO: Documents with old format (financial_data field): {old_format_count}")
        
        # Check if we have proper quarter data
        quarters_pipeline = [
            {"$unwind": "$financial_metrics"},
            {"$group": {"_id": "$financial_metrics.quarter"}},
            {"$match": {"_id": {"$ne": None}}},
            {"$sort": {"_id": -1}}
        ]
        
        quarters = list(db.detailed_financials.aggregate(quarters_pipeline))
        if quarters:
            logger.info(f"Found {len(quarters)} unique quarters in the database:")
            print(f"INFO: Found {len(quarters)} unique quarters in the database:")
            for q in quarters[:10]:  # Show the first 10 quarters
                logger.info(f"  - {q['_id']}")
                print(f"INFO:   - {q['_id']}")
            if len(quarters) > 10:
                logger.info(f"  ... and {len(quarters) - 10} more")
                print(f"INFO:   ... and {len(quarters) - 10} more")
        else:
            logger.warning("No quarters found in the database")
            print("WARNING: No quarters found in the database")
        
        # Check a sample document structure
        sample = db.detailed_financials.find_one({})
        if sample:
            logger.info("Sample document structure:")
            print("INFO: Sample document structure found")
            
            # Add explicit success marker
            print("SCRIPT_SUCCESS: Database check completed successfully")
            
            # Return success
            return True
        else:
            logger.warning("No documents found in the database")
            print("WARNING: No documents found in the database")
            print("SCRIPT_FAILURE: Database check failed - no documents found")
            return False
    
    except Exception as e:
        error_message = f"Error checking database: {str(e)}"
        logger.error(error_message)
        print(f"ERROR: {error_message}")
        print("SCRIPT_FAILURE: Database check failed with an exception")
        return False
    finally:
        if 'client' in locals():
            client.close()
            logger.info("MongoDB connection closed")
            print("INFO: MongoDB connection closed")

if __name__ == "__main__":
    success = check_database()
    if success:
        print("CHECK_COMPLETED: Database check completed successfully")
        sys.exit(0)
    else:
        print("CHECK_FAILED: Database check failed")
        sys.exit(1) 