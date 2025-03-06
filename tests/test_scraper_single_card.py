"""
Test file for scraping a single result card from MoneyControl.
This test focuses on scraping only the first result card (RANA SUGARS),
logging the scraped data, and verifying database storage in the correct format.
"""
import os
import sys
import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Load environment variables
load_dotenv()

# Set MONGODB_CONNECTION_STRING from MONGODB_URI if it doesn't exist
if not os.getenv('MONGODB_CONNECTION_STRING') and os.getenv('MONGODB_URI'):
    os.environ['MONGODB_CONNECTION_STRING'] = os.getenv('MONGODB_URI')
    print(f"Set MONGODB_CONNECTION_STRING to {os.environ['MONGODB_CONNECTION_STRING']}")

# Set MONGODB_DATABASE_NAME from MONGODB_DB_NAME if it doesn't exist
if not os.getenv('MONGODB_DATABASE_NAME') and os.getenv('MONGODB_DB_NAME'):
    os.environ['MONGODB_DATABASE_NAME'] = os.getenv('MONGODB_DB_NAME')
    print(f"Set MONGODB_DATABASE_NAME to {os.environ['MONGODB_DATABASE_NAME']}")

# Set browser to Brave
os.environ['BROWSER'] = 'brave'
print(f"Set BROWSER to {os.environ['BROWSER']}")

# Set headless mode to false
os.environ['HEADLESS'] = 'false'
print(f"Set HEADLESS to {os.environ['HEADLESS']}")

# Import scraper components
from src.scraper import (
    scrape_custom_url,
    get_db_collection,
    get_financial_data_by_company
)
from src.scraper.scrapedata import scrape_moneycontrol_earnings
from src.utils.logger import logger

# Configure logging
# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/scraper_single_card_test.log"),
        logging.StreamHandler()
    ]
)

# Target URL for scraping
TARGET_URL = "https://www.moneycontrol.com/markets/earnings/latest-results/?tab=LR&subType=yoy"

# Expected company name for the first card
EXPECTED_COMPANY = "RANA SUGARS"

# Expected metrics based on the screenshot
EXPECTED_METRICS = {
    "quarter": "Q3 FY24-25",
    "cmp": "14.99 (1.63%)",
    "revenue": "390",
    "gross_profit": "21",
    "net_profit": "14",
    "revenue_growth": "15%",
    "gross_profit_growth": "110%",
    "net_profit_growth": "133%",
    "result_date": "February 28, 2025",
    "report_type": "Standalone"
}

class FirstCardOnlyScraper:
    """
    Custom scraper that only processes the first card.
    This is a wrapper around the actual scraper implementation.
    """
    def __init__(self):
        self.original_scrape_multiple_stocks = None
        self.original_scrape_moneycontrol_earnings = None
        
    def patch_scraper(self):
        """Patch the scraper to only process the first card"""
        # Import the original functions
        from src.scraper.scrapedata import scrape_multiple_stocks as original_multi_func
        from src.scraper.scrapedata import scrape_moneycontrol_earnings as original_earnings_func
        
        self.original_scrape_multiple_stocks = original_multi_func
        self.original_scrape_moneycontrol_earnings = original_earnings_func
        
        # Define the patched function for scrape_multiple_stocks
        async def patched_scrape_multiple_stocks(driver, url, db_collection=None):
            logger.info("Using patched scraper that only processes the first card")
            try:
                # Call the original function
                results = await self.original_scrape_multiple_stocks(driver, url, db_collection)
                
                # Only return the first result
                if results and len(results) > 0:
                    first_result = results[0]
                    logger.info(f"Returning only the first card: {first_result.get('company_name', 'unknown')}")
                    return [first_result]
                return []
            except Exception as e:
                logger.error(f"Error in patched scrape_multiple_stocks: {str(e)}")
                return []
        
        # Define the patched function for scrape_moneycontrol_earnings
        async def patched_scrape_moneycontrol_earnings(url, db_collection=None):
            logger.info("Using patched scraper that only processes the first card")
            try:
                # Call the original function but limit processing to first card
                driver = setup_webdriver()
                
                try:
                    # Login to MoneyControl
                    login_success = login_to_moneycontrol(driver, target_url=url)
                    if not login_success:
                        logger.error("Failed to login to MoneyControl")
                        return []
                    
                    logger.info(f"Opening page: {url}")
                    driver.get(url)
                    
                    # Wait for result cards to load
                    WebDriverWait(driver, 30).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, '#latestRes > div > ul > li:nth-child(1)'))
                    )
                    logger.info("Page opened successfully")
                    
                    # Parse the page content
                    page_source = driver.page_source
                    soup = BeautifulSoup(page_source, 'html.parser')
                    
                    # Get only the first result card
                    result_cards = soup.select('#latestRes > div > ul > li')
                    
                    if not result_cards:
                        logger.error("No result cards found")
                        return []
                    
                    logger.info(f"Found {len(result_cards)} result cards, processing only the first one")
                    
                    # Process only the first card
                    first_card = result_cards[0]
                    company_data = await process_result_card(first_card, driver, db_collection)
                    
                    if company_data:
                        return [company_data]
                    else:
                        return []
                        
                except Exception as e:
                    logger.error(f"Error in patched scrape_moneycontrol_earnings: {str(e)}")
                    return []
                finally:
                    driver.quit()
            except Exception as e:
                logger.error(f"Error in patched scrape_moneycontrol_earnings: {str(e)}")
                return []
        
        # Apply the patches
        import src.scraper.scrapedata
        src.scraper.scrapedata.scrape_multiple_stocks = patched_scrape_multiple_stocks
        src.scraper.scrapedata.scrape_moneycontrol_earnings = patched_scrape_moneycontrol_earnings
        
        # Import necessary components for the patched function
        from src.scraper.browser_setup import setup_webdriver, login_to_moneycontrol
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from bs4 import BeautifulSoup
        from src.scraper.scrapedata import process_result_card
        
    def restore_scraper(self):
        """Restore the original scraper functions"""
        if self.original_scrape_multiple_stocks and self.original_scrape_moneycontrol_earnings:
            import src.scraper.scrapedata
            src.scraper.scrapedata.scrape_multiple_stocks = self.original_scrape_multiple_stocks
            src.scraper.scrapedata.scrape_moneycontrol_earnings = self.original_scrape_moneycontrol_earnings
            logger.info("Restored original scraper functions")

