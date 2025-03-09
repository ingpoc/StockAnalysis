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
from selenium.common.exceptions import (
    TimeoutException, 
    WebDriverException, 
    NoSuchElementException,
    NoSuchWindowException,
    InvalidSessionIdException
)
from motor.motor_asyncio import AsyncIOMotorCollection
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import components
from src.scraper.browser_setup import setup_webdriver, login_to_moneycontrol
from src.scraper.extract_metrics import (
    extract_financial_data, 
    extract_company_info, 
    process_financial_data,
    scrape_financial_metrics
)
from src.scraper.db_operations import (
    store_financial_data,
    update_or_insert_company_data
)

# Import the centralized logger
from src.utils.logger import logger

# URL constants
URL_TYPES = {
    "LR": "https://www.moneycontrol.com/markets/earnings/latest-results/?tab=LR&subType=yoy",
    "BP": "https://www.moneycontrol.com/markets/earnings/latest-results/?tab=BP&subType=yoy",
    "WP": "https://www.moneycontrol.com/markets/earnings/latest-results/?tab=WP&subType=yoy",
    "PT": "https://www.moneycontrol.com/markets/earnings/latest-results/?tab=PT&subType=yoy",
    "NT": "https://www.moneycontrol.com/markets/earnings/latest-results/?tab=NT&subType=yoy"
}

async def scrape_moneycontrol_earnings(url: str, db_collection: Optional[AsyncIOMotorCollection] = None) -> List[Dict[str, Any]]:
    """
    Scrape earnings data from MoneyControl for multiple companies or a single company.
    
    Args:
        url (str): URL of the MoneyControl earnings page or a direct stock URL.
        db_collection (AsyncIOMotorCollection, optional): MongoDB collection to store data.
        
    Returns:
        List[Dict[str, Any]]: List of financial data dictionaries.
    """
    results = []
    driver = setup_webdriver()
    last_card_count = 0
    no_new_content_count = 0
    max_no_new_content = 3  # Stop after 3 attempts with no new content
    
    try:
        # Login to MoneyControl with ad handling
        login_success = login_to_moneycontrol(driver, target_url=url)
        if not login_success:
            logger.error("Failed to login to MoneyControl")
            return results
        
        logger.info(f"Opening page: {url}")
        driver.get(url)
        
        # Wait for result cards to load
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '#latestRes > div > ul > li:nth-child(1)'))
        )
        logger.info("Page opened successfully")
        
        # Process cards incrementally while scrolling
        while True:
            # Early check if browser is still open
            try:
                # This will raise an exception if browser is closed
                _ = driver.current_url
            except (NoSuchWindowException, InvalidSessionIdException):
                logger.error("Browser window was closed during scrolling. Scraping terminated.")
                break
            
            # Find all current result cards
            result_cards = driver.find_elements(By.CSS_SELECTOR, '#latestRes > div > ul > li')
            current_card_count = len(result_cards)
            
            # Check if we have new cards
            if current_card_count == last_card_count:
                no_new_content_count += 1
                if no_new_content_count >= max_no_new_content:
                    logger.info(f"No new content after {max_no_new_content} scrolls. Ending scrape.")
                    break
            else:
                no_new_content_count = 0
                # Process only the new cards
                new_cards = result_cards[last_card_count:current_card_count]
                logger.info(f"Processing {len(new_cards)} new cards (total: {current_card_count})")
                
                # Convert HTML elements to BeautifulSoup objects for processing
                page_source = driver.page_source
                soup = BeautifulSoup(page_source, 'html.parser')
                soup_cards = soup.select('#latestRes > div > ul > li')
                
                # Process each new card
                for i, card in enumerate(soup_cards[last_card_count:current_card_count]):
                    try:
                        # Check if browser is still alive before processing each card
                        try:
                            _ = driver.current_url
                        except (NoSuchWindowException, InvalidSessionIdException):
                            logger.error("Browser window was closed. Scraping terminated.")
                            return results
                        
                        company_data = await process_result_card(card, driver, db_collection)
                        if company_data:
                            results.append(company_data)
                    except NoSuchWindowException:
                        logger.error("Browser window was closed. Scraping stopped.")
                        return results
                    except InvalidSessionIdException:
                        logger.error("Browser session was terminated. Scraping stopped.")
                        return results
                    except Exception as e:
                        company_name = card.select_one('h3 a').text.strip() if card.select_one('h3 a') else "Unknown Company"
                        logger.error(f"Error processing card for {company_name}: {str(e)}")
            
            # Update last_card_count for the next iteration
            last_card_count = current_card_count
            
            # Scroll to the last card to load more
            if result_cards:
                driver.execute_script("arguments[0].scrollIntoView();", result_cards[-1])
                time.sleep(2)  # Wait for new content to load
    
    except TimeoutException:
        logger.error("Timeout waiting for page to load")
    except NoSuchWindowException:
        logger.error("Browser window was closed by the user. Scraping terminated.")
    except InvalidSessionIdException:
        logger.error("Browser session was terminated. This usually happens when the browser is closed manually.")
    except WebDriverException as e:
        if "chrome not reachable" in str(e).lower():
            logger.error("Browser was closed or crashed. Scraping stopped.")
        else:
            logger.error(f"WebDriver error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error during scraping: {str(e)}")
    finally:
        try:
            driver.quit()
        except Exception:
            # Silently handle errors when trying to quit an already closed browser
            pass
        
    return results

