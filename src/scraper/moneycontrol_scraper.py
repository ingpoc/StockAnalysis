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
        
        logger.info("Login successful. Proceeding with scraping.")
        
        # Add debug information about the current page
        try:
            logger.info(f"Current URL after login: {driver.current_url}")
            logger.info(f"Page title: {driver.title}")
            
            # Take a screenshot for debugging
            screenshot_path = "debug_screenshot.png"
            driver.save_screenshot(screenshot_path)
            logger.info(f"Saved debug screenshot to {screenshot_path}")
            
            # Log page source length for debugging
            page_source = driver.page_source
            logger.info(f"Page source length: {len(page_source)} characters")
            
            # Save page source for debugging
            with open("debug_page_source.html", "w", encoding="utf-8") as f:
                f.write(page_source)
            logger.info("Saved page source to debug_page_source.html")
        except Exception as e:
            logger.error(f"Error capturing debug information: {str(e)}")
        
        # Determine if it's a direct stock URL or an earnings list
        if "stockpricequote" in url or "/stock/" in url:
            logger.info("Detected direct stock URL. Scraping single stock.")
            stock_data = await scrape_single_stock(driver, url, db_collection)
            if stock_data:
                results.append(stock_data)
                logger.info(f"Successfully scraped data for {stock_data.get('company_name', 'unknown company')}")
        else:
            logger.info("Detected earnings list URL. Scraping multiple stocks.")
            results = await scrape_earnings_list(driver, url, db_collection)
        
        logger.info(f"Successfully scraped {len(results)} companies' financial data.")
        
        # Now save all collected data to the database
        if db_collection is not None and results:
            logger.info(f"Saving {len(results)} companies to database")
            for company_data in results:
                await save_to_database(db_collection, company_data)
            
            # Verify data was saved to database
            saved_count = 0
            for result in results:
                company_name = result.get("company_name")
                quarter = result.get("financial_metrics", {}).get("quarter")
                
                if company_name and quarter:
                    # Check if the data exists in the database
                    exists = await check_company_quarter_exists(db_collection, company_name, quarter)
                    if exists:
                        saved_count += 1
                    else:
                        logger.warning(f"Data for {company_name} ({quarter}) may not have been saved to the database.")
            
            logger.info(f"Verified {saved_count} out of {len(results)} companies were saved to the database.")
        
        return results
    
    except WebDriverException as e:
        logger.error(f"WebDriver error during scraping: {str(e)}")
        if "Connection refused" in str(e):
            logger.error("Connection to browser was refused. The browser may have been closed.")
        return []
    except Exception as e:
        logger.error(f"Error during scraping: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return []
    finally:
        if driver:
            try:
                logger.info("Closing WebDriver")
                driver.quit()
                logger.info("WebDriver closed")
            except Exception as e:
                logger.error(f"Error closing WebDriver: {str(e)}")
                
                # Force kill Chrome processes if necessary
                try:
                    import psutil
                    for proc in psutil.process_iter(['pid', 'name']):
                        try:
                            if 'chrome' in proc.info['name'].lower() or 'chromedriver' in proc.info['name'].lower():
                                logger.info(f"Killing process: {proc.info['name']} (PID: {proc.info['pid']})")
                                proc.kill()
                        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                            pass
                except ImportError:
                    logger.warning("psutil not installed, cannot force kill Chrome processes")
                except Exception as e:
                    logger.error(f"Error killing Chrome processes: {str(e)}")

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
                '.qtrinfo',
                '.qtrtxt',
                '.quarterheading',
                '.quarter-heading',
                '.quarter_heading',
                '.quarter-info',
                '.quarter_info'
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
            if not financial_data.get("quarter") and "quarter=" in url:
                quarter_match = re.search(r'quarter=([^&]+)', url)
                if quarter_match:
                    financial_data["quarter"] = quarter_match.group(1)
                    logger.info(f"Extracted quarter from URL: {financial_data['quarter']}")
            
            # If still no quarter, try to extract from page title
            if not financial_data.get("quarter") and page_title and ('Q1' in page_title or 'Q2' in page_title or 'Q3' in page_title or 'Q4' in page_title or 'FY' in page_title):
                # Extract quarter pattern from title
                quarter_match = re.search(r'(Q[1-4]|FY)[-\s]?(\d{2}[-\s]?\d{2}|\d{4}[-\s]?\d{2}|\d{4})', page_title)
                if quarter_match:
                    financial_data["quarter"] = quarter_match.group(0)
                    logger.info(f"Extracted quarter from title: {financial_data['quarter']}")
            
            # If still no quarter, try to extract from any text on the page
            if not financial_data.get("quarter"):
                # Look for any text containing quarter information
                page_source = driver.page_source
                quarter_patterns = [
                    r'(Q[1-4]|FY)[-\s]?(\d{2}[-\s]?\d{2}|\d{4}[-\s]?\d{2}|\d{4})',
                    r'(Quarter\s+[1-4]|First Quarter|Second Quarter|Third Quarter|Fourth Quarter)',
                    r'(Q[1-4])[-\s]?(FY\s?\d{2}[-\s]?\d{2}|\d{4}[-\s]?\d{2}|\d{4})'
                ]
                
                for pattern in quarter_patterns:
                    matches = re.findall(pattern, page_source)
                    if matches:
                        if isinstance(matches[0], tuple):
                            financial_data["quarter"] = ''.join(matches[0])
                        else:
                            financial_data["quarter"] = matches[0]
                        logger.info(f"Extracted quarter from page source: {financial_data['quarter']}")
                        break
            
            # If still no quarter, use a default based on current date
            if not financial_data.get("quarter"):
                current_date = datetime.now()
                month = current_date.month
                year = current_date.year
                
                # Determine fiscal quarter based on month
                if 4 <= month <= 6:  # Apr-Jun: Q1
                    quarter_num = 1
                elif 7 <= month <= 9:  # Jul-Sep: Q2
                    quarter_num = 2
                elif 10 <= month <= 12:  # Oct-Dec: Q3
                    quarter_num = 3
                else:  # Jan-Mar: Q4
                    quarter_num = 4
                    
                # Format as "Q1 FY23-24" style
                if month >= 4:  # New fiscal year starts in April
                    fy_start = year
                    fy_end = year + 1
                else:
                    fy_start = year - 1
                    fy_end = year
                    
                fy_start_short = str(fy_start)[-2:]
                fy_end_short = str(fy_end)[-2:]
                
                financial_data["quarter"] = f"Q{quarter_num} FY{fy_start_short}-{fy_end_short}"
                logger.info(f"Using default quarter based on current date: {financial_data['quarter']}")
                
        except Exception as e:
            logger.error(f"Error extracting quarter information: {str(e)}")
        
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

async def scrape_earnings_list(driver, url, db_collection=None):
    """
    Scrape financial data from the MoneyControl earnings list page.
    
    Args:
        driver: Selenium WebDriver instance
        url: URL of the earnings list page
        db_collection: Optional MongoDB collection to store data
        
    Returns:
        List of dictionaries containing company financial data
    """
    results = []
    
    try:
        logger.info(f"Scraping earnings list from URL: {url}")
        
        # Wait for the page to load
        logger.info("Waiting for page to load")
        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'body'))
            )
            logger.info("Page loaded successfully")
        except TimeoutException:
            logger.error("Timeout waiting for page to load")
            return []
        
        # Scroll to load all content
        logger.info("Scrolling page to load all content")
        await scroll_page(driver)
        
        # Get the page source
        logger.info("Getting page source")
        page_source = driver.page_source
        
        # Parse with BeautifulSoup
        logger.info("Parsing page with BeautifulSoup")
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Try different selectors for the result cards
        selectors = [
            'li.rapidResCardWeb_gryCard__hQigs',
            'li.gryCard',
            'div.card',
            'div.result-card',
            'li[class*="gryCard"]',
            'div[class*="card"]',
            'table.mctable1 tr',  # Try table rows as well
            'div.FL.PR20 table tr'  # Another possible table selector
        ]
        
        found_elements = False
        for selector in selectors:
            logger.info(f"Trying selector: {selector}")
            elements = soup.select(selector)
            logger.info(f"Found {len(elements)} elements with selector '{selector}'")
            
            if elements:
                found_elements = True
                logger.info(f"Using selector '{selector}' with {len(elements)} elements")
                
                # Log the first element for debugging
                if elements:
                    first_element = elements[0]
                    logger.info(f"First element: {first_element.name} with classes {first_element.get('class', [])}")
                    logger.info(f"First element text snippet: {first_element.text[:100]}...")
                
                # Get all elements from the page
                web_elements = []
                try:
                    # Convert the selector to a CSS selector for Selenium
                    css_selector = selector
                    web_elements = driver.find_elements(By.CSS_SELECTOR, css_selector)
                    logger.info(f"Found {len(web_elements)} web elements with selector '{css_selector}'")
                except Exception as e:
                    logger.error(f"Error finding web elements: {str(e)}")
                
                # Process each element
                for i, element in enumerate(elements):
                    try:
                        company_data = extract_company_data(element, selector)
                        if not company_data:
                            logger.warning(f"Could not extract company data from element {i+1}")
                            continue
                        
                        company_name = company_data.get('company_name')
                        company_url = company_data.get('url')
                        financial_metrics = company_data.get('financial_metrics', {})
                        quarter = financial_metrics.get('quarter')
                        
                        if not company_name:
                            logger.warning(f"Missing company name for element {i+1}")
                            continue
                        
                        if not quarter:
                            # Try to extract quarter from the page
                            logger.warning(f"Missing quarter for {company_name}, trying to extract from page")
                            
                            # Look for quarter in the page title or headers
                            try:
                                page_title = driver.title
                                quarter_match = re.search(r'Q[1-4]\s+FY\d{2}-\d{2}', page_title)
                                if quarter_match:
                                    quarter = quarter_match.group(0)
                                    financial_metrics['quarter'] = quarter
                                    logger.info(f"Extracted quarter from page title: {quarter}")
                                else:
                                    # Try to find in headers
                                    headers = driver.find_elements(By.CSS_SELECTOR, 'h1, h2, h3, h4, h5')
                                    for header in headers:
                                        text = header.text
                                        quarter_match = re.search(r'Q[1-4]\s+FY\d{2}-\d{2}', text)
                                        if quarter_match:
                                            quarter = quarter_match.group(0)
                                            financial_metrics['quarter'] = quarter
                                            logger.info(f"Extracted quarter from header: {quarter}")
                                            break
                            except Exception as e:
                                logger.debug(f"Error extracting quarter from page: {str(e)}")
                        
                        if not quarter:
                            # If still no quarter, use a default based on current date
                            from datetime import datetime
                            now = datetime.now()
                            year = now.year
                            month = now.month
                            
                            # Determine fiscal quarter based on month
                            if month >= 1 and month <= 3:
                                q = 'Q3'
                            elif month >= 4 and month <= 6:
                                q = 'Q4'
                            elif month >= 7 and month <= 9:
                                q = 'Q1'
                            else:
                                q = 'Q2'
                            
                            # Determine fiscal year
                            if month >= 4:
                                fy = f"FY{str(year)[2:]}-{str(year+1)[2:]}"
                            else:
                                fy = f"FY{str(year-1)[2:]}-{str(year)[2:]}"
                            
                            quarter = f"{q} {fy}"
                            financial_metrics['quarter'] = quarter
                            logger.info(f"Using default quarter for {company_name}: {quarter}")
                        
                        logger.info(f"Processing company: {company_name}, Quarter: {quarter}")
                        
                        # Check if this company's quarter data already exists in the database
                        skip_company = False
                        if db_collection is not None:
                            exists = await check_company_quarter_exists(db_collection, company_name, quarter)
                            if exists:
                                logger.info(f"Skipping {company_name} ({quarter}) - data already exists in database")
                                skip_company = True
                        
                        # If we're skipping this company, continue to the next one
                        if skip_company:
                            continue
                        
                        # If we have web elements and a URL, click on the link to get more details
                        if web_elements and i < len(web_elements) and company_url:
                            logger.info(f"Opening detail page for {company_name}")
                            
                            # Store the current window handle
                            main_window = driver.current_window_handle
                            
                            try:
                                # Open link in a new tab
                                driver.execute_script("window.open(arguments[0], '_blank');", company_url)
                                
                                # Wait for the new tab to open and switch to it
                                await asyncio.sleep(1)
                                
                                # Switch to the new tab (last window handle)
                                window_handles = driver.window_handles
                                driver.switch_to.window(window_handles[-1])
                                
                                # Wait for the detail page to load
                                try:
                                    WebDriverWait(driver, 30).until(
                                        EC.presence_of_element_located((By.CSS_SELECTOR, 'body'))
                                    )
                                    logger.info(f"Detail page loaded for {company_name}")
                                    
                                    # Extract metrics from the detail page
                                    stock_metrics = await extract_stock_metrics(driver, company_name)
                                    
                                    # Merge financial metrics from the result card with stock metrics
                                    # If stock metrics has financial data that's missing in the result card, use it
                                    for key in ['revenue', 'gross_profit', 'net_profit', 'net_profit_growth', 'revenue_growth', 'gross_profit_growth', 'report_type', 'result_date']:
                                        if key in stock_metrics and stock_metrics[key] and (key not in financial_metrics or not financial_metrics[key]):
                                            financial_metrics[key] = stock_metrics[key]
                                            logger.info(f"Using stock metric for {key}: {stock_metrics[key]}")
                                    
                                    # Add metrics to company data
                                    company_data['stock_metrics'] = stock_metrics
                                    company_data['financial_metrics'] = financial_metrics
                                    
                                    # Log the metrics found
                                    logger.info(f"Extracted {sum(1 for v in stock_metrics.values() if v is not None)} metrics for {company_name}")
                                    
                                except TimeoutException:
                                    logger.error(f"Timeout waiting for detail page to load for {company_name}")
                                
                                # Close the tab and switch back to the main window
                                driver.close()
                                driver.switch_to.window(main_window)
                                
                            except Exception as e:
                                logger.error(f"Error processing detail page for {company_name}: {str(e)}")
                                import traceback
                                logger.error(f"Traceback: {traceback.format_exc()}")
                                # Make sure we're back on the main window
                                try:
                                    driver.switch_to.window(main_window)
                                except:
                                    pass
                        
                        # Add to results
                        results.append(company_data)
                            
                    except Exception as e:
                        logger.error(f"Error extracting data from element {i+1}: {str(e)}")
                        import traceback
                        logger.error(f"Traceback: {traceback.format_exc()}")
                
                # Break after finding a working selector
                break
        
        if not found_elements:
            logger.warning("No elements found with any of the selectors")
            
            # Save the page source for offline analysis
            with open("failed_scrape_page.html", "w", encoding="utf-8") as f:
                f.write(page_source)
            logger.info("Saved failed scrape page source to failed_scrape_page.html")
        
        # Now that we have collected all data, save it to the database
        if db_collection is not None and results:
            logger.info(f"Saving {len(results)} companies to database")
            for company_data in results:
                await save_to_database(db_collection, company_data)
            
            # Verify data was saved to database
            saved_count = 0
            for result in results:
                company_name = result.get("company_name")
                quarter = result.get("financial_metrics", {}).get("quarter")
                
                if company_name and quarter:
                    # Check if the data exists in the database
                    exists = await check_company_quarter_exists(db_collection, company_name, quarter)
                    if exists:
                        saved_count += 1
                    else:
                        logger.warning(f"Data for {company_name} ({quarter}) may not have been saved to the database.")
            
            logger.info(f"Verified {saved_count} out of {len(results)} companies were saved to the database.")
        
        logger.info(f"Scraped {len(results)} companies from earnings list")
        return results
    
    except Exception as e:
        logger.error(f"Error scraping earnings list: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

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
    if db_collection is None or not company_name or not quarter:
        logger.warning(f"Cannot check if company exists: db_collection={db_collection is not None}, company_name={company_name}, quarter={quarter}")
        return False
        
    try:
        # Find the company document with the specific quarter
        query = {
            "company_name": company_name,
            "financial_metrics.quarter": quarter
        }
        
        # Use count_documents to check if any matching documents exist
        count = await db_collection.count_documents(query)
        
        # Return True if at least one document was found
        exists = count > 0
        
        if exists:
            logger.info(f"Found existing data for {company_name} ({quarter}) in database")
        else:
            logger.info(f"No existing data found for {company_name} ({quarter}) in database")
            
        return exists
    except Exception as e:
        logger.error(f"Error checking if company {company_name} exists for quarter {quarter}: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False 

def extract_company_data(element, selector):
    """
    Extract company data from a BeautifulSoup element.
    
    Args:
        element: BeautifulSoup element containing company data
        selector: Selector used to find this element
        
    Returns:
        Dictionary containing company data or None if extraction fails
    """
    try:
        company_name = None
        company_url = None
        financial_metrics = {}
        
        # Extract company name and URL - using more generic selectors
        # Look for any link that might contain the company name
        company_links = element.select('a')
        if company_links:
            # Usually the first link or a link with a specific class contains the company name
            for link in company_links:
                # Skip links that are likely not company names (too short or contain specific words)
                link_text = link.text.strip()
                if len(link_text) > 3 and not any(x in link_text.lower() for x in ['view', 'more', 'details', 'login']):
                    company_name = link_text
                    company_url = link.get('href')
                    if company_url and not company_url.startswith('http'):
                        company_url = f"https://www.moneycontrol.com{company_url}"
                    logger.info(f"Found company name: {company_name}, URL: {company_url}")
                    break
        
        # If no company name found, try to find it in headings or strong text
        if not company_name:
            heading_elements = element.select('h1, h2, h3, h4, h5, h6, strong, b')
            for heading in heading_elements:
                heading_text = heading.text.strip()
                if len(heading_text) > 3 and not any(x in heading_text.lower() for x in ['view', 'more', 'details', 'login']):
                    company_name = heading_text
                    logger.info(f"Found company name from heading: {company_name}")
                    break
        
        # Extract quarter information - using more generic approach
        # Look for text that matches quarter pattern
        text = element.text
        quarter_match = re.search(r'Q[1-4]\s+FY\d{2}-\d{2}', text)
        if quarter_match:
            quarter = quarter_match.group(0)
            financial_metrics['quarter'] = quarter
            logger.info(f"Extracted quarter from text: {quarter}")
        
        # Extract financial metrics from tables - using more generic approach
        # Look for any tables in the element
        tables = element.select('table')
        if tables:
            for table in tables:
                rows = table.select('tr')
                if len(rows) >= 2:  # At least header and one data row
                    # Try to identify columns by header text
                    headers = []
                    header_cells = rows[0].select('th')
                    if header_cells:
                        headers = [cell.text.strip().lower() for cell in header_cells]
                    
                    # If no headers found in th elements, try first row td elements
                    if not headers:
                        header_cells = rows[0].select('td')
                        if header_cells:
                            headers = [cell.text.strip().lower() for cell in header_cells]
                    
                    # Process data rows
                    for row in rows[1:]:  # Skip header row
                        cells = row.select('td')
                        if len(cells) >= 2:
                            # Try to identify what this row represents
                            row_header = cells[0].text.strip().lower()
                            
                            # Check for revenue/sales
                            if any(term in row_header for term in ['revenue', 'sales', 'income', 'turnover']):
                                # Usually the second column is current period, third is previous period
                                if len(cells) >= 2:
                                    value = cells[1].text.strip()
                                    financial_metrics['revenue'] = clean_numeric_value(value)
                                    logger.info(f"Found revenue: {financial_metrics['revenue']}")
                                
                                # If there's a growth column
                                if len(cells) >= 4:
                                    growth = cells[3].text.strip()
                                    financial_metrics['revenue_growth'] = clean_growth_value(growth)
                                    logger.info(f"Found revenue growth: {financial_metrics['revenue_growth']}")
                            
                            # Check for gross profit
                            elif any(term in row_header for term in ['gross profit', 'operating profit', 'ebitda']):
                                if len(cells) >= 2:
                                    value = cells[1].text.strip()
                                    financial_metrics['gross_profit'] = clean_numeric_value(value)
                                    logger.info(f"Found gross profit: {financial_metrics['gross_profit']}")
                                
                                # If there's a growth column
                                if len(cells) >= 4:
                                    growth = cells[3].text.strip()
                                    financial_metrics['gross_profit_growth'] = clean_growth_value(growth)
                                    logger.info(f"Found gross profit growth: {financial_metrics['gross_profit_growth']}")
                            
                            # Check for net profit
                            elif any(term in row_header for term in ['net profit', 'pat', 'profit after tax', 'net income']):
                                if len(cells) >= 2:
                                    value = cells[1].text.strip()
                                    financial_metrics['net_profit'] = clean_numeric_value(value)
                                    logger.info(f"Found net profit: {financial_metrics['net_profit']}")
                                
                                # If there's a growth column
                                if len(cells) >= 4:
                                    growth = cells[3].text.strip()
                                    financial_metrics['net_profit_growth'] = clean_growth_value(growth)
                                    logger.info(f"Found net profit growth: {financial_metrics['net_profit_growth']}")
        
        # If no tables found or metrics not extracted from tables, try to find metrics in the text
        if not financial_metrics.get('revenue') and not financial_metrics.get('net_profit'):
            # Try to extract revenue
            revenue_patterns = [
                r'Revenue:?\s*₹?\s*([0-9,.]+)\s*(?:cr|Cr)?',
                r'Sales:?\s*₹?\s*([0-9,.]+)\s*(?:cr|Cr)?',
                r'Income:?\s*₹?\s*([0-9,.]+)\s*(?:cr|Cr)?'
            ]
            
            for pattern in revenue_patterns:
                revenue_match = re.search(pattern, text, re.IGNORECASE)
                if revenue_match:
                    revenue = revenue_match.group(1).replace(',', '')
                    try:
                        revenue = float(revenue)
                        financial_metrics['revenue'] = revenue
                        logger.info(f"Extracted revenue from text: {revenue}")
                        break
                    except ValueError:
                        pass
            
            # Try to extract net profit
            profit_patterns = [
                r'Net Profit:?\s*₹?\s*([0-9,.]+)\s*(?:cr|Cr)?',
                r'PAT:?\s*₹?\s*([0-9,.]+)\s*(?:cr|Cr)?',
                r'Profit:?\s*₹?\s*([0-9,.]+)\s*(?:cr|Cr)?'
            ]
            
            for pattern in profit_patterns:
                profit_match = re.search(pattern, text, re.IGNORECASE)
                if profit_match:
                    profit = profit_match.group(1).replace(',', '')
                    try:
                        profit = float(profit)
                        financial_metrics['net_profit'] = profit
                        logger.info(f"Extracted net profit from text: {profit}")
                        break
                    except ValueError:
                        pass
            
            # Try to extract growth percentages
            growth_patterns = [
                r'Revenue Growth:?\s*([+-]?[0-9.]+)%',
                r'Sales Growth:?\s*([+-]?[0-9.]+)%',
                r'YoY Growth:?\s*([+-]?[0-9.]+)%'
            ]
            
            for pattern in growth_patterns:
                growth_match = re.search(pattern, text, re.IGNORECASE)
                if growth_match:
                    growth = growth_match.group(1)
                    try:
                        growth = float(growth)
                        financial_metrics['revenue_growth'] = growth
                        logger.info(f"Extracted revenue growth from text: {growth}%")
                        break
                    except ValueError:
                        pass
            
            profit_growth_patterns = [
                r'(?:Net Profit|PAT) Growth:?\s*([+-]?[0-9.]+)%',
                r'Profit Growth:?\s*([+-]?[0-9.]+)%'
            ]
            
            for pattern in profit_growth_patterns:
                growth_match = re.search(pattern, text, re.IGNORECASE)
                if growth_match:
                    growth = growth_match.group(1)
                    try:
                        growth = float(growth)
                        financial_metrics['net_profit_growth'] = growth
                        logger.info(f"Extracted profit growth from text: {growth}%")
                        break
                    except ValueError:
                        pass
        
        # Extract report type (Standalone/Consolidated) - using more generic approach
        if 'standalone' in text.lower():
            financial_metrics['report_type'] = 'Standalone'
            logger.info("Found report type: Standalone")
        elif 'consolidated' in text.lower():
            financial_metrics['report_type'] = 'Consolidated'
            logger.info("Found report type: Consolidated")
        
        # Extract result date - using more generic approach
        date_patterns = [
            r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}',
            r'\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}',
            r'\d{2}/\d{2}/\d{4}'
        ]
        
        for pattern in date_patterns:
            date_match = re.search(pattern, text)
            if date_match:
                financial_metrics['result_date'] = date_match.group(0)
                logger.info(f"Found result date: {financial_metrics['result_date']}")
                break
        
        # If we still don't have a company name, return None
        if not company_name:
            logger.warning("Could not extract company name")
            return None
        
        # Log what we extracted
        logger.info(f"Extracted data for {company_name}: Quarter: {financial_metrics.get('quarter')}, Revenue: {financial_metrics.get('revenue')}, Net Profit: {financial_metrics.get('net_profit')}")
        
        # Return the company data
        return {
            'company_name': company_name,
            'url': company_url,
            'financial_metrics': financial_metrics,
            'timestamp': datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error extracting company data: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

def clean_numeric_value(value):
    """
    Clean and convert numeric values from text.
    
    Args:
        value: String value to clean
        
    Returns:
        Cleaned numeric value as a string
    """
    if not value:
        return None
    
    try:
        # Remove currency symbols, commas, and 'cr' suffix
        cleaned = re.sub(r'[₹,]', '', value)
        cleaned = cleaned.replace('cr', '').replace('Cr', '').strip()
        
        # Handle negative values
        if cleaned.startswith('(') and cleaned.endswith(')'):
            cleaned = '-' + cleaned[1:-1]
        
        # Convert to float and then back to string for consistency
        if cleaned and cleaned != '--' and cleaned != 'NA' and cleaned != '-':
            return str(float(cleaned))
        return cleaned
    except Exception:
        pass
    
    # If it's already a number, convert to string
    if isinstance(value, (int, float)):
        return str(value)
    
    return value

def clean_growth_value(value):
    """
    Clean and convert growth percentage values from text.
    
    Args:
        value: String value to clean
        
    Returns:
        Cleaned growth value as a string
    """
    if not value:
        return None
    
    try:
        # Remove % symbol
        cleaned = value.replace('%', '').strip()
        
        # Handle negative values
        if cleaned.startswith('(') and cleaned.endswith(')'):
            cleaned = '-' + cleaned[1:-1]
        
        # Convert to float and then back to string for consistency
        if cleaned and cleaned != '--' and cleaned != 'NA' and cleaned != '-':
            return str(float(cleaned))
        return cleaned
    except Exception:
        pass
    
    # If it's already a number, convert to string
    if isinstance(value, (int, float)):
        return str(value)
    
    return value

async def save_to_database(db_collection, company_data):
    """
    Save company data to the database.
    
    Args:
        db_collection: MongoDB collection
        company_data: Dictionary containing company data
    """
    try:
        company_name = company_data.get('company_name')
        financial_metrics = company_data.get('financial_metrics', {})
        stock_metrics = company_data.get('stock_metrics', {})
        quarter = financial_metrics.get('quarter')
        
        if not company_name or not quarter:
            logger.warning(f"Missing company name or quarter, cannot save to database")
            return
        
        # Check if company exists
        existing_company = await db_collection.find_one({"company_name": company_name})
        
        # Extract symbol from stock metrics if available
        symbol = stock_metrics.get('symbol')
        
        if existing_company:
            # Check if this quarter already exists
            exists = await check_company_quarter_exists(db_collection, company_name, quarter)
            
            update_data = {}
            
            # Update symbol if we have it and it's not already set
            if symbol and (not existing_company.get('symbol') or existing_company.get('symbol') == 'None'):
                update_data["symbol"] = symbol
                logger.info(f"Updating symbol for {company_name} to {symbol}")
            
            # Update stock metrics if we have them
            if stock_metrics:
                update_data["stock_metrics"] = stock_metrics
                logger.info(f"Updating stock metrics for {company_name}")
            
            if exists:
                # Update existing quarter
                logger.info(f"Updating existing quarter {quarter} for {company_name}")
                await db_collection.update_one(
                    {"company_name": company_name, "financial_metrics.quarter": quarter},
                    {"$set": {"financial_metrics.$": financial_metrics}}
                )
            else:
                # Add new quarter
                logger.info(f"Adding new quarter {quarter} for {company_name}")
                update_data["$push"] = {"financial_metrics": financial_metrics}
            
            # Apply updates if we have any
            if update_data:
                # Remove $push from the main update if it exists
                push_data = update_data.pop("$push", None)
                
                # If we have other fields to update
                if update_data:
                    await db_collection.update_one(
                        {"company_name": company_name},
                        {"$set": update_data}
                    )
                
                # If we have $push data, apply it separately
                if push_data:
                    await db_collection.update_one(
                        {"company_name": company_name},
                        {"$push": push_data}
                    )
        else:
            # Create new company
            logger.info(f"Creating new company {company_name}")
            await db_collection.insert_one({
                "company_name": company_name,
                "symbol": symbol,
                "financial_metrics": [financial_metrics],
                "stock_metrics": stock_metrics,
                "timestamp": datetime.now()
            })
    
    except Exception as e:
        logger.error(f"Error saving to database: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

async def extract_stock_metrics(driver, company_name):
    """
    Extract metrics from a stock's detail page.
    
    Args:
        driver: Selenium WebDriver instance
        company_name: Name of the company
        
    Returns:
        Dictionary with extracted metrics
    """
    try:
        logger.info(f"Extracting stock metrics for {company_name}")
        
        # Log current URL for verification
        logger.info(f"Current URL: {driver.current_url}")
        
        # Initialize result dictionary
        metrics = {
            "symbol": None,
            "current_price": None,
            "change": None,
            "change_percent": None,
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
            "fundamental_insights_description": None,
            "estimates": {},
            "report_type": None,
            "result_date": None,
            "revenue": None,
            "gross_profit": None,
            "net_profit": None,
            "net_profit_growth": None,
            "gross_profit_growth": None,
            "revenue_growth": None
        }
        
        # Extract symbol from URL
        try:
            url = driver.current_url
            symbol_match = re.search(r'/([^/]+)\?', url)
            if symbol_match:
                metrics["symbol"] = symbol_match.group(1)
                logger.info(f"Extracted symbol: {metrics['symbol']}")
        except Exception as e:
            logger.debug(f"Error extracting symbol: {str(e)}")
        
        # Extract current price
        try:
            price_elem = driver.find_element(By.CSS_SELECTOR, '.pcstkspr span')
            if price_elem:
                metrics["current_price"] = price_elem.text.strip()
                logger.info(f"Found current_price: {metrics['current_price']}")
        except Exception as e:
            logger.debug(f"Error extracting current price: {str(e)}")
            
            # Try alternative selector
            try:
                price_elem = driver.find_element(By.CSS_SELECTOR, '.stprh span')
                if price_elem:
                    metrics["current_price"] = price_elem.text.strip()
                    logger.info(f"Found current_price (alt): {metrics['current_price']}")
            except Exception as e:
                logger.debug(f"Error extracting current price (alt): {str(e)}")
        
        # Extract change and change percent
        try:
            change_elem = driver.find_element(By.CSS_SELECTOR, '.pcstkspr .pricupdn')
            if change_elem:
                change_text = change_elem.text.strip()
                # Split into change and change percent
                if ' ' in change_text:
                    parts = change_text.split(' ')
                    metrics["change"] = parts[0].strip()
                    metrics["change_percent"] = parts[1].strip('()')
                else:
                    metrics["change"] = change_text
                logger.info(f"Found change: {metrics['change']}, change_percent: {metrics['change_percent']}")
        except Exception as e:
            logger.debug(f"Error extracting change: {str(e)}")
        
        # Extract metrics from the Know Before You Invest section
        know_before_metrics = await extract_know_before_invest_data(driver, company_name)
        
        # Merge the metrics
        for key, value in know_before_metrics.items():
            if value is not None:
                metrics[key] = value
        
        # Extract financial data from the page
        try:
            # Look for financial data table
            financial_tables = driver.find_elements(By.CSS_SELECTOR, '.financial-data-table, .quarterly-results, .annual-results')
            
            if financial_tables:
                logger.info(f"Found {len(financial_tables)} financial tables")
                
                for table in financial_tables:
                    try:
                        # Check if this is a quarterly results table
                        table_title = table.find_element(By.CSS_SELECTOR, 'caption, th').text.strip()
                        if 'quarterly' in table_title.lower() or 'q3' in table_title.lower() or 'q3 fy' in table_title.lower():
                            logger.info(f"Found quarterly results table: {table_title}")
                            
                            # Extract rows
                            rows = table.find_elements(By.CSS_SELECTOR, 'tr')
                            for row in rows:
                                try:
                                    cells = row.find_elements(By.CSS_SELECTOR, 'td')
                                    if len(cells) >= 2:
                                        row_header = cells[0].text.strip().lower()
                                        value = cells[1].text.strip()
                                        
                                        if 'revenue' in row_header or 'sales' in row_header:
                                            metrics['revenue'] = value
                                            logger.info(f"Found revenue: {value}")
                                        elif 'gross profit' in row_header or 'operating profit' in row_header:
                                            metrics['gross_profit'] = value
                                            logger.info(f"Found gross_profit: {value}")
                                        elif 'net profit' in row_header:
                                            metrics['net_profit'] = value
                                            logger.info(f"Found net_profit: {value}")
                                        elif 'growth' in row_header and 'revenue' in row_header:
                                            metrics['revenue_growth'] = value
                                            logger.info(f"Found revenue_growth: {value}")
                                        elif 'growth' in row_header and 'profit' in row_header and 'net' not in row_header:
                                            metrics['gross_profit_growth'] = value
                                            logger.info(f"Found gross_profit_growth: {value}")
                                        elif 'growth' in row_header and 'net profit' in row_header:
                                            metrics['net_profit_growth'] = value
                                            logger.info(f"Found net_profit_growth: {value}")
                                except Exception as e:
                                    logger.debug(f"Error processing row in financial table: {str(e)}")
                    except Exception as e:
                        logger.debug(f"Error processing financial table: {str(e)}")
            
            # Try alternative approach with BeautifulSoup
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Look for quarterly results section
            quarterly_sections = soup.select('.quarterly-results, .results-section, #quarterly')
            for section in quarterly_sections:
                logger.info(f"Found quarterly results section")
                
                # Look for tables in this section
                tables = section.select('table')
                for table in tables:
                    # Check if this table has Q3 data
                    if 'Q3' in table.text and 'FY' in table.text:
                        logger.info(f"Found table with Q3 data")
                        
                        # Extract rows
                        rows = table.select('tr')
                        for row in rows:
                            cells = row.select('td')
                            if len(cells) >= 2:
                                row_header = cells[0].text.strip().lower()
                                value = cells[1].text.strip()
                                
                                if 'revenue' in row_header or 'sales' in row_header:
                                    metrics['revenue'] = value
                                    logger.info(f"Found revenue (BS): {value}")
                                elif 'gross profit' in row_header or 'operating profit' in row_header:
                                    metrics['gross_profit'] = value
                                    logger.info(f"Found gross_profit (BS): {value}")
                                elif 'net profit' in row_header:
                                    metrics['net_profit'] = value
                                    logger.info(f"Found net_profit (BS): {value}")
                                elif 'growth' in row_header and 'revenue' in row_header:
                                    metrics['revenue_growth'] = value
                                    logger.info(f"Found revenue_growth (BS): {value}")
                                elif 'growth' in row_header and 'profit' in row_header and 'net' not in row_header:
                                    metrics['gross_profit_growth'] = value
                                    logger.info(f"Found gross_profit_growth (BS): {value}")
                                elif 'growth' in row_header and 'net profit' in row_header:
                                    metrics['net_profit_growth'] = value
                                    logger.info(f"Found net_profit_growth (BS): {value}")
        except Exception as e:
            logger.debug(f"Error extracting financial data: {str(e)}")
        
        # Extract report type (Standalone/Consolidated)
        try:
            report_type_elems = driver.find_elements(By.CSS_SELECTOR, '.report-type, .standalone, .consolidated')
            for elem in report_type_elems:
                text = elem.text.strip()
                if 'standalone' in text.lower():
                    metrics['report_type'] = 'Standalone'
                    logger.info(f"Found report_type: Standalone")
                    break
                elif 'consolidated' in text.lower():
                    metrics['report_type'] = 'Consolidated'
                    logger.info(f"Found report_type: Consolidated")
                    break
        except Exception as e:
            logger.debug(f"Error extracting report type: {str(e)}")
        
        # Extract result date
        try:
            date_elems = driver.find_elements(By.CSS_SELECTOR, '.result-date, .date-published')
            for elem in date_elems:
                text = elem.text.strip()
                if text and ('20' in text or 'Jan' in text or 'Feb' in text or 'Mar' in text):
                    metrics['result_date'] = text
                    logger.info(f"Found result_date: {text}")
                    break
        except Exception as e:
            logger.debug(f"Error extracting result date: {str(e)}")
        
        # Extract estimates
        try:
            # Look for estimate section
            estimate_section = driver.find_element(By.CSS_SELECTOR, '.estimates_section')
            if estimate_section:
                logger.info("Found estimates section")
                
                # Extract estimate data
                estimate_rows = estimate_section.find_elements(By.CSS_SELECTOR, 'tr')
                for row in estimate_rows:
                    try:
                        cells = row.find_elements(By.CSS_SELECTOR, 'td')
                        if len(cells) >= 2:
                            metric_name = cells[0].text.strip()
                            metric_value = cells[1].text.strip()
                            if metric_name and metric_value:
                                metrics["estimates"][metric_name] = metric_value
                                logger.info(f"Found estimate: {metric_name} = {metric_value}")
                    except Exception as e:
                        logger.debug(f"Error extracting estimate row: {str(e)}")
        except Exception as e:
            logger.debug(f"Error extracting estimates: {str(e)}")
            
            # Try alternative approach with BeautifulSoup
            try:
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                estimate_tables = soup.select('.estimates_section table')
                
                if estimate_tables:
                    logger.info(f"Found {len(estimate_tables)} estimate tables with BeautifulSoup")
                    
                    for table in estimate_tables:
                        rows = table.select('tr')
                        for row in rows:
                            cells = row.select('td')
                            if len(cells) >= 2:
                                metric_name = cells[0].text.strip()
                                metric_value = cells[1].text.strip()
                                if metric_name and metric_value:
                                    metrics["estimates"][metric_name] = metric_value
                                    logger.info(f"Found estimate (BS): {metric_name} = {metric_value}")
            except Exception as e:
                logger.debug(f"Error extracting estimates with BeautifulSoup: {str(e)}")
        
        # Extract fundamental insights
        try:
            insights_elem = driver.find_element(By.CSS_SELECTOR, '.fundamental-insights, .insights-title')
            if insights_elem:
                metrics["fundamental_insights"] = insights_elem.text.strip()
                logger.info(f"Found fundamental_insights: {metrics['fundamental_insights']}")
                
                # Try to find the description
                desc_elem = insights_elem.find_element(By.XPATH, "following-sibling::*[1]")
                if desc_elem:
                    metrics["fundamental_insights_description"] = desc_elem.text.strip()
                    logger.info(f"Found fundamental_insights_description: {metrics['fundamental_insights_description']}")
        except Exception as e:
            logger.debug(f"Error extracting fundamental insights: {str(e)}")
        
        # Log extraction results
        logger.info(f"Extracted {sum(1 for v in metrics.values() if v is not None)} metrics for {company_name}")
        
        return metrics
    except Exception as e:
        logger.error(f"Error in extract_stock_metrics: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {} 