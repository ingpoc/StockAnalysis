"""
Main scraper module for financial data.
Provides functions to scrape financial data from MoneyControl.
"""
import os
import time
import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from motor.motor_asyncio import AsyncIOMotorCollection
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import components
from src.scraper.browser_setup import setup_webdriver, login_to_moneycontrol
from src.scraper.extract_metrics import (
    extract_financial_data, 
    extract_company_info, 
    process_financial_data
)

# Import the centralized logger
from src.utils.logger import logger

# URL constants
URL_TYPES = {
    "LR": "https://www.moneycontrol.com/markets/earnings/latest-results/?tab=LR&subType=yoy",
    "BP": "https://www.moneycontrol.com/stocks/marketstats/results-calendar/best-performers/",
    "WP": "https://www.moneycontrol.com/stocks/marketstats/results-calendar/worst-performers/",
    "PT": "https://www.moneycontrol.com/stocks/marketstats/results-calendar/positive-trend/",
    "NT": "https://www.moneycontrol.com/stocks/marketstats/results-calendar/negative-trend/"
}

async def scrape_moneycontrol_earnings(url: str, db_collection: Optional[AsyncIOMotorCollection] = None) -> List[Dict[str, Any]]:
    """
    Scrape earnings data from MoneyControl for multiple companies or a single company.
    
    Args:
        url (str): URL of the MoneyControl earnings page or a direct stock URL.
        db_collection (AsyncIOMotorCollection, optional): MongoDB collection to store data.
        
    Returns:
        List[Dict[str, Any]]: List of dictionaries containing company financial data.
    """
    driver = None
    results = []
    
    try:
        logger.info(f"Starting scraping process for URL: {url}")
        
        # Get headless mode setting from environment
        headless_value = os.getenv('HEADLESS', 'true').lower()
        headless_mode = headless_value != "false"
        
        # Set up WebDriver
        driver = setup_webdriver(headless=headless_mode)
        if not driver:
            logger.error("Failed to set up WebDriver")
            return []
        
        # Get credentials from environment variables
        username = os.getenv('MONEYCONTROL_USERNAME')
        password = os.getenv('MONEYCONTROL_PASSWORD')
        
        if username and password:
            # Login to MoneyControl
            login_success = login_to_moneycontrol(driver, username, password, target_url=url)
            if not login_success:
                logger.error("Failed to login to MoneyControl. Proceeding without login.")
        else:
            logger.warning("MoneyControl credentials not found in environment variables. Proceeding without login.")
            # Navigate to the URL directly
            driver.get(url)
            time.sleep(3)  # Wait for page to load
        
        # Determine if it's a direct stock URL or an earnings list
        if "stockpricequote" in url or "/stock/" in url:
            logger.info("Detected direct stock URL. Scraping single stock.")
            stock_data = await scrape_single_stock(driver, url, db_collection)
            if stock_data:
                results.append(stock_data)
                logger.info(f"Successfully scraped data for {stock_data.get('company_name', 'unknown company')}")
        else:
            logger.info("Detected earnings list URL. Scraping multiple stocks.")
            stocks_data = await scrape_multiple_stocks(driver, url, db_collection)
            results.extend(stocks_data)
            logger.info(f"Successfully scraped data for {len(stocks_data)} companies")
        
        return results
    except Exception as e:
        logger.error(f"Error in scrape_moneycontrol_earnings: {str(e)}")
        return []
    finally:
        # Clean up resources
        if driver:
            logger.info("Closing WebDriver")
            driver.quit()

async def scrape_single_stock(driver: webdriver.Chrome, url: str, db_collection: Optional[AsyncIOMotorCollection] = None) -> Optional[Dict[str, Any]]:
    """
    Scrape financial data for a single stock.
    
    Args:
        driver (webdriver.Chrome): WebDriver instance.
        url (str): URL of the stock page.
        db_collection (AsyncIOMotorCollection, optional): MongoDB collection to store data.
        
    Returns:
        Dict[str, Any]: Scraped financial data or None if scraping failed.
    """
    try:
        # Wait for the page to load
        logger.info("Waiting for page to load")
        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".pcnsb, .nsecp, .bsecp, .stprh"))
            )
            logger.info("Page loaded successfully")
        except TimeoutException:
            logger.warning("Timeout waiting for page to load, proceeding anyway")
        
        # Get the page source
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # Extract company info
        company_info = extract_company_info(soup)
        company_name = company_info.get("company_name")
        symbol = company_info.get("symbol")
        
        if not company_name or not symbol:
            logger.error("Could not extract company name or symbol")
            return None
        
        logger.info(f"Extracting financial data for {company_name} ({symbol})")
        
        # Extract financial data
        financial_metrics = extract_financial_data(soup)
        
        # Process financial data
        processed_metrics = process_financial_data(financial_metrics)
        
        # Create the final data structure
        financial_data = {
            "company_name": company_name,
            "symbol": symbol,
            "financial_metrics": processed_metrics,
            "timestamp": datetime.utcnow()
        }
        
        # Store in database if provided
        if db_collection:
            logger.info(f"Storing financial data for {company_name} ({symbol}) in database")
            await db_collection.insert_one(financial_data)
        
        logger.info(f"Successfully scraped financial data for {company_name} ({symbol})")
        return financial_data
    except Exception as e:
        logger.error(f"Error scraping single stock: {str(e)}")
        return None

