"""
Debug script to identify the correct selectors on the MoneyControl page.
"""
import time
import logging
import os
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from src.scraper.scraper_login import setup_webdriver, login_to_moneycontrol

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("selector_debug.log")
    ]
)

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def debug_selectors():
    """
    Debug the selectors on the MoneyControl page.
    """
    driver = None
    try:
        # Set up the WebDriver
        logger.info("Setting up WebDriver")
        driver = setup_webdriver(headless=False)  # Use non-headless mode for debugging
        logger.info("WebDriver set up successfully")
        
        # Get credentials from environment variables
        username = os.getenv('MONEYCONTROL_USERNAME')
        password = os.getenv('MONEYCONTROL_PASSWORD')
        
        if not username or not password:
            logger.error("MoneyControl credentials not found in environment variables.")
            return
        
        # URL to debug
        url = "https://www.moneycontrol.com/stocks/marketinfo/earnings/results.php"
        
        # Login to MoneyControl
        logger.info(f"Attempting to login to MoneyControl")
        login_success = login_to_moneycontrol(driver, username, password, target_url=url)
        if not login_success:
            logger.error("Failed to login to MoneyControl. Aborting debug.")
            return
        
        # Wait for the page to load
        logger.info("Waiting for page to load")
        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'body'))
            )
            logger.info("Page loaded successfully")
        except Exception as e:
            logger.error(f"Error waiting for page to load: {str(e)}")
            return
        
        # Scroll to load all content
        logger.info("Scrolling page to load all content")
        scroll_page(driver)
        
        # Parse the page
        logger.info("Parsing page content")
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Save the page source for offline analysis
        with open("debug_page_source.html", "w", encoding="utf-8") as f:
            f.write(page_source)
        logger.info("Saved page source to debug_page_source.html")
        
        # Try different selectors
        selectors = [
            'li.rapidResCardWeb_gryCard__hQigs',
            'li.gryCard',
            'div.card',
            'div.result-card',
            'li[class*="gryCard"]',
            'div[class*="card"]'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            logger.info(f"Selector '{selector}' found {len(elements)} elements")
            
            if elements:
                # Print details of the first element
                first_element = elements[0]
                logger.info(f"First element with selector '{selector}':")
                logger.info(f"  Tag name: {first_element.name}")
                logger.info(f"  Classes: {first_element.get('class', [])}")
                
                # Try to find company name
                company_name_element = first_element.select_one('h3 a')
                if company_name_element:
                    logger.info(f"  Company name: {company_name_element.text.strip()}")
                else:
                    logger.info("  Company name element not found")
                
                # Try to find financial data
                financial_data_elements = first_element.select('tr')
                logger.info(f"  Found {len(financial_data_elements)} financial data rows")
                
                for i, row in enumerate(financial_data_elements[:3]):  # Show first 3 rows
                    logger.info(f"  Row {i+1}: {row.text.strip()}")
        
        # Wait for user to review the page
        logger.info("Debug complete. Waiting 30 seconds before closing...")
        time.sleep(30)
        
    except Exception as e:
        logger.error(f"Error during debugging: {str(e)}")
    finally:
        if driver:
            driver.quit()
            logger.info("WebDriver closed")

def scroll_page(driver):
    """
    Scroll the page to load all dynamic content.
    """
    try:
        last_height = driver.execute_script("return document.body.scrollHeight")
        for _ in range(5):  # Limit to 5 scrolls for debugging
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
    except Exception as e:
        logger.error(f"Error during scrolling: {str(e)}")

if __name__ == "__main__":
    debug_selectors() 