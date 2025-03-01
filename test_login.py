"""
Test script for MoneyControl login functionality.
"""
import os
import time
from dotenv import load_dotenv
from src.scraper.scraper_login import setup_webdriver, login_to_moneycontrol
from src.utils.logger import logger

def test_login():
    """Test the login functionality with the updated implementation."""
    load_dotenv()
    
    # Get credentials from environment variables
    username = os.getenv("MONEYCONTROL_USERNAME")
    password = os.getenv("MONEYCONTROL_PASSWORD")
    
    if not username or not password:
        logger.error("MoneyControl credentials not found in environment variables")
        return
    
    # Target URL for testing
    target_url = "https://www.moneycontrol.com/markets/earnings/latest-results/?tab=LR&subType=yoy"
    
    logger.info("Setting up WebDriver")
    driver = setup_webdriver(headless=False)  # Use headless=False to see the browser
    
    try:
        logger.info("Attempting to login to MoneyControl")
        success = login_to_moneycontrol(driver, username, password, target_url)
        
        if success:
            logger.info("Login successful!")
            logger.info(f"Current URL: {driver.current_url}")
            # Wait to see the results
            time.sleep(10)
        else:
            logger.error("Login failed")
    except Exception as e:
        logger.exception(f"Error during test: {str(e)}")
    finally:
        logger.info("Closing WebDriver")
        driver.quit()

if __name__ == "__main__":
    test_login() 