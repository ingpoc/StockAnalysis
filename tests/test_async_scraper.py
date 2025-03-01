"""
Test script for the MoneyControl scraper with async MongoDB operations.
"""
import asyncio
import logging
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

from src.scraper.moneycontrol_scraper import scrape_moneycontrol_earnings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("async_scraper_test.log")
    ]
)

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

async def test_async_scraper():
    """
    Test the MoneyControl scraper with async MongoDB operations.
    """
    # Set up MongoDB connection
    mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(mongo_uri)
    db = client.stock_data
    collection = db.detailed_financials
    
    # URL for latest results
    url = "https://www.moneycontrol.com/markets/earnings/latest-results/?tab=LR&subType=yoy"
    logger.info(f"Testing async scraper with URL: {url}")
    
    try:
        # Run the scraper with the MongoDB collection
        results = await scrape_moneycontrol_earnings(url, collection)
        logger.info(f"Scraping completed. Found {len(results)} results.")
        
        # Print the first result for verification
        if results:
            logger.info(f"First result: {results[0]['company_name']}")
            logger.info(f"Financial metrics: {results[0]['financial_metrics']}")
        else:
            logger.warning("No results found.")
            
        # Verify data in MongoDB
        count = await collection.count_documents({})
        logger.info(f"Total documents in collection: {count}")
        
    except Exception as e:
        logger.error(f"Error during async scraping test: {str(e)}")
    finally:
        # Close MongoDB connection
        client.close()
        logger.info("MongoDB connection closed")

if __name__ == "__main__":
    asyncio.run(test_async_scraper()) 