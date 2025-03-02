"""
Main module for scraping financial data from MoneyControl.
"""
import logging
import time
import asyncio
import os
from datetime import datetime
import re
import traceback
from typing import Dict, List, Optional, Any, Union
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
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
        
        # Determine if this is a direct stock URL or an earnings list page
        if "stockpricequote" in url or "stock" in url:
            # This is a direct stock URL - use the test script approach
            logger.info("Detected direct stock URL. Using direct stock scraping approach.")
            company_data = await scrape_single_stock(driver, url, db_collection)
            if company_data:
                results.append(company_data)
        else:
            # This is an earnings list page - scrape multiple companies
            logger.info("Detected earnings list URL. Scraping multiple companies.")
            results = await scrape_earnings_list(driver, url, db_collection)
        
        logger.info(f"Successfully scraped {len(results)} companies' financial data.")
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

async def scrape_single_stock(driver, url, db_collection=None):
    """
    Scrape financial data for a single stock using direct URL.
    This approach is based on the test script method which has proven to be more reliable.
    
    Args:
        driver: Selenium WebDriver instance
        url: Direct URL to the stock page
        db_collection: Optional MongoDB collection to store data
        
    Returns:
        Dict with company financial data or None if scraping failed
    """
    try:
        # Wait for the page to load
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'body')))
        logger.info(f"Stock page loaded: {url}")
        
        # Extract company name from the page title
        try:
            page_title = driver.title
            company_name = page_title.split('|')[0].strip() if '|' in page_title else "Unknown Company"
            logger.info(f"Extracted company name: {company_name}")
        except Exception as e:
            logger.error(f"Error extracting company name: {str(e)}")
            company_name = "Unknown Company"
        
        # Save page source and screenshot for debugging if needed
        logs_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(logs_dir, exist_ok=True)
        
        try:
            screenshot_path = os.path.join(logs_dir, f"{company_name.replace(' ', '_')}_detail_page.png")
            driver.save_screenshot(screenshot_path)
            logger.info(f"Screenshot saved to {screenshot_path}")
        except Exception as e:
            logger.warning(f"Failed to save screenshot: {str(e)}")
        
        # Extract symbol from the page - try multiple approaches
        symbol = None
        try:
            # Try to find symbol in the page content
            symbol_elements = [
                driver.find_elements(By.CSS_SELECTOR, '.pcstname span'),
                driver.find_elements(By.CSS_SELECTOR, '.inid_name span'),
                driver.find_elements(By.CSS_SELECTOR, '.stockname span'),
                driver.find_elements(By.CSS_SELECTOR, '.bsedata_bx span')
            ]
            
            for elements in symbol_elements:
                if elements and len(elements) > 0:
                    for element in elements:
                        text = element.text.strip()
                        if text and '(' in text and ')' in text:
                            # Extract text between parentheses
                            symbol = text.split('(')[1].split(')')[0].strip()
                            logger.info(f"Extracted symbol from element: {symbol}")
                            break
                    if symbol:
                        break
            
            # If still no symbol, try to extract from URL
            if not symbol and 'stockpricequote' in url:
                url_parts = url.split('/')
                if len(url_parts) >= 2:
                    symbol = url_parts[-1]  # Use the last part of the URL as symbol
                    logger.info(f"Using URL last segment as symbol: {symbol}")
            
            # Finally, if we still have no symbol, use the company name
            if not symbol:
                symbol = company_name.replace(' ', '_').upper()
                logger.warning(f"No symbol found, using formatted company name: {symbol}")
            
        except Exception as e:
            logger.warning(f"Error extracting symbol: {str(e)}")
            # Fallback symbol
            symbol = company_name.replace(' ', '_').upper()
            logger.warning(f"Error occurred, using formatted company name as symbol: {symbol}")
        
        # Initialize financial data dictionary
        financial_data = {
            "quarter": None,  # We'll try to extract this from visible elements
            "cmp": None,
            "revenue": None,
            "gross_profit": None,
            "net_profit": None,
            "net_profit_growth": None,
            "gross_profit_growth": None,
            "revenue_growth": None,
            "result_date": None,
            "report_type": None,
        }
        
        # Extract stock price (CMP)
        try:
            # Try multiple selectors for CMP
            cmp_selectors = [
                '.pcstktxt span:first-child',
                '.nsecp, .bsecp',
                '.stock-price',
                '.stprice',
                '.priceinfo span',
                '.price_wrapper span',
                '.stock_price',
                '.nse_bse_sub_prices span:first-child',
                '.stock_details .price',
                '.stock-current-price'
            ]
            
            for selector in cmp_selectors:
                try:
                    cmp_elem = driver.find_element(By.CSS_SELECTOR, selector)
                    if cmp_elem and cmp_elem.text.strip():
                        financial_data["cmp"] = cmp_elem.text.strip()
                        logger.info(f"Extracted CMP with selector '{selector}': {financial_data['cmp']}")
                        break
                except Exception:
                    continue
                    
            # If still not found, try to find any element with price-like content
            if not financial_data["cmp"]:
                # Look for elements containing ₹ symbol or Rs.
                price_patterns = [
                    r'₹\s*[\d,.]+',
                    r'Rs\.\s*[\d,.]+',
                    r'INR\s*[\d,.]+',
                    r'NSE\s*:\s*[\d,.]+',
                    r'BSE\s*:\s*[\d,.]+',
                    r'CMP\s*:\s*[\d,.]+',
                    r'Price\s*:\s*[\d,.]+',
                    r'Current\s*Price\s*:\s*[\d,.]+',
                ]
                
                page_source = driver.page_source
                for pattern in price_patterns:
                    match = re.search(pattern, page_source)
                    if match:
                        financial_data["cmp"] = match.group(0)
                        logger.info(f"Extracted CMP with regex pattern: {financial_data['cmp']}")
                        break
        except Exception as e:
            logger.debug(f"Error extracting CMP: {str(e)}")
        
        # Extract quarter information
        try:
            # Try to find quarter info in the page
            quarter_selectors = [
                '.qtrheading',
                '.qtrheding',
                '.qtrending',
                'h2.mainheading',
                '.mainheading',
                '.qtrinfo'
            ]
            
            for selector in quarter_selectors:
                try:
                    quarter_elem = driver.find_element(By.CSS_SELECTOR, selector)
                    if quarter_elem:
                        quarter_text = quarter_elem.text.strip()
                        if quarter_text and ('Q1' in quarter_text or 'Q2' in quarter_text or 'Q3' in quarter_text or 'Q4' in quarter_text or 'FY' in quarter_text):
                            financial_data["quarter"] = quarter_text
                            logger.info(f"Extracted quarter: {financial_data['quarter']}")
                            break
                except Exception:
                    continue
            
            # If still no quarter info, try to extract from the URL
            if not financial_data["quarter"] and "quarter=" in url:
                quarter_match = re.search(r'quarter=([^&]+)', url)
                if quarter_match:
                    financial_data["quarter"] = quarter_match.group(1)
                    logger.info(f"Extracted quarter from URL: {financial_data['quarter']}")
            
            # If still no quarter, try to extract from page title
            if not financial_data["quarter"] and page_title and ('Q1' in page_title or 'Q2' in page_title or 'Q3' in page_title or 'Q4' in page_title or 'FY' in page_title):
                # Extract quarter pattern from title
                quarter_match = re.search(r'(Q[1-4]|FY)[-\s]?(\d{2}[-\s]?\d{2}|\d{4}[-\s]?\d{2}|\d{4})', page_title)
                if quarter_match:
                    financial_data["quarter"] = quarter_match.group(0)
                    logger.info(f"Extracted quarter from title: {financial_data['quarter']}")
        except Exception as e:
            logger.debug(f"Error extracting quarter info: {str(e)}")
        
        # Extract financial metrics using the extract_financial_data function
        try:
            # Convert driver's page source to BeautifulSoup object
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Call extract_financial_data with the soup object
            extracted_data = extract_financial_data(soup)
            if extracted_data:
                # Update financial data with extracted metrics
                for key, value in extracted_data.items():
                    if value is not None:
                        financial_data[key] = value
                        logger.info(f"Extracted {key}: {value}")
        except Exception as e:
            logger.error(f"Error extracting financial data: {str(e)}")
        
        # Extract report type (Standalone/Consolidated)
        try:
            report_type_selectors = [
                '.consotabs li.active',
                '.standalone',
                '.consolidated',
                '.repttype'
            ]
            
            for selector in report_type_selectors:
                try:
                    report_type_elem = driver.find_element(By.CSS_SELECTOR, selector)
                    if report_type_elem:
                        report_type = report_type_elem.text.strip()
                        if report_type and ('Standalone' in report_type or 'Consolidated' in report_type):
                            financial_data["report_type"] = report_type
                            logger.info(f"Extracted report type: {financial_data['report_type']}")
                            break
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Error extracting report type: {str(e)}")
        
        # Extract result date
        try:
            # Try multiple selectors for result date
            date_selectors = [
                '.resdate',
                '.resultdate',
                '.date-time',
                '.resinfo',
                '.result_date',
                '.board_meeting',
                '.meeting_date',
                '.announcement_date',
                '.date_info',
                '.result_announcement',
                '.result_info span',
                '.date_container'
            ]
            
            for selector in date_selectors:
                try:
                    date_elem = driver.find_element(By.CSS_SELECTOR, selector)
                    if date_elem:
                        date_text = date_elem.text.strip()
                        if date_text and re.search(r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{1,2}\s+[A-Za-z]+\s+\d{2,4}', date_text):
                            financial_data["result_date"] = date_text
                            logger.info(f"Extracted result date with selector '{selector}': {financial_data['result_date']}")
                            break
                except Exception:
                    continue
                    
            # If still not found, try to find any element with date-like content
            if not financial_data["result_date"]:
                # Look for date patterns in the page source
                date_patterns = [
                    r'Result\s*Date\s*:\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{1,2}\s+[A-Za-z]+\s+\d{2,4})',
                    r'Board\s*Meeting\s*Date\s*:\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{1,2}\s+[A-Za-z]+\s+\d{2,4})',
                    r'Announced\s*on\s*:\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{1,2}\s+[A-Za-z]+\s+\d{2,4})',
                    r'Published\s*on\s*:\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{1,2}\s+[A-Za-z]+\s+\d{2,4})',
                    r'Date\s*:\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{1,2}\s+[A-Za-z]+\s+\d{2,4})'
                ]
                
                page_source = driver.page_source
                for pattern in date_patterns:
                    match = re.search(pattern, page_source)
                    if match:
                        financial_data["result_date"] = match.group(1)
                        logger.info(f"Extracted result date with regex pattern: {financial_data['result_date']}")
                        break
                        
            # If still not found, try to extract from any text that looks like a date
            if not financial_data["result_date"]:
                all_text = driver.page_source
                date_patterns = [
                    r'\d{1,2}[-/]\d{1,2}[-/]\d{4}',  # DD-MM-YYYY or DD/MM/YYYY
                    r'\d{1,2}[-/]\d{1,2}[-/]\d{2}',   # DD-MM-YY or DD/MM/YY
                    r'\d{1,2}\s+[A-Za-z]+\s+\d{4}',   # DD Month YYYY
                    r'\d{1,2}\s+[A-Za-z]+\s+\d{2}'    # DD Month YY
                ]
                
                for pattern in date_patterns:
                    match = re.search(pattern, all_text)
                    if match:
                        financial_data["result_date"] = match.group(0)
                        logger.info(f"Extracted result date with general date pattern: {financial_data['result_date']}")
                        break
        except Exception as e:
            logger.debug(f"Error extracting result date: {str(e)}")
        
        # Get additional metrics from the KnowBeforeYouInvest section
        additional_metrics = await extract_know_before_invest_data(driver, company_name)
        
        if additional_metrics:
            # Update financial data with additional metrics
            for key, value in additional_metrics.items():
                if value is not None:
                    financial_data[key] = value
                    logger.info(f"Added additional metric {key}: {value}")
            
        # Check database for existing data and handle
        existing_company = None
        if db_collection is not None and financial_data.get('quarter') is not None:
            try:
                quarter = financial_data.get('quarter')
                exists = await check_company_quarter_exists(db_collection, company_name, quarter)
                
                if exists:
                    logger.info(f"{company_name} already has data for {quarter}. Updating.")
                    await db_collection.update_one(
                        {
                            "company_name": company_name,
                            "financial_metrics.quarter": quarter
                        },
                        {"$set": {"financial_metrics.$": financial_data}}
                    )
                else:
                    existing_company = await db_collection.find_one({"company_name": company_name})
                    if existing_company is not None:
                        logger.info(f"Adding new quarter data for {company_name} - {quarter}")
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
                            "timestamp": datetime.now()
                        }
                        await db_collection.insert_one(new_stock_data)
                    
                logger.info(f"Data for {company_name} processed and saved to database.")
            except Exception as e:
                logger.error(f"Database error for {company_name}: {str(e)}")
        
        # Return the stock data
        stock_data = {
            "company_name": company_name,
            "symbol": symbol,
            "financial_metrics": financial_data,
            "timestamp": datetime.now()
        }
        
        return stock_data
    except Exception as e:
        logger.error(f"Error in scrape_single_stock: {str(e)}")
        return None

