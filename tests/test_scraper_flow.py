#!/usr/bin/env python3
"""
Comprehensive test script for the full scraping flow:
1. Scrape data from MoneyControl
2. Save data to the database
3. Validate the saved data
4. Test API endpoints that return the data

This script combines functionality from multiple test scripts to provide
a complete end-to-end test of the scraping and API functionality.
"""

import asyncio
import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime
from dotenv import load_dotenv
import requests
from motor.motor_asyncio import AsyncIOMotorClient

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import scraper modules
from src.scraper.scraper_login import setup_webdriver, login_to_moneycontrol
from src.scraper.moneycontrol_scraper import (
    scrape_earnings_list, 
    scrape_single_stock,
    extract_stock_metrics
)
from src.utils.logger import logger

# Configure logging
log_file = os.path.join(os.path.dirname(__file__), "scraper_flow_test.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file)
    ]
)

# Load environment variables
load_dotenv()

# Constants
MONGO_URL = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONEYCONTROL_USERNAME = os.getenv("MONEYCONTROL_USERNAME")
MONEYCONTROL_PASSWORD = os.getenv("MONEYCONTROL_PASSWORD")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api")
EARNINGS_URL = "https://www.moneycontrol.com/markets/earnings/latest-results/?tab=LR&subType=yoy"
TEST_SYMBOL = "JUBLPHARMA"  # Use a symbol that's likely to be in the results