def scroll_page(driver, selector='', max_no_new_content=3, sleep_time=2):
    """
    Scroll the page incrementally to load all content.
    
    Args:
        driver (webdriver.Chrome): WebDriver instance.
        selector (str): CSS selector for elements to scroll to. If empty, scrolls by page height.
        max_no_new_content (int): Maximum number of attempts with no new content before stopping.
        sleep_time (int): Seconds to wait after each scroll to allow content to load.
        
    Returns:
        int: Total number of elements found (if selector provided).
    """
    if not selector:
        # Traditional scroll by page height if no selector provided
        last_height = driver.execute_script("return document.body.scrollHeight")
        
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(sleep_time)
            
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
                
            last_height = new_height
        return 0
    else:
        # Incremental scroll by elements if selector provided
        last_element_count = 0
        no_new_content_count = 0
        
        while True:
            # Find all elements with the given selector
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            
            # Check if we have new elements
            if len(elements) == last_element_count:
                no_new_content_count += 1
                if no_new_content_count >= max_no_new_content:
                    logger.info(f"No new content after {max_no_new_content} scrolls. Ending scroll.")
                    break
            else:
                no_new_content_count = 0
            
            last_element_count = len(elements)
            logger.info(f"Found {last_element_count} elements so far")
            
            # Scroll to the last element to load more
            if elements:
                driver.execute_script("arguments[0].scrollIntoView();", elements[-1])
                time.sleep(sleep_time)  # Wait for new content to load
                
        return last_element_count

