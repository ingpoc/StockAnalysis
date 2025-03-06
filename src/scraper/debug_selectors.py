"""
Debug script to identify the correct selectors for result cards on MoneyControl.
"""
import os
import sys
import asyncio
from selenium import webdriver
from bs4 import BeautifulSoup
import time
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Import project modules
from src.scraper.browser_setup import setup_webdriver, login_to_moneycontrol
from src.utils.logger import logger

# Target URL
TARGET_URL = "https://www.moneycontrol.com/markets/earnings/latest-results/?tab=LR&subType=yoy"

async def main():
    """Main function to debug selectors"""
    logger.info("=== Starting Selector Debug ===")
    
    # Initialize the WebDriver
    driver = setup_webdriver(headless=False)
    
    try:
        # Login to MoneyControl
        login_success = login_to_moneycontrol(driver, target_url=TARGET_URL)
        if not login_success:
            logger.error("Failed to login to MoneyControl")
            return
        
        # Navigate to the page
        logger.info(f"Opening page: {TARGET_URL}")
        driver.get(TARGET_URL)
        
        # Wait for page to load (adjust timeout as needed)
        time.sleep(10)
        
        # Get the page source
        page_source = driver.page_source
        
        # Save the page source for inspection
        with open("page_source.html", "w", encoding="utf-8") as f:
            f.write(page_source)
        logger.info("Saved page source to page_source.html")
        
        # Take a screenshot for visual reference
        driver.save_screenshot("debug_screenshot.png")
        logger.info("Saved screenshot to debug_screenshot.png")
        
        # Parse the page with BeautifulSoup
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Try different selectors for result cards
        selectors_to_try = [
            'li.rapidResCardWeb_gryCard___hQigs',
            '.rapidResCardWeb_gryCard___hQigs',
            '.EarningUpdateCard_grayCardMain___OI3r',
            '#latestRes > div > ul > li',
            'div.EarningUpdateCard_grayCardMain___OI3r',
            'li',
            'div[class*="grayCardMain"]',
            'div[class*="cardMain"]'
        ]
        
        logger.info("Testing different selectors:")
        for selector in selectors_to_try:
            elements = soup.select(selector)
            logger.info(f"Selector '{selector}': Found {len(elements)} elements")
            
            # Log the first element for inspection
            if elements:
                logger.info(f"First element class: {elements[0].get('class', 'No class')}")
                logger.info(f"First element tag: {elements[0].name}")
                
                # Try to find company name within this element
                company_name_elements = elements[0].select('h3 a')
                if company_name_elements:
                    logger.info(f"Found company name: {company_name_elements[0].text.strip()}")
                else:
                    logger.info("No company name found in this element")
        
        # Get all classes in the document for reference
        all_classes = set()
        for tag in soup.find_all(class_=True):
            for class_name in tag.get('class', []):
                if 'card' in class_name.lower():
                    all_classes.add(class_name)
        
        logger.info("All classes containing 'card':")
        for class_name in sorted(all_classes):
            logger.info(f"  - {class_name}")
            
        logger.info("=== Selector Debug Complete ===")
    except Exception as e:
        logger.error(f"Error during selector debug: {str(e)}")
    finally:
        driver.quit()

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main()) 