async def test_scrape_single_card():
    """
    Test scraping a single result card from MoneyControl.
    """
    logger.info("=== Starting Single Card Scraping Test ===")
    
    # Create the first-card-only scraper
    first_card_scraper = FirstCardOnlyScraper()
    
    try:
        # Patch the scraper to only process the first card
        first_card_scraper.patch_scraper()
        
        # Get database collection
        collection = await get_db_collection()
        if collection is None:
            logger.error("Failed to get database collection")
            return False
        
        # Scrape the latest results using the actual URL
        logger.info(f"Scraping URL: {TARGET_URL} (first card only)...")
        results = await scrape_moneycontrol_earnings(TARGET_URL, collection)
        
        # Check if we got any results
        if not results or len(results) == 0:
            logger.error("No results scraped")
            return False
        
        # Get the first result (should be RANA SUGARS)
        first_result = results[0]
        
        # Log the scraped data
        logger.info("Scraped data for first card:")
        logger.info(f"Company Name: {first_result.get('company_name', 'N/A')}")
        logger.info(f"Symbol: {first_result.get('symbol', 'N/A')}")
        
        # Log the financial metrics
        financial_metrics = first_result.get('financial_metrics', [])
        if isinstance(financial_metrics, list) and financial_metrics:
            logger.info("Financial Metrics:")
            for key, value in financial_metrics[0].items():
                logger.info(f"  {key}: {value}")
        else:
            logger.warning("Financial metrics not in expected list format")
        
        # Verify the company name
        company_name = first_result.get("company_name", "")
        if EXPECTED_COMPANY not in company_name:
            logger.warning(f"Expected company {EXPECTED_COMPANY}, but got {company_name}")
        
        # Verify data was stored in the database
        logger.info(f"Verifying data for {company_name} in database...")
        db_data = await get_financial_data_by_company(company_name, limit=1, collection=collection)
        
        if not db_data or len(db_data) == 0:
            logger.error(f"No data found in database for {company_name}")
            return False
        
        # Verify the database structure
        logger.info("Verifying database structure...")
        db_validation = validate_db_structure(db_data[0])
        
        if db_validation["valid"]:
            logger.info("Database structure validation passed")
        else:
            logger.error(f"Database structure validation failed: {db_validation['errors']}")
            return False
        
        # Compare with expected metrics from screenshots
        logger.info("Comparing with expected metrics from screenshots...")
        metrics_match = compare_metrics(financial_metrics, EXPECTED_METRICS)
        
        if metrics_match["match"]:
            logger.info("Metrics match expected values from screenshots")
        else:
            logger.warning(f"Metrics mismatch: {metrics_match['mismatches']}")
        
        logger.info("=== Single Card Scraping Test Completed Successfully ===")
        return True
    except Exception as e:
        logger.error(f"Error in test_scrape_single_card: {str(e)}")
        return False
    finally:
        # Restore the original scraper function
        first_card_scraper.restore_scraper()