async def scrape_multiple_stocks(driver: webdriver.Chrome, url: str, db_collection: Optional[AsyncIOMotorCollection] = None) -> List[Dict[str, Any]]:
    """
    Scrape financial data for multiple stocks from an earnings list.
    
    Args:
        driver (webdriver.Chrome): WebDriver instance.
        url (str): URL of the earnings list page.
        db_collection (AsyncIOMotorCollection, optional): MongoDB collection to store data.
        
    Returns:
        List[Dict[str, Any]]: List of scraped financial data.
    """
    results = []
    
    try:
        # Wait for the page to load
        logger.info("Waiting for page to load")
        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".earnings-card, .result-card, .card, tr.row, tr.data-row, .EarningUpdate_erUpdtList__8QL_Z, .EarningUpdateCard_listItem__659iw"))
            )
            logger.info("Page loaded successfully")
        except TimeoutException:
            logger.warning("Timeout waiting for page to load, proceeding anyway")
        
        # Take a screenshot for debugging
        logger.info("Taking screenshot for debugging")
        try:
            driver.save_screenshot("debug_screenshot.png")
            logger.info("Screenshot saved as debug_screenshot.png")
        except Exception as e:
            logger.warning(f"Failed to take screenshot: {str(e)}")
        
        # Save page source for debugging
        try:
            page_source = driver.page_source
            with open("page_source.html", "w", encoding="utf-8") as f:
                f.write(page_source)
            logger.info("Page source saved to page_source.html")
        except Exception as e:
            logger.warning(f"Failed to save page source: {str(e)}")
        
        # Find all stock cards
        logger.info("Finding stock cards")
        card_selectors = [
            ".EarningUpdateCard_listItem__659iw",
            ".EarningUpdate_erUpdtList__8QL_Z > *",
            ".earnings-card",
            ".result-card",
            ".card",
            "tr.row",
            "tr.data-row",
            "div[class*='EarningUpdateCard']",  # Any div with 'EarningUpdateCard' in its class
            "div[class*='card']",  # Any div with 'card' in its class
        ]
        
        # Try each selector
        cards = []
        for selector in card_selectors:
            logger.info(f"Trying selector: {selector}")
            try:
                found_cards = driver.find_elements(By.CSS_SELECTOR, selector)
                if found_cards:
                    logger.info(f"Found {len(found_cards)} cards with selector: {selector}")
                    cards = found_cards
                    break
            except Exception as e:
                logger.warning(f"Error finding cards with selector {selector}: {str(e)}")
        
        # If no cards found, try to get the page source and log it
        if not cards:
            logger.warning("No cards found with any selector, checking page source")
            try:
                # Try to find cards based on the search results structure
                soup = BeautifulSoup(page_source, 'html.parser')
                
                # Try to find the earnings update list
                earnings_list = soup.select('.EarningUpdate_erUpdtList__8QL_Z')
                if earnings_list:
                    logger.info("Found .EarningUpdate_erUpdtList__8QL_Z section in page source")
                    # Try to find all company entries
                    company_entries = earnings_list[0].find_all('div', class_='EarningUpdateCard_listItem__659iw')
                    if company_entries:
                        logger.info(f"Found {len(company_entries)} company entries in .EarningUpdate_erUpdtList__8QL_Z")
                        # Process each company entry manually
                        for entry in company_entries:
                            try:
                                company_name_elem = entry.select_one('.EarningUpdateCard_stkName__Jkf_F')
                                if company_name_elem:
                                    company_name = company_name_elem.text.strip()
                                    logger.info(f"Found company: {company_name}")
                                    
                                    # Extract financial data
                                    financial_data = extract_financial_data(BeautifulSoup(str(entry), 'html.parser'))
                                    
                                    # Create company data dictionary
                                    company_data = {
                                        "company_name": company_name,
                                        "symbol": extract_symbol_from_card(entry) or "",
                                        "financial_metrics": [financial_data],
                                        "timestamp": datetime.now()
                                    }
                                    
                                    # Store in database if provided
                                    if db_collection is not None:
                                        await store_financial_data(company_data, db_collection)
                                    
                                    results.append(company_data)
                                    
                                    # If we have at least one result, break the loop
                                    if len(results) > 0:
                                        break
                            except Exception as e:
                                logger.error(f"Error processing company entry: {str(e)}")
                    else:
                        logger.warning("No company entries found in .EarningUpdate_erUpdtList__8QL_Z")
                else:
                    logger.warning("No .EarningUpdate_erUpdtList__8QL_Z section found in page source")
            except Exception as e:
                logger.error(f"Error processing page source: {str(e)}")
        
        if not cards and not results:
            logger.error("No stock cards found")
            return []
        
        # Process each card
        if cards:
            logger.info(f"Processing {len(cards)} stock cards")
            for card in cards:
                try:
                    # Extract company name
                    company_name = extract_company_name_from_card(card)
                    if not company_name:
                        logger.warning("Could not extract company name from card, skipping")
                        continue
                    
                    logger.info(f"Processing card for company: {company_name}")
                    
                    # Extract financial data
                    financial_data = extract_financial_data(BeautifulSoup(card.get_attribute("outerHTML"), 'html.parser'))
                    
                    # Create company data dictionary
                    company_data = {
                        "company_name": company_name,
                        "symbol": extract_symbol_from_card(card) or "",
                        "financial_metrics": [financial_data],
                        "timestamp": datetime.now()
                    }
                    
                    # Store in database if provided
                    if db_collection is not None:
                        await store_financial_data(company_data, db_collection)
                    
                    results.append(company_data)
                    
                    # If we have at least one result, break the loop
                    if len(results) > 0:
                        break
                except Exception as e:
                    logger.error(f"Error processing card: {str(e)}")
        
        logger.info(f"Successfully scraped data for {len(results)} companies")
        return results
    except Exception as e:
        logger.error(f"Error scraping multiple stocks: {str(e)}")
        return []
    finally:
        # Close the WebDriver
        logger.info("Closing WebDriver")
        if driver:
            driver.quit()

