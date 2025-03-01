"""
Script to list all collections in the database.
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

async def list_collections():
    """
    List all collections in the database.
    """
    # Set up MongoDB connection
    mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(mongo_uri)
    db = client.stock_analysis
    
    try:
        # List all collections
        collections = await db.list_collection_names()
        logger.info(f"Collections in database: {collections}")
        
        # Check each collection for documents
        for collection_name in collections:
            collection = db[collection_name]
            count = await collection.count_documents({})
            logger.info(f"Collection '{collection_name}' has {count} documents")
            
            # Get a sample document from each collection
            if count > 0:
                sample_doc = await collection.find_one()
                logger.info(f"Sample document from '{collection_name}':")
                logger.info(f"Keys: {list(sample_doc.keys())}")
                
                # Check if it has financial_metrics
                if 'financial_metrics' in sample_doc:
                    financial_metrics = sample_doc['financial_metrics']
                    if isinstance(financial_metrics, list):
                        logger.info(f"Number of financial metrics entries: {len(financial_metrics)}")
                        
                        # Show quarters in the document
                        quarters = [metric.get('quarter') for metric in financial_metrics if metric.get('quarter')]
                        logger.info(f"Quarters in this document: {quarters}")
                    else:
                        logger.info(f"Financial metrics is not a list: {type(financial_metrics)}")
        
    except Exception as e:
        logger.error(f"Error listing collections: {str(e)}")
    finally:
        # Close MongoDB connection
        client.close()
        logger.info("MongoDB connection closed")

if __name__ == "__main__":
    asyncio.run(list_collections()) 