async def extract_know_before_invest_data(driver, company_name):
    """
    Extract data from the KnowBeforeYouInvest section.
    This is based on the test script implementation which is more reliable.
    
    Args:
        driver: Selenium WebDriver instance
        company_name: Name of the company
        
    Returns:
        Dictionary with extracted metrics
    """
    try:
        logger.info(f"Extracting KnowBeforeYouInvest data for {company_name}")
        
        # Log current URL for verification
        logger.info(f"Current URL: {driver.current_url}")
        
        # Initialize result dictionary
        metrics = {
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
        
        # First, extract standard metrics that are usually present
        try:
            # Market cap
            market_cap_elem = driver.find_element(By.CSS_SELECTOR, 'tr:nth-child(7) td.nsemktcap.bsemktcap')
            if market_cap_elem:
                metrics["market_cap"] = market_cap_elem.text.strip()
                logger.info(f"Found market_cap: {metrics['market_cap']}")
        except Exception as e:
            logger.debug(f"Error extracting market cap: {str(e)}")
            
        try:
            # Face value
            face_value_elem = driver.find_element(By.CSS_SELECTOR, 'tr:nth-child(7) td.nsefv.bsefv')
            if face_value_elem:
                metrics["face_value"] = face_value_elem.text.strip()
                logger.info(f"Found face_value: {metrics['face_value']}")
        except Exception as e:
            logger.debug(f"Error extracting face value: {str(e)}")
            
        try:
            # Book value
            book_value_elem = driver.find_element(By.CSS_SELECTOR, 'tr:nth-child(5) td.nsebv.bsebv')
            if book_value_elem:
                metrics["book_value"] = book_value_elem.text.strip()
                logger.info(f"Found book_value: {metrics['book_value']}")
        except Exception as e:
            logger.debug(f"Error extracting book value: {str(e)}")
            
        try:
            # Dividend yield
            dividend_yield_elem = driver.find_element(By.CSS_SELECTOR, 'tr:nth-child(6) td.nsedy.bsedy')
            if dividend_yield_elem:
                metrics["dividend_yield"] = dividend_yield_elem.text.strip()
                logger.info(f"Found dividend_yield: {metrics['dividend_yield']}")
        except Exception as e:
            logger.debug(f"Error extracting dividend yield: {str(e)}")
            
        try:
            # TTM EPS
            ttm_eps_elem = driver.find_element(By.CSS_SELECTOR, 'tr:nth-child(1) td:nth-child(2) span.nseceps.bseceps')
            if ttm_eps_elem:
                metrics["ttm_eps"] = ttm_eps_elem.text.strip()
                logger.info(f"Found ttm_eps: {metrics['ttm_eps']}")
        except Exception as e:
            logger.debug(f"Error extracting TTM EPS: {str(e)}")
            
        try:
            # TTM PE
            ttm_pe_elem = driver.find_element(By.CSS_SELECTOR, 'tr:nth-child(2) td:nth-child(2) span.nsepe.bsepe')
            if ttm_pe_elem:
                metrics["ttm_pe"] = ttm_pe_elem.text.strip()
                logger.info(f"Found ttm_pe: {metrics['ttm_pe']}")
        except Exception as e:
            logger.debug(f"Error extracting TTM PE: {str(e)}")
            
        try:
            # PB Ratio
            pb_ratio_elem = driver.find_element(By.CSS_SELECTOR, 'tr:nth-child(3) td:nth-child(2) span.nsepb.bsepb')
            if pb_ratio_elem:
                metrics["pb_ratio"] = pb_ratio_elem.text.strip()
                logger.info(f"Found pb_ratio: {metrics['pb_ratio']}")
        except Exception as e:
            logger.debug(f"Error extracting PB ratio: {str(e)}")
            
        try:
            # Sector PE
            sector_pe_elem = driver.find_element(By.CSS_SELECTOR, 'tr:nth-child(4) td.nsesc_ttm.bsesc_ttm')
            if sector_pe_elem:
                metrics["sector_pe"] = sector_pe_elem.text.strip()
                logger.info(f"Found sector_pe: {metrics['sector_pe']}")
        except Exception as e:
            logger.debug(f"Error extracting sector PE: {str(e)}")
        
        # Try to find the KnowBeforeYouInvest section
        try:
            know_before_section = driver.find_element(By.ID, "knowBeforeInvest")
            logger.info("Found #knowBeforeInvest section")
            # If found, we can use more specific selectors
        except NoSuchElementException:
            logger.warning("Could not find #knowBeforeInvest section directly")
            
            # Alternative approach: Scroll down the page to make all elements visible
            logger.info("Scrolling through page to ensure all elements are visible")
            height = driver.execute_script("return document.body.scrollHeight")
            for i in range(0, height, 500):
                driver.execute_script(f"window.scrollTo(0, {i});")
                await asyncio.sleep(0.1)
        
        # Use BeautifulSoup for more flexible parsing
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Check if relevant keywords exist on the page
        keywords = ['strengths', 'weaknesses', 'technicals', 'piotroski', 'cagr']
        for keyword in keywords:
            if keyword in driver.page_source.lower():
                logger.info(f"Found keyword '{keyword}' on the page")
        
        # Extract strengths - try multiple selectors
        strengths_selectors = [
            '#swot_ls > a > strong',
            '.swotdiv .strengths strong',
            '.swotleft strong',
            '.swot_str strong',
            '.swotls strong',
            '#swot_ls strong',
            '.swot_ls strong'
        ]
        
        for selector in strengths_selectors:
            strengths_elem = soup.select(selector)
            if strengths_elem:
                metrics["strengths"] = strengths_elem[0].text.strip()
                logger.info(f"Found strengths with selector '{selector}': {metrics['strengths']}")
                break
        
        # Extract weaknesses - try multiple selectors
        weaknesses_selectors = [
            '#swot_lw > a > strong',
            '.swotdiv .weaknesses strong',
            '.swotright strong',
            '.swot_weak strong',
            '.swotlw strong',
            '#swot_lw strong',
            '.swot_lw strong'
        ]
        
        for selector in weaknesses_selectors:
            weaknesses_elem = soup.select(selector)
            if weaknesses_elem:
                metrics["weaknesses"] = weaknesses_elem[0].text.strip()
                logger.info(f"Found weaknesses with selector '{selector}': {metrics['weaknesses']}")
                break
        
        # Extract technicals trend - try multiple selectors
        technicals_selectors = [
            '#techAnalysis a[style*="flex"]',
            '.techDiv p strong',
            '.techAnls strong',
            '.technicals strong', 
            '#dMoving_Averages strong'
        ]
        
        for selector in technicals_selectors:
            try:
                technicals_elem = soup.select(selector)
                if technicals_elem:
                    metrics["technicals_trend"] = technicals_elem[0].text.strip()
                    logger.info(f"Found technicals_trend with selector '{selector}': {metrics['technicals_trend']}")
                    break
            except Exception as e:
                logger.debug(f"Error with selector '{selector}': {str(e)}")
        
        # Extract Piotroski score - try multiple selectors
        piotroski_selectors = [
            'div:nth-child(2) div.fpioi div.nof',
            '.piotroski_score',
            '.pio_score span',
            '#piotroskiScore',
            '.fpioi .nof',
            '#knowBeforeInvest .fpioi .nof'
        ]
        
        for selector in piotroski_selectors:
            piotroski_elem = soup.select(selector)
            if piotroski_elem:
                metrics["piotroski_score"] = piotroski_elem[0].text.strip()
                logger.info(f"Found piotroski_score with selector '{selector}': {metrics['piotroski_score']}")
                break
        
        # Find all tables on the page to extract CAGR data
        tables = soup.find_all('table')
        logger.info(f"Found {len(tables)} tables on the page")
        
        # Extract CAGR data from tables
        for i, table in enumerate(tables[:30]):  # Limit to first 30 tables for performance
            if 'CAGR' in str(table) or 'cagr' in str(table).lower() or 'Grwth' in str(table):
                logger.info(f"Table {i+1} might contain CAGR data")
                
                # Look for profit growth 3yr CAGR
                if 'Profit Grwth 3Yr CAGR' in str(table) or 'Profit Growth 3Yr CAGR' in str(table):
                    try:
                        profit_cagr_cell = table.find('td', string=lambda s: s and 'Profit Grwth 3Yr CAGR' in s)
                        if profit_cagr_cell:
                            next_cell = profit_cagr_cell.find_next('td')
                            if next_cell:
                                metrics["net_profit_growth_3yr_cagr"] = next_cell.text.strip()
                                logger.info(f"Found net_profit_growth_3yr_cagr: {metrics['net_profit_growth_3yr_cagr']}")
                    except Exception as e:
                        logger.debug(f"Error extracting profit CAGR: {str(e)}")
                
                # Look for sales growth 3yr CAGR
                if 'Sales Grwth 3Yr CAGR' in str(table) or 'Sales Growth 3Yr CAGR' in str(table):
                    try:
                        sales_cagr_cell = table.find('td', string=lambda s: s and ('Sales Grwth 3Yr CAGR' in s or 'Sales Growth 3Yr CAGR' in s))
                        if sales_cagr_cell:
                            next_cell = sales_cagr_cell.find_next('td')
                            if next_cell:
                                metrics["revenue_growth_3yr_cagr"] = next_cell.text.strip()
                                logger.info(f"Found revenue_growth_3yr_cagr: {metrics['revenue_growth_3yr_cagr']}")
                    except Exception as e:
                        logger.debug(f"Error extracting sales CAGR: {str(e)}")
        
        # Log extraction results
        for key, value in metrics.items():
            if value is not None:
                logger.info(f"Successfully extracted {key}: {value}")
            else:
                logger.debug(f"Could not extract {key}")
        
        return metrics
    except Exception as e:
        logger.error(f"Error in extract_know_before_invest_data: {str(e)}")
        return {}

async def scrape_earnings_list(driver, url, db_collection=None, max_companies=None):
    """
    Scrape earnings list from MoneyControl and extract detailed stock metrics for each company.
    
    Args:
        driver: Selenium WebDriver instance
        url: URL of the earnings list page
        db_collection: MongoDB collection to store the results
        max_companies: Maximum number of companies to scrape (default None = all companies)
        
    Returns:
        List of dictionaries containing company data
    """
    logger.info("Waiting for result cards to load...")
    try:
        # Wait for result cards to load - try different possible selectors
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "li.rapidResCardWeb_gryCard__hQigs"))
            )
            logger.info("Page loaded successfully with new card selector")
        except TimeoutException:
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.resultCard"))
                )
                logger.info("Page loaded successfully with primary selector")
            except TimeoutException:
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.tab_container_results"))
                    )
                    logger.info("Page loaded successfully with alternate selector")
                except TimeoutException:
                    logger.error("Failed to load page with any selector")
                    return []

        # Scroll to load all dynamic content
        logger.info("Scrolling page to load all content")
        await scroll_page(driver)
        
        # Find all result cards - try multiple selectors
        result_cards = driver.find_elements(By.CSS_SELECTOR, "li.rapidResCardWeb_gryCard__hQigs")
        if not result_cards:
            logger.info("Could not find cards with primary selector, trying alternates...")
            result_cards = driver.find_elements(By.CSS_SELECTOR, "div.resultCard")
            if not result_cards:
                result_cards = driver.find_elements(By.CSS_SELECTOR, "div.tab_container_results div.resultCardComp")
        
        logger.info(f"Found {len(result_cards)} result cards to process")
        
        # Limit the number of companies to process if max_companies is specified
        if max_companies is not None:
            companies_to_process = min(len(result_cards), max_companies)
            logger.info(f"Will process {companies_to_process} companies (max_companies={max_companies})")
        else:
            companies_to_process = len(result_cards)
            logger.info(f"Will process all {companies_to_process} companies")
        
        # Extract basic financial data from result cards
        logger.info("Extracting basic financial data from result cards")
        
        results = []
        for i, card in enumerate(result_cards[:companies_to_process], 1):
            logger.info(f"Processing card {i} of {companies_to_process}")
            try:
                # Extract company name - try multiple selectors to improve reliability
                company_name = None
                try:
                    # New selector for rapid results cards
                    company_name = card.find_element(By.CSS_SELECTOR, "h3.rapidResCardWeb_blkTxtOne__cigbf a").text.strip()
                except NoSuchElementException:
                    try:
                        company_name = card.find_element(By.CSS_SELECTOR, "a.resultTitle").text.strip()
                    except NoSuchElementException:
                        try:
                            company_name = card.find_element(By.CSS_SELECTOR, "h2.resultTitle").text.strip()
                        except NoSuchElementException:
                            try:
                                company_name = card.find_element(By.CSS_SELECTOR, "span.resultTitle").text.strip()
                            except NoSuchElementException:
                                try:
                                    # Try to find any heading element within the card
                                    heading_elements = card.find_elements(By.CSS_SELECTOR, "h1, h2, h3, h4, h5, strong, b")
                                    if heading_elements:
                                        company_name = heading_elements[0].text.strip()
                                except Exception:
                                    company_name = "Unknown Company"
                
                if not company_name or company_name == "":
                    company_name = "Unknown Company"
                
                # Extract URL
                stock_url = None
                try:
                    # New selector for rapid results cards
                    stock_url = card.find_element(By.CSS_SELECTOR, "h3.rapidResCardWeb_blkTxtOne__cigbf a").get_attribute("href")
                except NoSuchElementException:
                    try:
                        stock_url = card.find_element(By.CSS_SELECTOR, "a.resultTitle").get_attribute("href")
                    except NoSuchElementException:
                        try:
                            # Find any link that might contain the stock URL
                            links = card.find_elements(By.TAG_NAME, "a")
                            if links:
                                for link in links:
                                    href = link.get_attribute("href")
                                    if "stockpricequote" in href:
                                        stock_url = href
                                        break
                        except Exception as e:
                            logger.error(f"Error extracting stock URL: {e}")

                if not stock_url:
                    logger.warning(f"Could not find stock URL for {company_name}, skipping")
                    continue
                
                logger.info(f"Processing stock: {company_name} with URL: {stock_url}")
                
                # Extract financial data from result card - these are preliminary and will be replaced by detailed stock page scraping
                financial_data = {}
                
                # Try multiple selectors for quarter info
                quarter_info = None
                try:
                    # Try to extract quarter info from table header
                    quarter_elements = card.find_elements(By.CSS_SELECTOR, "table.commonTable th")
                    if quarter_elements:
                        quarter_info = quarter_elements[0].text.strip()
                        financial_data["quarter"] = quarter_info
                except Exception as e:
                    logger.warning(f"Error extracting quarter info: {e}")
                
                # Try to extract preliminary financial metrics using the table data
                try:
                    rows = card.find_elements(By.CSS_SELECTOR, "table.commonTable tbody tr")
                    if rows:
                        for row in rows:
                            cells = row.find_elements(By.TAG_NAME, "td")
                            if len(cells) >= 4:
                                metric_name = cells[0].text.strip().lower()
                                if "revenue" in metric_name:
                                    financial_data["revenue"] = cells[1].text.strip()
                                elif "net profit" in metric_name:
                                    financial_data["net_profit"] = cells[1].text.strip()
                                elif "gross profit" in metric_name:
                                    financial_data["gross_profit"] = cells[1].text.strip()
                except Exception as e:
                    logger.warning(f"Error extracting table data: {e}")
                
                # Get date from the card if available
                try:
                    date_element = card.find_element(By.CSS_SELECTOR, "p.rapidResCardWeb_gryTxtOne__mEhU_")
                    if date_element:
                        financial_data["date"] = date_element.text.strip()
                except Exception:
                    pass
                
                # Get current price if available
                try:
                    price_element = card.find_element(By.CSS_SELECTOR, "p.rapidResCardWeb_priceTxt___5MvY")
                    if price_element:
                        price_text = price_element.text.strip().split()[0]
                        financial_data["current_price"] = price_text
                except Exception:
                    pass
                
                # Get standalone/consolidated info
                try:
                    bottom_text = card.find_element(By.CSS_SELECTOR, "p.rapidResCardWeb_bottomText__p8YzI")
                    if bottom_text:
                        financial_data["report_type"] = bottom_text.text.strip()
                except Exception:
                    pass

                # Check if we already have this company and quarter in the database before proceeding
                if db_collection is not None and financial_data.get("quarter"):
                    try:
                        quarter = financial_data.get("quarter")
                        exists = await check_company_quarter_exists(db_collection, company_name, quarter)
                        if exists:
                            logger.info(f"Company {company_name} already has data for quarter {quarter}. Skipping.")
                            continue
                    except Exception as e:
                        logger.error(f"Error checking for existing company data: {e}")

                # Now navigate to the stock page and extract more detailed data
                logger.info(f"Navigating to stock URL: {stock_url}")
                try:
                    # Store current window handle
                    main_window = driver.current_window_handle
                    
                    # Open a new tab with the stock URL
                    logger.info("Opening new tab for stock details")
                    driver.execute_script("window.open(arguments[0], '_blank');", stock_url)
                    
                    # Switch to the new tab
                    windows = driver.window_handles
                    driver.switch_to.window(windows[-1])
                    
                    # Wait for the stock page to load
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.inid_name, h1.pcstname"))
                    )
                    
                    # Extract more detailed data using scrape_single_stock
                    detailed_data = await scrape_single_stock(driver, stock_url)
                    
                    # Close the tab and switch back to the main window
                    logger.info("Closing stock details tab and returning to main page")
                    driver.close()
                    driver.switch_to.window(main_window)
                    
                    # Merge preliminary and detailed data
                    if detailed_data:
                        # Keep the original data we scraped from the earnings page
                        preliminary_data = financial_data.copy()
                        
                        # Update with detailed data but preserve earnings-specific data
                        financial_data.update(detailed_data)
                        
                        # Make sure we keep the quarter info from the earnings page
                        if "quarter" in preliminary_data and preliminary_data["quarter"]:
                            financial_data["quarter"] = preliminary_data["quarter"]
                    
                    # Extract symbol from the URL if it's not in the detailed data
                    symbol = None
                    if "symbol" in financial_data and financial_data["symbol"]:
                        symbol = financial_data["symbol"]
                    else:
                        # Try to extract from URL
                        match = re.search(r'/([^/]+)$', stock_url)
                        if match:
                            potential_symbol = match.group(1)
                            # Check if it contains letters (some URLs end with IDs)
                            if re.search(r'[a-zA-Z]', potential_symbol):
                                symbol = potential_symbol
                
                    # Prepare the document to be inserted
                    document = {
                        "name": company_name,
                        "symbol": symbol,
                        "url": stock_url,
                        "financial_data": financial_data,
                        "scraped_at": datetime.now(),
                        "source": "earnings_list"
                    }
                    
                    # Insert into MongoDB if collection is provided
                    if db_collection is not None:
                        # First, check if we already have this company in the database
                        existing_company = await db_collection.find_one({"company_name": company_name})
                        quarter = financial_data.get("quarter")
                        
                        if existing_company is not None:
                            # Company exists - check if it has the right structure
                            if "financial_metrics" in existing_company:
                                # Has the right structure - check if this quarter already exists
                                exists = await check_company_quarter_exists(db_collection, company_name, quarter)
                                
                                if exists and quarter:
                                    # Update the existing quarter
                                    logger.info(f"Updating existing quarter {quarter} for {company_name}")
                                    await db_collection.update_one(
                                        {
                                            "company_name": company_name, 
                                            "financial_metrics.quarter": quarter
                                        },
                                        {"$set": {"financial_metrics.$": financial_data}}
                                    )
                                else:
                                    # Add as new quarter
                                    logger.info(f"Adding new quarter data for {company_name}")
                                    await db_collection.update_one(
                                        {"company_name": company_name},
                                        {"$push": {"financial_metrics": financial_data}}
                                    )
                            else:
                                # Has the old structure - convert to new structure
                                logger.info(f"Converting to new structure for {company_name}")
                                await db_collection.update_one(
                                    {"company_name": company_name},
                                    {"$set": {
                                        "symbol": symbol,
                                        "financial_metrics": [financial_data],
                                        "timestamp": datetime.now()
                                    }}
                                )
                        else:
                            # Create new company document with the right structure
                            logger.info(f"Creating new company document for {company_name}")
                            new_document = {
                                "company_name": company_name,
                                "symbol": symbol,
                                "financial_metrics": [financial_data],
                                "timestamp": datetime.now()
                            }
                            await db_collection.insert_one(new_document)
                    
                    # Add to results list
                    results.append({
                        "company_name": company_name,
                        "symbol": symbol,
                        "financial_metrics": financial_data,
                        "timestamp": datetime.now()
                    })
                    
                    # Navigate back to the earnings list page - No need to navigate back since we're using tabs
                    # driver.get(url)
                    try:
                        # Make sure we're still on the right page
                        WebDriverWait(driver, 5).until(
                            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "li.rapidResCardWeb_gryCard__hQigs, div.resultCard, div.tab_container_results div.resultCardComp"))
                        )
                    except Exception as e:
                        logger.warning(f"Main page check failed, refreshing: {e}")
                        driver.get(url)
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "li.rapidResCardWeb_gryCard__hQigs, div.resultCard, div.tab_container_results div.resultCardComp"))
                        )
                    
                except Exception as e:
                    logger.error(f"Error during detailed scraping for {company_name}: {e}")
                    # If we failed to get detailed data, still add the basic data
                    document = {
                        "name": company_name,
                        "symbol": None,
                        "url": stock_url,
                        "financial_data": financial_data,
                        "scraped_at": datetime.now(),
                        "source": "earnings_list",
                        "error": str(e)
                    }
                    
                    if db_collection is not None:
                        await db_collection.update_one(
                            {"url": stock_url},
                            {"$set": document},
                            upsert=True
                        )
                    
                    results.append(document)
                    
                    # Make sure we're back on the main window if an error occurred
                    try:
                        if driver.current_window_handle != main_window:
                            driver.close()
                            driver.switch_to.window(main_window)
                    except Exception as tab_e:
                        logger.warning(f"Error handling window after exception: {tab_e}")
                        # If we can't recover, try to get back to the earnings page
                        try:
                            driver.get(url)
                            await asyncio.sleep(3)  # Simple wait for page to reload
                        except Exception as recover_e:
                            logger.error(f"Failed to recover main page: {recover_e}")
            
            except Exception as e:
                logger.error(f"Error processing card {i}: {e}")
                
        return results
    
    except Exception as e:
        logger.error(f"Error in scrape_earnings_list: {e}")
        traceback.print_exc()
        return []