async def process_result_card(card, driver, db_collection: Optional[AsyncIOMotorCollection] = None) -> Optional[Dict[str, Any]]:
    """
    Process a result card and extract financial data.
    
    Args:
        card: BeautifulSoup element representing a result card.
        driver: WebDriver instance for navigating to company pages.
        db_collection (AsyncIOMotorCollection, optional): MongoDB collection to store data.
        
    Returns:
        Dict[str, Any]: Financial data or None if processing failed.
    """
    company_name = None
    metrics_data = None
    symbol = None
    stock_link = None
    financial_data = None
    
    try:
        # First check if browser is still active
        try:
            # A simple check that will raise an exception if browser is closed
            _ = driver.current_url
        except (NoSuchWindowException, InvalidSessionIdException):
            logger.error("Browser window was closed. Cannot process result card.")
            raise  # Re-raise to be caught by the caller
            
        # Extract company name and link
        company_name = card.select_one('h3 a').text.strip() if card.select_one('h3 a') else None
        if not company_name:
            logger.warning("Skipping card due to missing company name.")
            return None
            
        stock_link = card.select_one('h3 a')['href'] if card.select_one('h3 a') else None
        if not stock_link:
            logger.warning(f"Skipping {company_name} due to missing stock link.")
            return None
            
        logger.info(f"Processing stock: {company_name}")
        
        # Extract basic financial data from the card
        financial_data = extract_financial_data(card)
        
        # Check if we already have data for this company and quarter
        if db_collection is not None:
            # Use a more specific query that includes both company name and quarter
            quarter = financial_data.get('quarter', '')
            if quarter:
                existing_entry = await db_collection.find_one({
                    "company_name": company_name,
                    "financial_metrics": {
                        "$elemMatch": {
                            "quarter": quarter
                        }
                    }
                })
                
                if existing_entry:
                    logger.info(f"Skipping {company_name} for {quarter} - data already exists in database.")
                    return None
        
        # Handle any ads before scraping metrics
        try:
            # Check for and remove ad overlays
            ad_iframes = driver.find_elements(By.CSS_SELECTOR, "iframe[id^='google_ads_iframe']")
            if ad_iframes:
                logger.info(f"Found {len(ad_iframes)} Google ad iframes before scraping {company_name}")
                
                # Try to close the ads using JavaScript
                driver.execute_script("""
                    // Remove Google ad iframes
                    const adIframes = document.querySelectorAll('iframe[id^="google_ads_iframe"]');
                    adIframes.forEach(iframe => {
                        iframe.remove();
                    });
                    
                    // Remove any overlay divs
                    const overlays = document.querySelectorAll('div[class*="overlay"], div[id*="overlay"], .modal');
                    overlays.forEach(overlay => {
                        overlay.remove();
                    });
                """)
                logger.info("Removed ad elements before scraping metrics")
        except Exception as e:
            logger.warning(f"Error handling ad overlays for {company_name}: {str(e)}")
        
        # Get additional metrics from the company page
        # This already opens a new tab, gets the data, and closes it
        try:
            # Check if browser is still active before opening new tab
            _ = driver.current_url
            metrics_data, symbol = scrape_financial_metrics(driver, stock_link)
            
            # Verify we got meaningful data - if not, consider it a failure
            if not metrics_data or all(value is None for value in metrics_data.values()):
                logger.warning(f"Failed to extract meaningful metrics data for {company_name}")
                metrics_data = None
        except (NoSuchWindowException, InvalidSessionIdException) as e:
            logger.error(f"Browser window was closed while scraping metrics for {company_name}")
            raise  # Re-raise to be caught by caller
        except Exception as e:
            logger.error(f"Error getting metrics data for {company_name}: {str(e)}")
            metrics_data = None
        
        # If we don't have metrics data, consider this a failure and don't save
        if metrics_data is None:
            logger.warning(f"No metrics data collected for {company_name}. Skipping database storage.")
            return None
            
        # Update financial data with metrics
        if metrics_data:
            financial_data.update(metrics_data)
            
        # Add financial data to the result
        financial_metrics = [financial_data]
        
        # Create the company data object
        company_data = {
            "company_name": company_name,
            "symbol": symbol or extract_symbol_from_card(card) or "",
            "financial_metrics": financial_metrics,
            "timestamp": datetime.utcnow()  # Ensure this is a datetime object
        }
        
        # Final check if the browser is still active before saving to database
        try:
            # This will raise an exception if browser is closed
            _ = driver.current_url
        except (NoSuchWindowException, InvalidSessionIdException):
            logger.error(f"Browser window was closed before saving data for {company_name}. Data not saved.")
            return None
            
        # Only store data if we have successful scraping and browser is still active
        if db_collection is not None:
            try:
                # Check if company already exists in database
                company_doc = await db_collection.find_one({"company_name": company_name})
                
                if company_doc:
                    # Add new quarter data to existing company
                    # Check if this quarter already exists (shouldn't happen due to earlier check, but just to be safe)
                    existing_quarters = [metric.get("quarter", "") for metric in company_doc.get("financial_metrics", [])]
                    quarter = financial_data.get('quarter', '')
                    
                    if quarter and quarter not in existing_quarters:
                        logger.info(f"Adding new quarter {quarter} to {company_name}")
                        await update_or_insert_company_data(company_name, quarter, financial_data, db_collection)
                else:
                    # Insert new company document
                    await update_or_insert_company_data(company_data['company_name'], company_data['quarter'], company_data, db_collection)
                    logger.info(f"Added {company_name} with {len(financial_metrics)} quarters")
            except Exception as e:
                logger.error(f"Error storing data for {company_name}: {str(e)}")
        
        return company_data
    except NoSuchWindowException as e:
        logger.error(f"Browser window was closed during processing of {company_name if company_name else 'unknown stock'}")
        raise  # Re-raise to be caught by the caller
    except InvalidSessionIdException as e:
        logger.error(f"Browser session was terminated during processing of {company_name if company_name else 'unknown stock'}")
        raise  # Re-raise to be caught by the caller
    except Exception as e:
        logger.error(f"Error processing {company_name if company_name else 'unknown stock'}: {str(e)}")
        return None

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
            await update_or_insert_company_data(company_name, processed_metrics[0]['quarter'], financial_data, db_collection)
        
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
                                        "timestamp": datetime.utcnow()
                                    }
                                    
                                    # Store in database if provided
                                    if db_collection is not None:
                                        # Check for duplicates before storing
                                        quarter = financial_data.get('quarter', '')
                                        if quarter:
                                            existing_entry = await db_collection.find_one({
                                                "company_name": company_name,
                                                "financial_metrics": {
                                                    "$elemMatch": {
                                                        "quarter": quarter
                                                    }
                                                }
                                            })
                                            
                                            if existing_entry:
                                                logger.info(f"Skipping {company_name} for {quarter} - data already exists in database.")
                                                continue
                                        
                                        # Store if no duplicate found
                                        await update_or_insert_company_data(company_name, quarter, company_data, db_collection)
                                    
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
                        "timestamp": datetime.utcnow()
                    }
                    
                    # Store in database if provided
                    if db_collection is not None:
                        # Check for duplicates before storing
                        quarter = financial_data.get('quarter', '')
                        if quarter:
                            existing_entry = await db_collection.find_one({
                                "company_name": company_name,
                                "financial_metrics": {
                                    "$elemMatch": {
                                        "quarter": quarter
                                    }
                                }
                            })
                            
                            if existing_entry:
                                logger.info(f"Skipping {company_name} for {quarter} - data already exists in database.")
                                continue
                        
                        # Store if no duplicate found
                        await update_or_insert_company_data(company_name, quarter, company_data, db_collection)
                    
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
        company_name = data.get('company_name', 'unknown')
        logger.info(f"Preparing to store financial data for {company_name} in database")
        
        # Check if we have any financial metrics to work with
        financial_metrics = data.get('financial_metrics', [])
        if not financial_metrics:
            logger.warning(f"No financial metrics found for {company_name}, storing anyway")
        else:
            # Check if this company+quarter combination already exists
            for metric in financial_metrics:
                quarter = metric.get('quarter')
                if quarter:
                    existing_entry = await collection.find_one({
                        "company_name": company_name,
                        "financial_metrics": {
                            "$elemMatch": {
                                "quarter": quarter
                            }
                        }
                    })
                    
                    if existing_entry:
                        logger.info(f"Data for {company_name} in quarter {quarter} already exists. Skipping.")
                        return False
        
        # If we get here, it's safe to store the data
        await collection.insert_one(data)
        logger.info(f"Financial data for {company_name} stored successfully")
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
    Scrape earnings data by result type.
    
    Args:
        result_type (str): Result type (LR, BP, WP, PT, NT).
        db_collection (AsyncIOMotorCollection, optional): MongoDB collection to store data.
        
    Returns:
        List[Dict[str, Any]]: List of financial data dictionaries.
    """
    url_types = {
        "LR": "https://www.moneycontrol.com/markets/earnings/latest-results/?tab=LR&subType=yoy",
        "BP": "https://www.moneycontrol.com/markets/earnings/latest-results/?tab=BP&subType=yoy",
        "WP": "https://www.moneycontrol.com/markets/earnings/latest-results/?tab=WP&subType=yoy",
        "PT": "https://www.moneycontrol.com/markets/earnings/latest-results/?tab=PT&subType=yoy",
        "NT": "https://www.moneycontrol.com/markets/earnings/latest-results/?tab=NT&subType=yoy"
    }
    
    if result_type not in url_types:
        logger.error(f"Invalid result type: {result_type}. Valid types are: {', '.join(url_types.keys())}")
        return []
    
    url = url_types[result_type]
    return await scrape_moneycontrol_earnings(url, db_collection)

async def scrape_estimates_vs_actuals(url: str, db_collection: Optional[AsyncIOMotorCollection] = None) -> List[Dict[str, Any]]:
    """
    Scrape estimates vs actuals data from MoneyControl.
    
    Args:
        url (str): URL of the MoneyControl estimates vs actuals page.
        db_collection (AsyncIOMotorCollection, optional): MongoDB collection to store data.
        
    Returns:
        List[Dict[str, Any]]: List of financial data dictionaries.
    """
    results = []
    driver = setup_webdriver()
    last_card_count = 0
    no_new_content_count = 0
    max_no_new_content = 3
    
    try:
        # Login to MoneyControl
        login_success = login_to_moneycontrol(driver, target_url=url)
        if not login_success:
            logger.error("Failed to login to MoneyControl")
            return results
        
        logger.info(f"Opening page: {url}")
        driver.get(url)
        
        # Wait for estimate cards to load - updated selector
        WebDriverWait(driver, 20).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, '#estVsAct > div > ul > li:nth-child(1)'))
        )
        logger.info("Page opened successfully")
        
        # Process cards incrementally while scrolling
        while True:
            # Early check if browser is still open
            try:
                # This will raise an exception if browser is closed
                _ = driver.current_url
            except (NoSuchWindowException, InvalidSessionIdException):
                logger.error("Browser window was closed during scrolling. Scraping terminated.")
                break
            
            # Find all current estimate cards
            estimate_cards = driver.find_elements(By.CSS_SELECTOR, '#estVsAct > div > ul > li')
            current_card_count = len(estimate_cards)
            
            # Check if we have new cards
            if current_card_count == last_card_count:
                no_new_content_count += 1
                if no_new_content_count >= max_no_new_content:
                    logger.info(f"No new content after {max_no_new_content} scrolls. Ending scrape.")
                    break
            else:
                no_new_content_count = 0
                # Process only the new cards
                new_cards = estimate_cards[last_card_count:current_card_count]
                logger.info(f"Processing {len(new_cards)} new estimate cards (total: {current_card_count})")
                
                # Process each new card
                for card in new_cards:
                    try:
                        data = await process_estimate_card(card, db_collection)
                        if data:
                            results.append(data)
                    except Exception as e:
                        logger.error(f"Error processing estimate card: {str(e)}")
            
            last_card_count = current_card_count
            
            # Scroll to the last card to load more
            if estimate_cards:
                driver.execute_script("arguments[0].scrollIntoView();", estimate_cards[-1])
                time.sleep(1)  # Wait for new content to load
    
    except Exception as e:
        logger.error(f"Error during estimates scraping: {str(e)}")
    finally:
        logger.info(f"Processed a total of {last_card_count} estimate cards.")
        driver.quit()
        
    return results

async def process_estimate_card(card, db_collection: Optional[AsyncIOMotorCollection] = None) -> Optional[Dict[str, Any]]:
    """
    Process an estimate card to extract financial data.
    
    Args:
        card: HTML element containing the estimate card.
        db_collection (AsyncIOMotorCollection, optional): MongoDB collection to store data.
        
    Returns:
        Dict[str, Any]: Financial data dictionary or None if processing failed.
    """
    try:
        # Updated selectors
        company_name = card.find_element(By.CSS_SELECTOR, 'h3 a').text.strip()
        quarter = card.find_element(By.CSS_SELECTOR, 'tr th:nth-child(1)').text.strip()
        # Updated class name based on debug results
        estimates_line = card.find_element(By.CSS_SELECTOR, 'div[class*="EastimateCard_botTxtCen"]').text.strip()
        cmp = card.find_element(By.CSS_SELECTOR, 'p[class*="EastimateCard_priceTxt"]').text.strip()
        result_date = card.find_element(By.CSS_SELECTOR, 'p[class*="EastimateCard_gryTxtOne"]').text.strip()
        
        logger.info(f"Processing: {company_name}, Quarter: {quarter}, Estimates: {estimates_line}")
        
        # Create default financial data with estimates
        default_financial_data = {
            "quarter": quarter,
            "estimates": estimates_line,
            "cmp": cmp,
            "revenue": "0",
            "gross_profit": "0",
            "net_profit": "0",
            "net_profit_growth": "0%",
            "gross_profit_growth": "0%",
            "revenue_growth": "0%",
            "result_date": result_date,
            "report_type": "NA",
            "market_cap": "NA",
            "face_value": "NA",
            "book_value": "NA",
            "dividend_yield": "NA",
            "ttm_eps": "NA",
            "ttm_pe": "NA",
            "pb_ratio": "NA",
            "sector_pe": "NA",
            "piotroski_score": "NA",
            "revenue_growth_3yr_cagr": "NA",
            "net_profit_growth_3yr_cagr": "NA",
            "operating_profit_growth_3yr_cagr": "NA",
            "strengths": "NA",
            "weaknesses": "NA",
            "technicals_trend": "NA",
            "fundamental_insights": "NA",
            "fundamental_insights_description": "NA"
        }
        
        # Store the data in the database if a collection is provided
        if db_collection is not None:
            await update_or_insert_company_data(company_name, quarter, default_financial_data, db_collection)
            
        return {
            "company_name": company_name,
            "quarter": quarter,
            "estimates": estimates_line,
            "cmp": cmp,
            "result_date": result_date
        }
        
    except Exception as e:
        logger.error(f"Error processing estimate card: {str(e)}")
        return None

async def scrape_custom_url(url: str, scrape_type: str = "earnings", db_collection: Optional[AsyncIOMotorCollection] = None) -> List[Dict[str, Any]]:
    """
    Scrape data from a custom URL.
    
    Args:
        url (str): URL to scrape.
        scrape_type (str): Type of scraping to perform (earnings or estimates).
        db_collection (AsyncIOMotorCollection, optional): MongoDB collection to store data.
        
    Returns:
        List[Dict[str, Any]]: List of financial data dictionaries.
    """
    if scrape_type == "earnings":
        return await scrape_moneycontrol_earnings(url, db_collection)
    elif scrape_type == "estimates":
        return await scrape_estimates_vs_actuals(url, db_collection)
    else:
        logger.error(f"Invalid scrape_type: {scrape_type}. Valid types are 'earnings' or 'estimates'.")
        return [] 