async def store_financial_data(data: Dict[str, Any], collection: AsyncIOMotorCollection) -> bool:
    """
    Store financial data in the database.
    
    Args:
        data (Dict[str, Any]): Financial data to store.
        collection (AsyncIOMotorCollection): MongoDB collection to store data.
        
    Returns:
        bool: True if data was stored successfully, False otherwise.
    """
    try:
        logger.info(f"Storing financial data for {data.get('company_name', 'unknown')} in database")
        await collection.insert_one(data)
        logger.info(f"Financial data for {data.get('company_name', 'unknown')} stored successfully")
        return True
    except Exception as e:
        logger.error(f"Error storing financial data: {str(e)}")
        return False

def extract_company_name_from_card(card) -> Optional[str]:
    """
    Extract company name from a stock card.
    
    Args:
        card: Stock card element or BeautifulSoup object.
        
    Returns:
        str: Company name or None if not found.
    """
    try:
        # If card is a BeautifulSoup object
        if isinstance(card, BeautifulSoup) or hasattr(card, 'select_one'):
            # Try different selectors for company name
            selectors = [
                '.EarningUpdateCard_stkName__Jkf_F',  # New class for company name
                'h3',  # Based on the search results
                '.company-name',
                '.name',
                'td:first-child',
                'th:first-child',
                '.card-title',
                '.title'
            ]
            
            for selector in selectors:
                element = card.select_one(selector)
                if element:
                    company_name = element.text.strip()
                    if company_name:
                        return company_name
            
            # If no selector worked, try to find any text that might be a company name
            text = card.get_text().strip()
            if text:
                # Split by newlines and take the first non-empty line
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                if lines:
                    return lines[0]
            
            return None
        
        # If card is a Selenium WebElement
        else:
            # Try different methods to extract company name
            try:
                # Try to find the new company name element
                company_name_element = card.find_element(By.CSS_SELECTOR, '.EarningUpdateCard_stkName__Jkf_F')
                if company_name_element:
                    return company_name_element.text.strip()
            except:
                pass
            
            try:
                # Try to find h3 element (based on search results)
                h3_element = card.find_element(By.TAG_NAME, 'h3')
                if h3_element:
                    return h3_element.text.strip()
            except:
                pass
            
            # Try other selectors
            selectors = [
                '.company-name',
                '.name',
                'td:first-child',
                'th:first-child',
                '.card-title',
                '.title'
            ]
            
            for selector in selectors:
                try:
                    element = card.find_element(By.CSS_SELECTOR, selector)
                    if element:
                        return element.text.strip()
                except:
                    continue
            
            # If no selector worked, try to get the text content
            try:
                text = card.text.strip()
                if text:
                    # Split by newlines and take the first non-empty line
                    lines = [line.strip() for line in text.split('\n') if line.strip()]
                    if lines:
                        return lines[0]
            except:
                pass
            
            return None
    except Exception as e:
        logger.error(f"Error extracting company name: {str(e)}")
        return None