def validate_db_structure(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate the structure of the data in the database.
    
    Args:
        data (Dict[str, Any]): Data to validate.
        
    Returns:
        Dict[str, Any]: Validation result with "valid" flag and any errors.
    """
    result = {
        "valid": True,
        "errors": []
    }
    
    # Check top-level keys
    required_keys = ["company_name", "symbol", "financial_metrics", "timestamp"]
    for key in required_keys:
        if key not in data:
            result["valid"] = False
            result["errors"].append(f"Missing required key: {key}")
    
    # Check financial_metrics structure
    if "financial_metrics" in data:
        # Check if financial_metrics is a list
        if not isinstance(data["financial_metrics"], list):
            result["valid"] = False
            result["errors"].append("financial_metrics should be a list")
        elif len(data["financial_metrics"]) == 0:
            result["valid"] = False
            result["errors"].append("financial_metrics list is empty")
        else:
            # Check the first financial metrics entry
            metrics = data["financial_metrics"][0]
            required_metrics = ["quarter", "cmp", "revenue", "gross_profit", "net_profit"]
            for metric in required_metrics:
                if metric not in metrics:
                    result["valid"] = False
                    result["errors"].append(f"Missing required metric: {metric}")
    
    # Check data types
    if "company_name" in data and not isinstance(data["company_name"], str):
        result["valid"] = False
        result["errors"].append("company_name must be a string")
    
    if "symbol" in data and not isinstance(data["symbol"], str):
        result["valid"] = False
        result["errors"].append("symbol must be a string")
    
    if "timestamp" in data and not isinstance(data["timestamp"], datetime):
        result["valid"] = False
        result["errors"].append("timestamp must be a datetime object")
    
    return result

def compare_metrics(scraped_metrics: List[Dict[str, Any]], expected_metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare scraped metrics with expected metrics.
    
    Args:
        scraped_metrics (List[Dict[str, Any]]): Scraped metrics list.
        expected_metrics (Dict[str, Any]): Expected metrics.
        
    Returns:
        Dict[str, Any]: Comparison result with "match" flag and any mismatches.
    """
    result = {
        "match": True,
        "mismatches": []
    }
    
    # Check if scraped_metrics is a list and has at least one item
    if not isinstance(scraped_metrics, list) or not scraped_metrics:
        result["match"] = False
        result["mismatches"].append("Scraped metrics is not a valid list or is empty")
        return result
    
    # Get the first metrics item
    metrics = scraped_metrics[0]
    
    for key, expected_value in expected_metrics.items():
        if key not in metrics:
            result["match"] = False
            result["mismatches"].append(f"Missing metric: {key}")
            continue
        
        scraped_value = metrics[key]
        # Clean up values for comparison (remove spaces, etc.)
        expected_clean = str(expected_value).replace(" ", "").strip()
        scraped_clean = str(scraped_value).replace(" ", "").strip()
        
        if expected_clean != scraped_clean:
            result["match"] = False
            result["mismatches"].append(f"Metric {key}: expected '{expected_value}', got '{scraped_value}'")
    
    return result

async def cleanup_test_data():
    """
    Clean up test data from the database.
    """
    try:
        # Connect to MongoDB
        mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        client = AsyncIOMotorClient(mongo_uri)
        db = client["stock_data"]
        collection = db["detailed_financials"]
        
        # Remove test data
        logger.info(f"Cleaning up test data for {EXPECTED_COMPANY}...")
        result = await collection.delete_many({"company_name": {"$regex": EXPECTED_COMPANY, "$options": "i"}})
        logger.info(f"Removed {result.deleted_count} test documents")
    except Exception as e:
        logger.error(f"Error cleaning up test data: {str(e)}")

async def main():
    """
    Main function to run the test.
    """
    try:
        # Run the test
        success = await test_scrape_single_card()
        
        # Clean up test data if requested
        cleanup_after_test = os.getenv("CLEANUP_TEST_DATA", "false").lower() == "true"
        if cleanup_after_test:
            await cleanup_test_data()
        
        # Exit with appropriate code
        if success:
            logger.info("Test completed successfully")
            return 0
        else:
            logger.error("Test failed")
            return 1
    except Exception as e:
        logger.error(f"Unhandled exception in main: {str(e)}")
        return 1

if __name__ == "__main__":
    # Run the async main function
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 