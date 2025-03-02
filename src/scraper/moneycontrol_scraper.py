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
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Try to extract from URL directly (most reliable)
            url_parts = url.split('/')
            if len(url_parts) > 0 and url_parts[-1].startswith('MS'):
                symbol = url_parts[-1]
                logger.info(f"Extracted symbol from URL: {symbol}")
                
            # If not found in URL, try other methods
            if not symbol:
                # Try main selector
                symbol_elem = soup.select_one('#company_info > ul > li:nth-child(5) > ul > li:nth-child(2) > p')
                if symbol_elem:
                    symbol = symbol_elem.text.strip()
                    logger.info(f"Extracted symbol from company info: {symbol}")
            
            # Try alternative selector
            if not symbol:
                alt_symbol_elem = soup.select_one('.nsestock_overview table tr:nth-child(1) td:nth-child(1)')
                if alt_symbol_elem:
                    symbol_text = alt_symbol_elem.text.strip()
                    if ':' in symbol_text:
                        symbol = symbol_text.split(':')[1].strip()
                        logger.info(f"Extracted symbol from stock overview: {symbol}")
            
            # Try extracting from breadcrumbs
            if not symbol:
                breadcrumb_elem = soup.select_one('.breadcrumb span')
                if breadcrumb_elem:
                    symbol = breadcrumb_elem.text.strip()
                    logger.info(f"Extracted symbol from breadcrumb: {symbol}")
            
            # Try alternative - extract from title
            if not symbol and '(' in page_title and ')' in page_title:
                symbol_part = page_title.split('(')[1].split(')')[0]
                if symbol_part:
                    symbol = symbol_part
                    logger.info(f"Extracted symbol from title: {symbol}")
            
            # Fallback to company name if still no symbol
            if not symbol:
                # Use the stock code from the URL if available
                if 'stockpricequote' in url:
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
            cmp_elem = driver.find_element(By.CSS_SELECTOR, '.pcstktxt span:first-child')
            if cmp_elem:
                financial_data["cmp"] = cmp_elem.text.strip()
                logger.info(f"Extracted CMP: {financial_data['cmp']}")
        except Exception as e:
            logger.debug(f"Error extracting CMP: {str(e)}")
        
        # Try to extract quarter info from page
        try:
            quarter_elem = driver.find_element(By.CSS_SELECTOR, '.qtrend')
            if quarter_elem:
                quarter_text = quarter_elem.text.strip()
                # Extract quarter information (Q1/Q2/Q3/Q4 and year)
                # This is a simplistic approach and might need adjustment
                if "Q1" in quarter_text:
                    financial_data["quarter"] = f"Q1 {quarter_text.split('Q1')[1].strip()}"
                elif "Q2" in quarter_text:
                    financial_data["quarter"] = f"Q2 {quarter_text.split('Q2')[1].strip()}"
                elif "Q3" in quarter_text:
                    financial_data["quarter"] = f"Q3 {quarter_text.split('Q3')[1].strip()}"
                elif "Q4" in quarter_text:
                    financial_data["quarter"] = f"Q4 {quarter_text.split('Q4')[1].strip()}"
                logger.info(f"Extracted quarter: {financial_data['quarter']}")
        except Exception as e:
            logger.debug(f"Error extracting quarter info: {str(e)}")
            
        # If we couldn't extract quarter, set a reasonable default
        if not financial_data["quarter"]:
            # Get current fiscal year (April to March in India)
            now = datetime.now()
            month = now.month
            year = now.year
            
            # Determine the fiscal year
            if month < 4:  # January to March
                fiscal_year = f"FY{str(year-1)[-2:]}-{str(year)[-2:]}"
            else:  # April to December
                fiscal_year = f"FY{str(year)[-2:]}-{str(year+1)[-2:]}"
            
            # Determine the quarter based on the month
            if month in [4, 5, 6]:
                quarter = "Q1"
            elif month in [7, 8, 9]:
                quarter = "Q2"
            elif month in [10, 11, 12]:
                quarter = "Q3"
            else:  # month in [1, 2, 3]
                quarter = "Q4"
            
            financial_data["quarter"] = f"{quarter} {fiscal_year}"
            logger.info(f"Using default quarter: {financial_data['quarter']}")

        # Use the more reliable test script approach for additional metrics
        additional_metrics = await extract_know_before_invest_data(driver, company_name)
        
        if additional_metrics:
            # Update financial data with additional metrics
            financial_data.update(additional_metrics)
            
        # Check database for existing data and handle
        existing_company = None
        if db_collection is not None and financial_data.get('quarter') is not None:
            try:
                existing_company = await db_collection.find_one({"company_name": company_name})
                if existing_company is not None:
                    existing_quarters = [metric.get('quarter') for metric in existing_company.get('financial_metrics', []) if metric.get('quarter')]
                    if financial_data['quarter'] in existing_quarters:
                        logger.info(f"{company_name} already has data for {financial_data['quarter']}. Updating.")
                        await db_collection.update_one(
                            {
                                "company_name": company_name,
                                "financial_metrics.quarter": financial_data['quarter']
                            },
                            {"$set": {"financial_metrics.$": financial_data}}
                        )
                    else:
                        logger.info(f"Adding new quarter data for {company_name} - {financial_data['quarter']}")
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

async def scrape_earnings_list(driver, url, db_collection=None, max_companies=5):
    """
    Scrape earnings list from MoneyControl and extract detailed stock metrics for each company.
    
    Args:
        driver: Selenium WebDriver instance
        url: URL of the earnings list page
        db_collection: MongoDB collection to store the results
        max_companies: Maximum number of companies to scrape (default 5)
        
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
        
        # Limit the number of companies to process
        companies_to_process = min(len(result_cards), max_companies)
        logger.info(f"Will process {companies_to_process} companies (max_companies={max_companies})")
        
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

                # Now navigate to the stock page and extract more detailed data
                logger.info(f"Navigating to stock URL: {stock_url}")
                try:
                    driver.get(stock_url)
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.inid_name, h1.pcstname"))
                    )
                    
                    # Extract more detailed data using scrape_single_stock
                    detailed_data = await scrape_single_stock(driver, stock_url)
                    
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
                        await db_collection.update_one(
                            {"url": stock_url},
                            {"$set": document},
                            upsert=True
                        )
                    
                    results.append(document)
                    logger.info(f"Successfully processed {company_name}")
                    
                    # Navigate back to the earnings list page
                    driver.get(url)
                    try:
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "li.rapidResCardWeb_gryCard__hQigs"))
                        )
                    except:
                        try:
                            WebDriverWait(driver, 10).until(
                                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.resultCard"))
                            )
                        except:
                            pass
                    
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
                    
                    # Navigate back to the earnings list page
                    driver.get(url)
                    await asyncio.sleep(3)  # Simple wait for page to reload
            
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