def extract_symbol_from_card(card) -> Optional[str]:
    """
    Extract stock symbol from a stock card.
    
    Args:
        card: Stock card element or BeautifulSoup object.
        
    Returns:
        str: Stock symbol or None if not found.
    """
    try:
        # If card is a BeautifulSoup object
        if isinstance(card, BeautifulSoup) or hasattr(card, 'select_one'):
            # Try to find the symbol in the price section (based on search results)
            # Example: "14.98 (1.56%)" - we want to extract the symbol from elsewhere
            
            # Try different selectors for symbol
            selectors = [
                '.EarningUpdateCard_stkData__rEKCf',  # New class for stock data
                '.symbol',
                '.ticker',
                '.stock-code',
                'h3 + div',  # Div after h3 (might contain the symbol)
                'h3 small',  # Small text inside h3
                'h3 span'    # Span inside h3
            ]
            
            for selector in selectors:
                element = card.select_one(selector)
                if element:
                    symbol_text = element.text.strip()
                    if symbol_text:
                        # Clean up the symbol (remove parentheses, etc.)
                        symbol = symbol_text.split('(')[0].strip()
                        return symbol
            
            # If we couldn't find the symbol, use the company name as a fallback
            company_name = extract_company_name_from_card(card)
            if company_name:
                return company_name
            
            return None
        
        # If card is a Selenium WebElement
        else:
            # Try different methods to extract symbol
            selectors = [
                '.EarningUpdateCard_stkData__rEKCf',  # New class for stock data
                '.symbol',
                '.ticker',
                '.stock-code',
                'h3 + div',  # Div after h3
                'h3 small',  # Small text inside h3
                'h3 span'    # Span inside h3
            ]
            
            for selector in selectors:
                try:
                    element = card.find_element(By.CSS_SELECTOR, selector)
                    if element:
                        symbol_text = element.text.strip()
                        if symbol_text:
                            # Clean up the symbol (remove parentheses, etc.)
                            symbol = symbol_text.split('(')[0].strip()
                            return symbol
                except:
                    continue
            
            # If we couldn't find the symbol, use the company name as a fallback
            company_name = extract_company_name_from_card(card)
            if company_name:
                return company_name
            
            return None
    except Exception as e:
        logger.error(f"Error extracting symbol: {str(e)}")
        return None

async def scrape_by_result_type(result_type: str, db_collection: Optional[AsyncIOMotorCollection] = None) -> List[Dict[str, Any]]:
    """
    Scrape financial data by result type.
    
    Args:
        result_type (str): Type of results to scrape (LR, BP, WP, PT, NT).
        db_collection (AsyncIOMotorCollection, optional): MongoDB collection to store data.
        
    Returns:
        List[Dict[str, Any]]: List of scraped financial data.
    """
    if result_type not in URL_TYPES:
        logger.error(f"Invalid result type: {result_type}")
        return []
    
    url = URL_TYPES[result_type]
    logger.info(f"Scraping {result_type} results from URL: {url}")
    
    return await scrape_moneycontrol_earnings(url, db_collection)

async def scrape_custom_url(url: str, db_collection: Optional[AsyncIOMotorCollection] = None) -> List[Dict[str, Any]]:
    """
    Scrape financial data from a custom URL.
    
    Args:
        url (str): Custom URL to scrape.
        db_collection (AsyncIOMotorCollection, optional): MongoDB collection to store data.
        
    Returns:
        List[Dict[str, Any]]: List of scraped financial data.
    """
    logger.info(f"Scraping custom URL: {url}")
    return await scrape_moneycontrol_earnings(url, db_collection) 