class ScraperFlowTest:
    """Test class for the full scraper flow."""
    
    def __init__(self):
        """Initialize the test class."""
        self.driver = None
        self.db_client = None
        self.db = None
        self.companies_collection = None
        self.financials_collection = None
        self.test_company = None
        self.test_symbol = TEST_SYMBOL
        
    async def setup(self):
        """Set up the test environment."""
        logger.info("Setting up test environment")
        
        # Set up MongoDB connection
        logger.info("Connecting to MongoDB")
        self.db_client = AsyncIOMotorClient(MONGO_URL)
        self.db = self.db_client.get_database("stock_data")
        self.companies_collection = self.db.get_collection("companies")
        self.financials_collection = self.db.get_collection("detailed_financials")
        
        # Set up WebDriver
        logger.info("Setting up WebDriver")
        self.driver = setup_webdriver()
        
        # Check if credentials are available
        if not MONEYCONTROL_USERNAME or not MONEYCONTROL_PASSWORD:
            logger.error("MoneyControl credentials not found in environment variables")
            raise ValueError("Missing MoneyControl credentials")
    
    async def teardown(self):
        """Clean up resources."""
        logger.info("Cleaning up resources")
        
        if self.driver:
            self.driver.quit()
            logger.info("WebDriver closed")
            
        if self.db_client:
            await self.db_client.close()
            logger.info("MongoDB connection closed")
    
    async def test_login(self):
        """Test login to MoneyControl."""
        logger.info("Testing login to MoneyControl")
        
        login_success = login_to_moneycontrol(
            self.driver, 
            MONEYCONTROL_USERNAME, 
            MONEYCONTROL_PASSWORD, 
            target_url=EARNINGS_URL
        )
        
        if not login_success:
            logger.error("Failed to login to MoneyControl")
            raise RuntimeError("Login to MoneyControl failed")
            
        logger.info("Login successful")
        return True
    
    async def test_scrape_earnings(self):
        """Test scraping earnings data."""
        logger.info("Testing earnings list scraper")
        
        # Scrape earnings list
        companies = await scrape_earnings_list(
            self.driver, 
            EARNINGS_URL, 
            self.companies_collection  # Save to database
        )
        
        if not companies or len(companies) == 0:
            logger.error("Failed to scrape any companies")
            raise RuntimeError("No companies scraped")
            
        logger.info(f"Successfully scraped {len(companies)} companies")
        
        # Save the first company for further testing
        self.test_company = companies[0]
        self.test_symbol = self.test_company['symbol']
        
        logger.info(f"Test company: {self.test_company['name']} ({self.test_symbol})")
        return companies
    
    async def test_scrape_stock_details(self):
        """Test scraping detailed stock information."""
        logger.info(f"Testing stock details scraper for {self.test_symbol}")
        
        # Get the stock URL
        stock_url = f"https://www.moneycontrol.com/india/stockpricequote/pharmaceuticals/{self.test_symbol.lower()}/{self.test_symbol}"
        
        # Scrape stock details
        stock_details = await scrape_single_stock(
            self.driver,
            stock_url,
            self.financials_collection  # Save to database
        )
        
        if not stock_details:
            logger.error(f"Failed to scrape stock details for {self.test_symbol}")
            raise RuntimeError(f"No stock details scraped for {self.test_symbol}")
            
        logger.info(f"Successfully scraped stock details for {self.test_symbol}")
        
        # Extract additional metrics
        metrics = await extract_stock_metrics(self.driver, stock_details.get('company_name', self.test_symbol))
        if metrics:
            logger.info(f"Successfully extracted additional metrics: {len(metrics)} metrics found")
        
        return stock_details
    
    async def validate_database(self):
        """Validate the data saved to the database."""
        logger.info("Validating database data")
        
        # Check if the company was saved to the database
        company_doc = await self.companies_collection.find_one({"symbol": self.test_symbol})
        if not company_doc:
            logger.error(f"Company {self.test_symbol} not found in database")
            raise RuntimeError(f"Company {self.test_symbol} not found in database")
            
        logger.info(f"Company {self.test_symbol} found in database")
        
        # Check if financial data was saved to the database
        financials_doc = await self.financials_collection.find_one({"symbol": self.test_symbol})
        if not financials_doc:
            logger.error(f"Financial data for {self.test_symbol} not found in database")
            raise RuntimeError(f"Financial data for {self.test_symbol} not found in database")
            
        logger.info(f"Financial data for {self.test_symbol} found in database")
        logger.info(f"Financial metrics in DB: {len(financials_doc.get('financial_metrics', []))} metrics found")
        
        # Validate the structure of the financial data
        if 'financial_metrics' not in financials_doc or not financials_doc['financial_metrics']:
            logger.error(f"Financial metrics missing for {self.test_symbol}")
            raise RuntimeError(f"Financial metrics missing for {self.test_symbol}")
            
        # Check for timestamp
        if 'timestamp' not in financials_doc:
            logger.warning(f"Timestamp missing for {self.test_symbol}")
        else:
            logger.info(f"Data timestamp: {financials_doc['timestamp']}")
            
        return True
    
    def test_api_endpoints(self):
        """Test API endpoints that return the scraped data."""
        logger.info("Testing API endpoints")
        
        # Test market data endpoint
        logger.info("Testing market data endpoint")
        market_response = requests.get(f"{API_BASE_URL}/market-data")
        
        if market_response.status_code != 200:
            logger.error(f"Market data API failed: {market_response.status_code}")
            logger.error(f"Response: {market_response.text}")
            raise RuntimeError(f"Market data API failed with status {market_response.status_code}")
            
        market_data = market_response.json()
        logger.info(f"Market data API returned {len(market_data)} items")
        
        # Test stock details endpoint
        logger.info(f"Testing stock details endpoint for {self.test_symbol}")
        stock_response = requests.get(f"{API_BASE_URL}/stock/{self.test_symbol}")
        
        if stock_response.status_code != 200:
            logger.error(f"Stock details API failed: {stock_response.status_code}")
            logger.error(f"Response: {stock_response.text}")
            raise RuntimeError(f"Stock details API failed with status {stock_response.status_code}")
            
        stock_data = stock_response.json()
        logger.info(f"Stock details API returned data for {stock_data.get('symbol', 'unknown')}")
        
        # Validate the structure of the API response
        if 'financial_metrics' not in stock_data or not stock_data['financial_metrics']:
            logger.error(f"Financial metrics missing in API response for {self.test_symbol}")
            raise RuntimeError(f"Financial metrics missing in API response for {self.test_symbol}")
            
        logger.info(f"API returned {len(stock_data['financial_metrics'])} financial metrics")
        
        return True
    
    async def run_all_tests(self):
        """Run all tests in sequence."""
        try:
            await self.setup()
            await self.test_login()
            await self.test_scrape_earnings()
            await self.test_scrape_stock_details()
            await self.validate_database()
            self.test_api_endpoints()
            
            logger.info("All tests passed successfully!")
            return True
        except Exception as e:
            logger.error(f"Test failed: {str(e)}")
            traceback.print_exc()
            return False
        finally:
            await self.teardown()

async def main():
    """Main function to run the tests."""
    logger.info("Starting scraper flow test")
    
    test = ScraperFlowTest()
    success = await test.run_all_tests()
    
    if success:
        logger.info("Scraper flow test completed successfully")
        return 0
    else:
        logger.error("Scraper flow test failed")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main())) 