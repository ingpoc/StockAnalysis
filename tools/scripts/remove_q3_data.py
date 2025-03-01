"""
Script to remove Q3 data from the financial_metrics array while preserving other quarters.
"""
import asyncio
import os
import logging
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("remove_q3_data.log")
    ]
)

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

async def remove_q3_data():
    """
    Remove Q3 data from the financial_metrics array while preserving other quarters.
    """
    # Set up MongoDB connection
    mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(mongo_uri)
    db = client.stock_data
    collection = db.detailed_financials
    
    try:
        # Count documents with Q3 data before removal
        q3_count_before = await collection.count_documents({"financial_metrics.quarter": {"$regex": "Q3"}})
        logger.info(f"Documents with Q3 data before removal: {q3_count_before}")
        
        # Count total Q3 entries across all documents before removal
        pipeline_before = [
            {"$unwind": "$financial_metrics"},
            {"$match": {"financial_metrics.quarter": {"$regex": "Q3"}}},
            {"$count": "q3_entries"}
        ]
        result_before = await collection.aggregate(pipeline_before).to_list(length=1)
        if result_before:
            logger.info(f"Total Q3 entries before removal: {result_before[0].get('q3_entries')}")
        
        # Get all documents with Q3 data
        documents_with_q3 = await collection.find(
            {"financial_metrics.quarter": {"$regex": "Q3"}}
        ).to_list(length=None)
        
        logger.info(f"Found {len(documents_with_q3)} documents with Q3 data")
        
        # Process each document
        update_count = 0
        for doc in documents_with_q3:
            company_name = doc.get('company_name')
            
            # Filter out Q3 entries
            original_metrics_count = len(doc.get('financial_metrics', []))
            filtered_metrics = [
                metric for metric in doc.get('financial_metrics', [])
                if not (metric.get('quarter') and 'Q3' in metric.get('quarter'))
            ]
            removed_count = original_metrics_count - len(filtered_metrics)
            
            # Update the document
            if removed_count > 0:
                result = await collection.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"financial_metrics": filtered_metrics}}
                )
                
                if result.modified_count > 0:
                    update_count += 1
                    logger.info(f"Removed {removed_count} Q3 entries from {company_name}")
                else:
                    logger.warning(f"Failed to update document for {company_name}")
        
        logger.info(f"Successfully updated {update_count} documents")
        
        # Count documents with Q3 data after removal
        q3_count_after = await collection.count_documents({"financial_metrics.quarter": {"$regex": "Q3"}})
        logger.info(f"Documents with Q3 data after removal: {q3_count_after}")
        
        # Verify all Q3 data has been removed
        pipeline_after = [
            {"$unwind": "$financial_metrics"},
            {"$match": {"financial_metrics.quarter": {"$regex": "Q3"}}},
            {"$count": "q3_entries"}
        ]
        result_after = await collection.aggregate(pipeline_after).to_list(length=1)
        if result_after:
            logger.warning(f"There are still {result_after[0].get('q3_entries')} Q3 entries remaining")
        else:
            logger.info("All Q3 entries have been successfully removed")
        
    except Exception as e:
        logger.error(f"Error removing Q3 data: {str(e)}")
    finally:
        # Close MongoDB connection
        client.close()
        logger.info("MongoDB connection closed")

if __name__ == "__main__":
    asyncio.run(remove_q3_data()) 