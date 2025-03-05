"""
Test script for MoneyControl login functionality.
"""
import os
import sys
import time
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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
    
    # Set headless mode to false for testing
    os.environ['HEADLESS'] = 'false'
    
    logger.info("Setting up WebDriver")
    driver = setup_webdriver()  # No longer passing headless parameter
    
    try:
        logger.info("Attempting to login to MoneyControl")
        success = login_to_moneycontrol(driver, username, password, target_url)
        
        if success:
            logger.info("Login successful!")
            logger.info(f"Current URL: {driver.current_url}")
            logger.info(f"Page title: {driver.title}")
            
            # Take a screenshot for verification
            screenshot_path = os.path.join(os.path.dirname(__file__), "login_success.png")
            driver.save_screenshot(screenshot_path)
            logger.info(f"Saved screenshot to {screenshot_path}")
            
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