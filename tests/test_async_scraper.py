"""
Test script for the MoneyControl scraper with async MongoDB operations.
"""
import asyncio
import logging
import os
import sys
import traceback
from datetime import datetime
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scraper.scraper_login import setup_webdriver, login_to_moneycontrol
from src.scraper.moneycontrol_scraper import (
    scrape_moneycontrol_earnings,
    scrape_earnings_list
)

# Configure logging
log_file = os.path.join(os.path.dirname(__file__), "async_scraper_test.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file)
    ]
)

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Constants
MONGO_URL = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONEYCONTROL_USERNAME = os.getenv("MONEYCONTROL_USERNAME")
MONEYCONTROL_PASSWORD = os.getenv("MONEYCONTROL_PASSWORD")
EARNINGS_URL = "https://www.moneycontrol.com/markets/earnings/latest-results/?tab=LR&subType=yoy"
MOTHERSON_URL = "https://www.moneycontrol.com/india/stockpricequote/auto-ancillaries/motherson/MS24"

async def test_async_scraper():
    """
    Test the MoneyControl scraper with async MongoDB operations.
    """
    # Set up MongoDB connection - for verification only, not for saving data
    mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(mongo_uri)
    db = client.stock_data
    collection = db.detailed_financials
    
    # URL for latest results
    url = "https://www.moneycontrol.com/markets/earnings/latest-results/?tab=LR&subType=yoy"
    logger.info(f"Testing async scraper with URL: {url}")
    
    try:
        # Run the scraper without passing the MongoDB collection to avoid saving data
        logger.info("Running scraper in test mode - NOT saving to database")
        results = await scrape_moneycontrol_earnings(url, None)
        logger.info(f"Scraping completed. Found {len(results)} results.")
        
        # Print the first result for verification
        if results:
            logger.info(f"First result: {results[0]['company_name']}")
            logger.info(f"Financial metrics: {results[0]['financial_metrics']}")
        else:
            logger.warning("No results found.")
            
        # Verify data in MongoDB (this just checks existing data, no new data was added)
        count = await collection.count_documents({})
        logger.info(f"Total documents in collection (unchanged): {count}")
        
    except Exception as e:
        logger.error(f"Error during async scraping test: {str(e)}")
    finally:
        # Close MongoDB connection
        if client:
            client.close()
        logger.info("MongoDB connection closed")

async def test_earnings_list_scraper():
    """Test the earnings list scraper functionality."""
    logger.info(f"Testing earnings list scraper with URL: {EARNINGS_URL}")
    
    # Initialize variables
    driver = None
    db_client = None
    
    try:
        # Set up DB connection - for verification only, not for saving data
        logger.info("Setting up MongoDB connection (for verification only)")
        db_client = AsyncIOMotorClient(MONGO_URL)
        db = db_client.get_database("stock_analysis")
        companies_collection = db.get_collection("companies")
        
        logger.info("Setting up WebDriver")
        driver = setup_webdriver()
        
        # Check if credentials are available
        if not MONEYCONTROL_USERNAME or not MONEYCONTROL_PASSWORD:
            logger.error("MoneyControl credentials not found in environment variables.")
            assert False, "Missing MoneyControl credentials"
            
        # Log in to MoneyControl
        login_success = login_to_moneycontrol(driver, MONEYCONTROL_USERNAME, MONEYCONTROL_PASSWORD, target_url=EARNINGS_URL)
        if not login_success:
            logger.error("Failed to login to MoneyControl.")
            assert False, "Failed to login to MoneyControl"
        
        # Run the earnings list scraper with a limit of 1 company
        # Pass None instead of companies_collection to avoid saving to the database
        logger.info("Running earnings list scraper with max_companies=1 (not saving to database)")
        companies = await scrape_earnings_list(driver, EARNINGS_URL, None, max_companies=1)
        
        # Log and validate the results
        if companies and len(companies) > 0:
            logger.info(f"Successfully scraped {len(companies)} company from earnings list")
            company = companies[0]
            logger.info(f"Company name: {company['name']}")
            logger.info(f"Symbol: {company['symbol']}")
            logger.info(f"Financial metrics: {company['financial_data']}")
            
            # Check if we have essential data
            assert company['name'] is not None and company['name'] != "Unknown Company", "Failed to extract company name"
            assert company['symbol'] is not None, "Failed to extract company symbol"
            assert company['financial_data'] is not None, "Failed to extract financial data"
            
            # Check for specific financial metrics
            metrics = company['financial_data']
            assert 'quarter' in metrics, "Quarter information missing"
            if 'market_cap' in metrics:
                assert metrics['market_cap'] is not None, "Market cap missing"
            
            # Log total documents in collection (for verification only, no data was added)
            count = await companies_collection.count_documents({})
            logger.info(f"Total documents in collection (unchanged): {count}")
        else:
            logger.error("Failed to scrape any companies from earnings list")
            assert False, "No companies scraped"
        
    except Exception as e:
        logger.error(f"Error in test_earnings_list_scraper: {str(e)}")
        traceback.print_exc()
        assert False, f"Test failed with error: {str(e)}"
    finally:
        # Close the driver and DB connection
        if driver:
            driver.quit()
        if db_client:
            try:
                await db_client.close()
            except Exception as e:
                logger.warning(f"Error closing DB connection: {e}")
        logger.info("Test resources cleaned up")

if __name__ == "__main__":
    # Run the test
    asyncio.run(test_earnings_list_scraper()) 