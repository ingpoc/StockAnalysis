"""
Main module for scraping financial data from MoneyControl.
"""
import logging
import time
import asyncio
import os
from typing import Dict, List, Optional, Any, Union
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from motor.motor_asyncio import AsyncIOMotorCollection
from dotenv import load_dotenv

from src.scraper.scraper_login import setup_webdriver, login_to_moneycontrol
from src.scraper.scrape_metrics import process_result_card, extract_financial_data

# Load environment variables
load_dotenv()

# Setup logging
logger = logging.getLogger(__name__)

async def scrape_moneycontrol_earnings(url: str, db_collection: Optional[AsyncIOMotorCollection] = None) -> List[Dict[str, Any]]:
    """
    Scrape earnings data from MoneyControl for multiple companies.
    
    Args:
        url (str): URL of the MoneyControl earnings page.
        db_collection (AsyncIOMotorCollection, optional): MongoDB collection to store data.
        
    Returns:
        List[Dict[str, Any]]: List of dictionaries containing company financial data.
    """
    driver = None
    results = []
    
    try:
        logger.info("Setting up WebDriver")
        driver = setup_webdriver()
        logger.info(f"WebDriver set up successfully")
        
        # Get credentials from environment variables
        username = os.getenv('MONEYCONTROL_USERNAME')
        password = os.getenv('MONEYCONTROL_PASSWORD')
        
        if not username or not password:
            logger.error("MoneyControl credentials not found in environment variables.")
            return []
            
        logger.info(f"Attempting to login to MoneyControl")
        # Login to MoneyControl with username and password, and redirect to the target URL
        login_success = login_to_moneycontrol(driver, username, password, target_url=url)
        if not login_success:
            logger.error("Failed to login to MoneyControl. Aborting scrape.")
            return []
            
        # Wait for the page to load
        try:
            # Wait for the first result card selector to be present
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'li.rapidResCardWeb_gryCard__hQigs'))
            )   
            logger.info("Page loaded successfully")
        except TimeoutException:
            logger.error("Timeout waiting for result cards to load")
            return []
            
        # Scroll to load all content
        scroll_page(driver)
        
        # Parse the page
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        result_cards = soup.select('li.rapidResCardWeb_gryCard__hQigs')
        logger.info(f"Found {len(result_cards)} result cards to process")
        
        # Extract the tab type from URL for logging
        tab_type = "Latest Results"  # Default
        if "tab=" in url:
            tab_param = url.split("tab=")[1].split("&")[0]
            if tab_param == "BP":
                tab_type = "Best Performer"
            elif tab_param == "WP":
                tab_type = "Worst Performer"
            elif tab_param == "PT":
                tab_type = "Positive Turnaround"
            elif tab_param == "NT":
                tab_type = "Negative Turnaround"
                
        logger.info(f"Scraping {tab_type} with {len(result_cards)} companies")
        
        # Process each company card
        for card in result_cards:
            # Process the card and store the data
            company_data = process_result_card(card, driver, db_collection)
            if company_data:
                results.append(company_data)
        
        logger.info(f"Successfully scraped {len(results)} companies' financial data from {tab_type}")
        return results
        
    except TimeoutException:
        logger.error("Timeout waiting for page to load")
        return results
    except WebDriverException as e:
        logger.error(f"WebDriver error: {str(e)}")
        return results
    except Exception as e:
        logger.error(f"Unexpected error during scraping: {str(e)}")
        return results
    finally:
        if driver:
            driver.quit()
            logger.info("WebDriver closed")

def scroll_page(driver) -> None:
    """
    Scrolls the page to load all dynamic content.
    
    Args:
        driver: Selenium WebDriver instance.
    """
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

async def scrape_stock_symbol_mappings() -> Dict[str, str]:
    """
    Scrape stock symbol mappings from MoneyControl.
    
    Returns:
        Dict[str, str]: Dictionary mapping company names to their stock symbols.
    """
    # Implement this if needed to create a mapping of company names to symbols
    # This can be useful to maintain a cache of symbols for faster lookups
    pass

async def get_company_financials(company_name: str, db_collection: AsyncIOMotorCollection) -> Union[Dict[str, Any], None]:
    """
    Retrieve financial data for a specific company.
    
    Args:
        company_name (str): Name of the company.
        db_collection (AsyncIOMotorCollection): MongoDB collection to query.
        
    Returns:
        Union[Dict[str, Any], None]: Financial data for the company or None if not found.
    """
    try:
        return await db_collection.find_one({"company_name": company_name})
    except Exception as e:
        logger.error(f"Error retrieving company data: {str(e)}")
        return None 