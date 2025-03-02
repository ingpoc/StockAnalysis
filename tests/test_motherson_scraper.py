"""
Test script to scrape only MOTHERSON card data to validate selectors.
This script targets a single stock for testing CSS selectors.
"""
import logging
import asyncio
import os
import sys
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
from pathlib import Path

# Add parent directory to path to import modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from src.scraper.scraper_login import setup_webdriver, login_to_moneycontrol

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# URL for MOTHERSON stock directly (to avoid scraping multiple cards)
MOTHERSON_URL = "https://www.moneycontrol.com/india/stockpricequote/auto-ancillaries/motherson/MS24"

def save_html_content(driver, filename):
    """Save the page source to a file for analysis"""
    html_content = driver.page_source
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    with open(logs_dir / filename, "w", encoding="utf-8") as f:
        f.write(html_content)
    logger.info(f"Saved HTML to logs/{filename}")
    return html_content

def extract_know_before_invest_data(driver, company_name):
    """Extract data from the KnowBeforeYouInvest section"""
    # Take a screenshot for debugging
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    screenshot_path = logs_dir / f"{company_name}_detail_page.png"
    driver.save_screenshot(str(screenshot_path))
    logger.info(f"Screenshot saved to {screenshot_path}")
    
    # Save HTML for analysis
    html_content = save_html_content(driver, f"{company_name}_page.html")
    
    # Log current URL
    logger.info(f"Current URL: {driver.current_url}")
    
    # Try to find the KnowBeforeYouInvest section directly
    try:
        know_before_section = driver.find_element(By.ID, "knowBeforeInvest")
        logger.info("Found #knowBeforeInvest section")
    except NoSuchElementException:
        logger.warning("Could not find #knowBeforeInvest section")
        
        # Alternative approach: Try to find relevant content by keywords
        logger.info("Trying to find section by page scroll and checking visible elements")
        
        # Scroll down the page in sections to make all elements visible
        height = driver.execute_script("return document.body.scrollHeight")
        for i in range(0, height, 500):
            driver.execute_script(f"window.scrollTo(0, {i});")
            time.sleep(0.1)
        
        # Use BeautifulSoup for more flexible parsing
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Check if relevant keywords exist on the page
        keywords = ['strengths', 'weaknesses', 'technicals', 'piotroski', 'cagr']
        for keyword in keywords:
            if keyword in html_content.lower():
                logger.info(f"Found keyword '{keyword}' on the page")
        
        # Initialize result dictionary
        result = {
            'company_name': company_name,
            'strengths': None,
            'weaknesses': None,
            'technicals_trend': None,
            'piotroski_score': None,
            'revenue_growth_3yr_cagr': None,
            'net_profit_growth_3yr_cagr': None,
            'operating_profit_growth_3yr_cagr': None
        }
        
        # Try multiple BeautifulSoup selectors for strengths
        strengths_selectors = [
            '#swot_ls > a > strong',
            '.swotdiv .strengths strong',
            '.swotleft strong',
            '.swot_str strong'
        ]
        
        for selector in strengths_selectors:
            strengths_elem = soup.select(selector)
            if strengths_elem:
                result['strengths'] = strengths_elem[0].text.strip()
                logger.info(f"Found strengths with BeautifulSoup selector '{selector}': {result['strengths']}")
                break
        
        # Try multiple BeautifulSoup selectors for weaknesses
        weaknesses_selectors = [
            '#swot_lw > a > strong',
            '.swotdiv .weaknesses strong',
            '.swotright strong',
            '.swot_weak strong'
        ]
        
        for selector in weaknesses_selectors:
            weaknesses_elem = soup.select(selector)
            if weaknesses_elem:
                result['weaknesses'] = weaknesses_elem[0].text.strip()
                logger.info(f"Found weaknesses with BeautifulSoup selector '{selector}': {result['weaknesses']}")
                break
        
        # Try multiple BeautifulSoup selectors for technical analysis trend
        technicals_selectors = [
            '#techAnalysis a[style*="flex"]',
            '.techDiv p strong',
            '.techAnls strong',
            '.technicals strong'
        ]
        
        for selector in technicals_selectors:
            technicals_elem = soup.select(selector)
            if technicals_elem:
                result['technicals_trend'] = technicals_elem[0].text.strip()
                logger.info(f"Found technicals_trend with BeautifulSoup selector '{selector}': {result['technicals_trend']}")
                break
        
        # Try multiple BeautifulSoup selectors for Piotroski score
        piotroski_selectors = [
            'div:nth-child(2) div.fpioi div.nof',
            '.piotroski_score',
            '.pio_score span',
            '#piotroskiScore'
        ]
        
        for selector in piotroski_selectors:
            piotroski_elem = soup.select(selector)
            if piotroski_elem:
                result['piotroski_score'] = piotroski_elem[0].text.strip()
                logger.info(f"Found piotroski_score with BeautifulSoup selector '{selector}': {result['piotroski_score']}")
                break
        
        # Find all tables on the page
        tables = soup.find_all('table')
        logger.info(f"Found {len(tables)} tables on the page")
        
        # Extract CAGR data from tables
        for i, table in enumerate(tables, 1):
            # Log a sample of each table
            table_text = str(table)[:200] + "..." if len(str(table)) > 200 else str(table)
            logger.info(f"Table {i} content sample: {table_text}")
            
            # Check if table contains CAGR data
            if 'CAGR' in str(table) or 'cagr' in str(table).lower() or 'Grwth' in str(table):
                logger.info(f"Table {i} might contain CAGR data")
                
                # Save table HTML for analysis
                with open(logs_dir / f"table_{i}.html", "w", encoding="utf-8") as f:
                    f.write(str(table))
                logger.info(f"Saved table HTML to logs/table_{i}.html")
                
                # Process specific tables we know contain CAGR data
                if i == 59 or 'Profit Grwth 3Yr CAGR' in str(table):
                    # Try to extract CAGR values
                    try:
                        # Extract profit growth 3yr CAGR
                        profit_cagr_cell = table.find('td', string=lambda s: s and 'Profit Grwth 3Yr CAGR' in s)
                        if profit_cagr_cell:
                            next_cell = profit_cagr_cell.find_next('td')
                            if next_cell:
                                result['net_profit_growth_3yr_cagr'] = next_cell.text.strip()
                                logger.info(f"Found net_profit_growth_3yr_cagr: {result['net_profit_growth_3yr_cagr']}")
                        
                        # Extract sales growth 3yr CAGR
                        sales_cagr_cell = table.find('td', string=lambda s: s and 'Sales Grwth 3Yr CAGR' in s)
                        if sales_cagr_cell:
                            next_cell = sales_cagr_cell.find_next('td')
                            if next_cell:
                                result['revenue_growth_3yr_cagr'] = next_cell.text.strip()
                                logger.info(f"Found revenue_growth_3yr_cagr: {result['revenue_growth_3yr_cagr']}")
                    except Exception as e:
                        logger.warning(f"Error extracting CAGR data from table {i}: {e}")
        
        # Log if any data was not found
        for key, value in result.items():
            if value is None and key != 'operating_profit_growth_3yr_cagr':  # We don't expect to find this
                logger.warning(f"Failed to extract {key}")
            elif value is not None:
                logger.info(f"Successfully extracted {key}: {value}")
        
        return result
    
    # If we found the section directly, process it here
    # (This code won't execute for MOTHERSON since we didn't find the section directly)
    return None

def main():
    logger.info("Setting up WebDriver")
    driver = setup_webdriver()
    
    try:
        # Get MoneyControl credentials from environment variables
        username = os.getenv('MONEYCONTROL_USERNAME')
        password = os.getenv('MONEYCONTROL_PASSWORD')
        
        if not username or not password:
            logger.error("MoneyControl credentials not found in environment variables")
            return
        
        logger.info("Logging in to MoneyControl")
        login_to_moneycontrol(
            driver, 
            username, 
            password, 
            target_url="https://www.moneycontrol.com/india/stockpricequote/auto-ancillaries/motherson/MS24"
        )
        
        logger.info("Starting extraction for MOTHERSON")
        results = extract_know_before_invest_data(driver, "MOTHERSON")
        
        # Log the extraction results
        logger.info("Extraction results:")
        if results:
            for key, value in results.items():
                logger.info(f"{key}: {value}")
        
        logger.info("Test completed successfully")
        
    except Exception as e:
        logger.error(f"Error during test: {e}", exc_info=True)
    finally:
        logger.info("Closing WebDriver")
        driver.quit()

if __name__ == "__main__":
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Run the main function
    main() 