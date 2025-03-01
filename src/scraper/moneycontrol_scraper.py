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
        logger.info(f"Starting scraping process for URL: {url}")
        logger.info("Setting up WebDriver")
        
        # Get headless mode setting from environment
        headless_value = os.getenv('HEADLESS', 'true').lower()
        headless_mode = headless_value != "false"
        
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
            # Wait for the first result card selector to be present with a longer timeout
            logger.info("Waiting for result cards to load...")
            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'li.rapidResCardWeb_gryCard__hQigs'))
            )   
            logger.info("Page loaded successfully")
        except TimeoutException:
            logger.warning("Timeout waiting for primary result cards selector. Trying alternative selectors...")
            
            # Try alternative selectors
            try:
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'li.gryCard'))
                )
                logger.info("Page loaded with alternative selector 'li.gryCard'")
            except TimeoutException:
                try:
                    WebDriverWait(driver, 30).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'div.card'))
                    )
                    logger.info("Page loaded with alternative selector 'div.card'")
                except TimeoutException:
                    logger.error("Timeout waiting for all result cards selectors. Saving page source for debugging.")
                    # Save the page source for debugging
                    with open("debug_timeout_page.html", "w", encoding="utf-8") as f:
                        f.write(driver.page_source)
                    logger.info("Saved page source to debug_timeout_page.html for debugging")
                    return []
            
        # Scroll to load all content
        logger.info("Scrolling page to load all content")
        scroll_page(driver)
        
        # Parse the page
        logger.info("Parsing page content")
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Try multiple selectors to find result cards
        result_cards = soup.select('li.rapidResCardWeb_gryCard__hQigs')
        
        if not result_cards:
            logger.warning("No result cards found with primary selector. Trying alternative selectors.")
            # Try alternative selectors if the primary one doesn't work
            result_cards = soup.select('li.gryCard')
            if not result_cards:
                result_cards = soup.select('div.card')
                if not result_cards:
                    # Try even more generic selectors
                    result_cards = soup.select('li[class*="gryCard"]')
                    if not result_cards:
                        result_cards = soup.select('div[class*="card"]')
        
        logger.info(f"Found {len(result_cards)} result cards to process")
        
        if len(result_cards) == 0:
            logger.error("No result cards found on the page. Check if the page structure has changed.")
            # Save the page source for debugging
            with open("debug_page_source.html", "w", encoding="utf-8") as f:
                f.write(page_source)
            logger.info("Saved page source to debug_page_source.html for debugging")
            return []
        
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
        for i, card in enumerate(result_cards):
            try:
                logger.info(f"Processing card {i+1} of {len(result_cards)}")
                # Process the card and store the data
                company_data = await process_result_card(card, driver, db_collection)
                if company_data:
                    results.append(company_data)
                    logger.info(f"Successfully processed card {i+1}")
                else:
                    logger.info(f"Card {i+1} was skipped (already exists or error)")
            except Exception as e:
                logger.error(f"Error processing card {i+1}: {str(e)}")
                # Continue with the next card
                continue
        
        logger.info(f"Successfully scraped {len(results)} companies' financial data from {tab_type}")
        return results
        
    except TimeoutException as e:
        logger.error(f"Timeout waiting for page to load: {str(e)}")
        return results
    except WebDriverException as e:
        logger.error(f"WebDriver error: {str(e)}")
        return results
    except Exception as e:
        logger.error(f"Unexpected error during scraping: {str(e)}")
        return results
    finally:
        if driver:
            try:
                driver.quit()
                logger.info("WebDriver closed")
            except Exception as e:
                logger.error(f"Error closing WebDriver: {str(e)}")

def scroll_page(driver) -> None:
    """
    Scrolls the page to load all dynamic content.
    
    Args:
        driver: Selenium WebDriver instance.
    """
    try:
        logger.info("Starting page scrolling to load dynamic content")
        last_height = driver.execute_script("return document.body.scrollHeight")
        scroll_attempts = 0
        max_scroll_attempts = 10  # Limit scrolling attempts to avoid infinite loops
        
        while scroll_attempts < max_scroll_attempts:
            # Scroll down to bottom
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            # Wait to load page
            time.sleep(2)
            
            # Calculate new scroll height and compare with last scroll height
            new_height = driver.execute_script("return document.body.scrollHeight")
            
            if new_height == last_height:
                # Try one more time to ensure content is fully loaded
                time.sleep(1)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                final_height = driver.execute_script("return document.body.scrollHeight")
                
                if final_height == new_height:
                    logger.info(f"Scrolling complete after {scroll_attempts + 1} attempts")
                    break
            
            last_height = new_height
            scroll_attempts += 1
            logger.debug(f"Scroll attempt {scroll_attempts}/{max_scroll_attempts}")
        
        if scroll_attempts >= max_scroll_attempts:
            logger.warning("Reached maximum scroll attempts. Some content might not be loaded.")
            
        # Scroll back to top for better processing
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
        
    except Exception as e:
        logger.error(f"Error during page scrolling: {str(e)}")
        # Continue with whatever content was loaded

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