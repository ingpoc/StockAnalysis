"""
Script to examine the database structure and show a sample document.
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
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

async def examine_database():
    """
    Examine the database structure and show a sample document.
    """
    # Set up MongoDB connection
    mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(mongo_uri)
    db = client.stock_data  # Updated database name
    collection = db.detailed_financials  # Updated collection name
    
    try:
        # Get a sample document
        sample_doc = await collection.find_one()
        if sample_doc:
            logger.info("Sample document structure:")
            logger.info(f"Company Name: {sample_doc.get('company_name')}")
            logger.info(f"Symbol: {sample_doc.get('symbol')}")
            
            # Check financial_metrics structure
            financial_metrics = sample_doc.get('financial_metrics', [])
            if isinstance(financial_metrics, list):
                logger.info(f"Number of financial metrics entries: {len(financial_metrics)}")
                
                # Show quarters in the document
                quarters = [metric.get('quarter') for metric in financial_metrics if metric.get('quarter')]
                logger.info(f"Quarters in this document: {quarters}")
                
                # Show first financial metric entry
                if financial_metrics:
                    logger.info("First financial metric entry:")
                    for key, value in financial_metrics[0].items():
                        logger.info(f"  {key}: {value}")
            else:
                logger.info(f"Financial metrics structure: {type(financial_metrics)}")
                logger.info(f"Financial metrics content: {financial_metrics}")
        else:
            logger.warning("No documents found in the collection.")
            
        # Count total documents
        count = await collection.count_documents({})
        logger.info(f"Total documents in collection: {count}")
        
        # Count documents with Q3 data
        q3_count = await collection.count_documents({"financial_metrics.quarter": {"$regex": "Q3"}})
        logger.info(f"Documents with Q3 data: {q3_count}")
        
        # Count total Q3 entries across all documents
        pipeline = [
            {"$unwind": "$financial_metrics"},
            {"$match": {"financial_metrics.quarter": {"$regex": "Q3"}}},
            {"$count": "q3_entries"}
        ]
        result = await collection.aggregate(pipeline).to_list(length=1)
        if result:
            logger.info(f"Total Q3 entries across all documents: {result[0].get('q3_entries')}")
        else:
            logger.info("No Q3 entries found")
        
    except Exception as e:
        logger.error(f"Error examining database: {str(e)}")
    finally:
        # Close MongoDB connection
        client.close()
        logger.info("MongoDB connection closed")

if __name__ == "__main__":
    asyncio.run(examine_database()) 