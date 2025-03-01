"""
Main module for scraping financial data from MoneyControl.
"""
import logging
import time
import asyncio
import os
import datetime
from typing import Dict, List, Optional, Any, Union
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from motor.motor_asyncio import AsyncIOMotorCollection
from dotenv import load_dotenv

from src.scraper.scraper_login import setup_webdriver, login_to_moneycontrol
from src.scraper.scrape_metrics import extract_financial_data

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
        
        # Get the live DOM elements instead of parsing with BeautifulSoup
        # This allows us to interact with each card directly
        logger.info("Finding result cards in the live DOM")
        
        # Try multiple selectors to find result cards
        result_cards = driver.find_elements(By.CSS_SELECTOR, 'li.rapidResCardWeb_gryCard__hQigs')
        
        if not result_cards:
            logger.warning("No result cards found with primary selector. Trying alternative selectors.")
            # Try alternative selectors if the primary one doesn't work
            result_cards = driver.find_elements(By.CSS_SELECTOR, 'li.gryCard')
            if not result_cards:
                result_cards = driver.find_elements(By.CSS_SELECTOR, 'div.card')
                if not result_cards:
                    # Try even more generic selectors
                    result_cards = driver.find_elements(By.CSS_SELECTOR, 'li[class*="gryCard"]')
                    if not result_cards:
                        result_cards = driver.find_elements(By.CSS_SELECTOR, 'div[class*="card"]')
        
        logger.info(f"Found {len(result_cards)} result cards to process")
        
        if len(result_cards) == 0:
            logger.error("No result cards found on the page. Check if the page structure has changed.")
            # Save the page source for debugging
            with open("debug_page_source.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
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
        
        # Process each company card directly in the DOM
        for i, card_element in enumerate(result_cards):
            try:
                logger.info(f"Processing card {i+1} of {len(result_cards)}")
                
                # Extract company name and link directly from the DOM element
                try:
                    company_name_element = card_element.find_element(By.CSS_SELECTOR, 'h3 a')
                    company_name = company_name_element.text.strip()
                    stock_link = company_name_element.get_attribute('href')
                    
                    if not company_name or not stock_link:
                        logger.warning(f"Skipping card {i+1} due to missing company name or stock link.")
                        continue
                        
                    logger.info(f"Processing stock: {company_name}")
                    
                    # Check if this company already exists in the database with this quarter's data
                    # Get the quarter information from the card
                    try:
                        quarter_element = card_element.find_element(By.CSS_SELECTOR, 'tr th:nth-child(1)')
                        quarter = quarter_element.text.strip()
                    except Exception as e:
                        logger.warning(f"Could not extract quarter for {company_name}: {str(e)}")
                        quarter = None
                        
                    if not quarter:
                        logger.warning(f"Skipping {company_name} due to missing quarter information.")
                        continue
                        
                    # Check database for existing data
                    existing_company = None
                    if db_collection is not None:
                        try:
                            existing_company = await db_collection.find_one({"company_name": company_name})
                            if existing_company is not None:
                                existing_quarters = [metric.get('quarter') for metric in existing_company.get('financial_metrics', []) if metric.get('quarter')]
                                if quarter in existing_quarters:
                                    logger.info(f"{company_name} already has data for {quarter}. Skipping.")
                                    continue
                        except Exception as e:
                            logger.error(f"Error checking existing data for {company_name}: {str(e)}")
                            # Continue with the scraping even if the database check fails
                    
                    # Extract basic financial data from the card
                    # Convert the Selenium element to HTML and parse with BeautifulSoup for easier data extraction
                    card_html = card_element.get_attribute('outerHTML')
                    card_soup = BeautifulSoup(card_html, 'html.parser')
                    financial_data = extract_financial_data(card_soup)
                    
                    if not financial_data:
                        logger.warning(f"Could not extract basic financial data for {company_name}. Skipping.")
                        continue
                    
                    # Now navigate to the stock's detail page to get additional metrics
                    original_window = driver.current_window_handle
                    
                    try:
                        # Open the stock link in a new tab
                        driver.execute_script(f"window.open('{stock_link}', '_blank');")
                        driver.switch_to.window(driver.window_handles[-1])
                        
                        # Wait for the page to load
                        try:
                            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'body')))
                        except TimeoutException:
                            logger.warning(f"Timeout waiting for stock page to load: {stock_link}")
                            driver.close()
                            driver.switch_to.window(original_window)
                            continue
                        
                        # Extract additional metrics
                        additional_metrics, symbol = None, None
                        try:
                            # Use the existing scrape_financial_metrics function
                            # But since we're already on the page, we'll extract the metrics directly
                            detailed_soup = BeautifulSoup(driver.page_source, 'html.parser')
                            
                            # Initialize metrics dictionary with default None values
                            additional_metrics = {
                                "market_cap": None,
                                "face_value": None,
                                "book_value": None,
                                "dividend_yield": None,
                                "ttm_eps": None,
                                "ttm_pe": None,
                                "pb_ratio": None,
                                "sector_pe": None,
                                "piotroski_score": None,
                                "revenue_growth_3yr_cagr": None,
                                "net_profit_growth_3yr_cagr": None,
                                "operating_profit_growth_3yr_cagr": None,
                                "strengths": None,
                                "weaknesses": None,
                                "technicals_trend": None,
                                "fundamental_insights": None,
                                "fundamental_insights_description": None
                            }
                            
                            # Safely extract each metric
                            try:
                                if detailed_soup.select_one('tr:nth-child(7) td.nsemktcap.bsemktcap'):
                                    additional_metrics["market_cap"] = detailed_soup.select_one('tr:nth-child(7) td.nsemktcap.bsemktcap').text.strip()
                            except Exception as e:
                                logger.debug(f"Error extracting market cap: {str(e)}")
                                
                            try:
                                if detailed_soup.select_one('tr:nth-child(7) td.nsefv.bsefv'):
                                    additional_metrics["face_value"] = detailed_soup.select_one('tr:nth-child(7) td.nsefv.bsefv').text.strip()
                            except Exception as e:
                                logger.debug(f"Error extracting face value: {str(e)}")
                                
                            try:
                                if detailed_soup.select_one('tr:nth-child(5) td.nsebv.bsebv'):
                                    additional_metrics["book_value"] = detailed_soup.select_one('tr:nth-child(5) td.nsebv.bsebv').text.strip()
                            except Exception as e:
                                logger.debug(f"Error extracting book value: {str(e)}")
                                
                            try:
                                if detailed_soup.select_one('tr:nth-child(6) td.nsedy.bsedy'):
                                    additional_metrics["dividend_yield"] = detailed_soup.select_one('tr:nth-child(6) td.nsedy.bsedy').text.strip()
                            except Exception as e:
                                logger.debug(f"Error extracting dividend yield: {str(e)}")
                                
                            try:
                                if detailed_soup.select_one('tr:nth-child(1) td:nth-child(2) span.nseceps.bseceps'):
                                    additional_metrics["ttm_eps"] = detailed_soup.select_one('tr:nth-child(1) td:nth-child(2) span.nseceps.bseceps').text.strip()
                            except Exception as e:
                                logger.debug(f"Error extracting TTM EPS: {str(e)}")
                                
                            try:
                                if detailed_soup.select_one('tr:nth-child(2) td:nth-child(2) span.nsepe.bsepe'):
                                    additional_metrics["ttm_pe"] = detailed_soup.select_one('tr:nth-child(2) td:nth-child(2) span.nsepe.bsepe').text.strip()
                            except Exception as e:
                                logger.debug(f"Error extracting TTM PE: {str(e)}")
                                
                            try:
                                if detailed_soup.select_one('tr:nth-child(3) td:nth-child(2) span.nsepb.bsepb'):
                                    additional_metrics["pb_ratio"] = detailed_soup.select_one('tr:nth-child(3) td:nth-child(2) span.nsepb.bsepb').text.strip()
                            except Exception as e:
                                logger.debug(f"Error extracting PB ratio: {str(e)}")
                                
                            try:
                                if detailed_soup.select_one('tr:nth-child(4) td.nsesc_ttm.bsesc_ttm'):
                                    additional_metrics["sector_pe"] = detailed_soup.select_one('tr:nth-child(4) td.nsesc_ttm.bsesc_ttm').text.strip()
                            except Exception as e:
                                logger.debug(f"Error extracting sector PE: {str(e)}")
                                
                            # Extract company symbol
                            try:
                                if detailed_soup.select_one('#company_info > ul > li:nth-child(5) > ul > li:nth-child(2) > p'):
                                    symbol = detailed_soup.select_one('#company_info > ul > li:nth-child(5) > ul > li:nth-child(2) > p').text.strip()
                            except Exception as e:
                                logger.debug(f"Error extracting symbol: {str(e)}")
                                
                            # Try alternative selectors for symbol if the primary one failed
                            if not symbol:
                                try:
                                    # Try to find symbol in the page title
                                    title = detailed_soup.select_one('title')
                                    if title and '(' in title.text and ')' in title.text:
                                        symbol_part = title.text.split('(')[1].split(')')[0]
                                        if symbol_part:
                                            symbol = symbol_part
                                except Exception as e:
                                    logger.debug(f"Error extracting symbol from title: {str(e)}")
                            
                        except Exception as e:
                            logger.error(f"Error extracting additional metrics for {company_name}: {str(e)}")
                            # Continue with basic data if additional metrics fail
                        
                        # Close the tab and switch back to the original window
                        driver.close()
                        driver.switch_to.window(original_window)
                        
                        # Update financial data with additional metrics
                        if additional_metrics is not None:
                            financial_data.update(additional_metrics)
                        
                        # Prepare the complete company data
                        stock_data = {
                            "company_name": company_name,
                            "symbol": symbol,
                            "financial_metrics": financial_data,
                            "timestamp": datetime.datetime.utcnow()
                        }
                        
                        # Save to database if a collection was provided
                        if db_collection is not None and financial_data.get('quarter') is not None:
                            try:
                                if existing_company is not None:
                                    logger.info(f"Adding new data for {company_name} - {financial_data.get('quarter')}")
                                    await db_collection.update_one(
                                        {"company_name": company_name},
                                        {"$push": {"financial_metrics": financial_data}}
                                    )
                                else:
                                    logger.info(f"Creating new entry for {company_name}")
                                    new_stock_data = {
                                        "company_name": company_name,
                                        "symbol": symbol,
                                        "financial_metrics": [financial_data],
                                        "timestamp": datetime.datetime.utcnow()
                                    }
                                    await db_collection.insert_one(new_stock_data)
                                    
                                logger.info(f"Data for {company_name} (quarter {financial_data.get('quarter')}) processed successfully.")
                            except Exception as e:
                                logger.error(f"Database error for {company_name}: {str(e)}")
                                # Return the data even if database operation fails
                        
                        results.append(stock_data)
                        logger.info(f"Successfully processed card {i+1}")
                        
                    except Exception as e:
                        logger.error(f"Error processing stock page for {company_name}: {str(e)}")
                        # Make sure to close the new tab and switch back if there was an error
                        try:
                            # Check if we're not in the original window
                            if driver.current_window_handle != original_window:
                                driver.close()
                                driver.switch_to.window(original_window)
                        except Exception as close_error:
                            logger.error(f"Error closing tab: {str(close_error)}")
                        continue
                        
                except Exception as e:
                    logger.error(f"Error extracting company info from card {i+1}: {str(e)}")
                    continue
                    
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