async def scroll_page(driver) -> None:
    """
    Scrolls the page to load all dynamic content.
    
    Args:
        driver: Selenium WebDriver instance.
    """
    try:
        logger.info("Starting page scrolling to load dynamic content")
        last_height = driver.execute_script("return document.body.scrollHeight")
        scroll_attempts = 0
        max_scroll_attempts = 5  # Reduced from 10 to improve performance
        
        while scroll_attempts < max_scroll_attempts:
            # Scroll down to bottom
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            # Wait to load page - reduced wait time to improve performance
            await asyncio.sleep(1)
            
            # Calculate new scroll height and compare with last scroll height
            new_height = driver.execute_script("return document.body.scrollHeight")
            
            if new_height == last_height:
                logger.info(f"Scrolling complete after {scroll_attempts + 1} attempts")
                break
            
            last_height = new_height
            scroll_attempts += 1
            logger.debug(f"Scroll attempt {scroll_attempts}/{max_scroll_attempts}")
        
        # Scroll back to top for better processing
        driver.execute_script("window.scrollTo(0, 0);")
        await asyncio.sleep(0.5)
        
    except Exception as e:
        logger.error(f"Error during page scrolling: {str(e)}")
        # Continue with whatever content was loaded

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

async def check_company_quarter_exists(db_collection, company_name, quarter):
    """
    Check if data for a specific company and quarter already exists in the database.
    
    Args:
        db_collection: MongoDB collection
        company_name: Name of the company
        quarter: Quarter to check
        
    Returns:
        bool: True if the company and quarter combination exists, False otherwise
    """
    if not db_collection or not company_name or not quarter:
        return False
        
    try:
        # Find the company document
        existing_company = await db_collection.find_one({"company_name": company_name})
        
        if existing_company and "financial_metrics" in existing_company:
            # Check if this quarter exists in the financial metrics
            existing_quarters = [
                metric.get("quarter") for metric in existing_company.get("financial_metrics", [])
                if metric.get("quarter")
            ]
            
            # Check if the quarter exists (exact match)
            if quarter in existing_quarters:
                logger.info(f"Company {company_name} already has data for quarter {quarter}")
                return True
                
            # Also check for similar quarters (sometimes format might be slightly different)
            quarter_pattern = re.sub(r'\s+', '', quarter).lower()
            for existing_quarter in existing_quarters:
                existing_pattern = re.sub(r'\s+', '', existing_quarter).lower()
                if quarter_pattern == existing_pattern:
                    logger.info(f"Company {company_name} already has data for similar quarter {existing_quarter} (requested: {quarter})")
                    return True
                    
        return False
    except Exception as e:
        logger.error(f"Error checking for existing company quarter: {str(e)}")
        return False 