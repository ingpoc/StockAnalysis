"""
Browser setup module for web scraping.
Provides functions to set up and manage browser sessions.
"""
import os
import time
import platform
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

# Load environment variables
load_dotenv()

# Import the centralized logger
from src.utils.logger import logger

def setup_webdriver(headless=True):
    """
    Set up and configure the WebDriver for scraping.
    
    Args:
        headless (bool): Whether to run the browser in headless mode.
        
    Returns:
        webdriver.Chrome: Configured WebDriver instance or None if setup fails.
    """
    try:
        logger.info(f"Setting up WebDriver (headless: {headless})")
        
        # Set up Chrome options
        chrome_options = Options()
        
        # Add headless mode if enabled
        if headless:
            chrome_options.add_argument("--headless=new")
        
        # Add common options for stability and performance
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-extensions")
        
        # Add user agent to avoid detection
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Exclude the "enable-automation" flag
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        
        # Check which browser to use
        browser = os.getenv('BROWSER', 'chrome').lower()
        
        if browser == 'brave':
            logger.info("Using Brave browser")
            
            # Path to Brave browser binary
            if platform.system() == 'Darwin':  # macOS
                if platform.machine() == 'arm64':  # Apple Silicon
                    brave_path = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
                else:  # Intel
                    brave_path = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
            elif platform.system() == 'Windows':
                brave_path = "C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe"
            else:  # Linux
                brave_path = "/usr/bin/brave-browser"
            
            # Check if the path exists
            if os.path.exists(brave_path):
                chrome_options.binary_location = brave_path
            else:
                logger.warning(f"Brave browser not found at {brave_path}, falling back to Chrome")
        
        # Set up WebDriver
        try:
            # Try to create the driver directly without ChromeDriverManager
            logger.info("Creating WebDriver directly")
            driver = webdriver.Chrome(options=chrome_options)
        except Exception as e:
            logger.warning(f"Failed to create WebDriver directly: {str(e)}")
            logger.info("Falling back to ChromeDriverManager")
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Set page load timeout
        driver.set_page_load_timeout(60)
        
        logger.info("WebDriver set up successfully")
        return driver
    except Exception as e:
        logger.error(f"Error setting up WebDriver: {str(e)}")
        return None

def login_to_moneycontrol(driver, username=None, password=None, target_url=None, skip_login=False):
    """
    Log in to MoneyControl website.
    
    Args:
        driver (webdriver.Chrome): WebDriver instance.
        username (str, optional): Username for login. Defaults to env variable.
        password (str, optional): Password for login. Defaults to env variable.
        target_url (str, optional): URL to navigate to after login.
        skip_login (bool, optional): Whether to skip login and go directly to target_url.
        
    Returns:
        bool: True if login was successful or skipped, False otherwise.
    """
    try:
        # If skip_login is True and target_url is provided, go directly to target_url
        if skip_login and target_url:
            logger.info(f"Skipping login and navigating directly to target URL: {target_url}")
            driver.get(target_url)
            time.sleep(3)  # Wait for page to load
            return True
        
        # Use the mobile login URL with redirect parameter
        login_url = f"https://m.moneycontrol.com/login.php"
        if target_url:
            login_url = f"https://m.moneycontrol.com/login.php?cpurl={target_url}"
        
        logger.info(f"Navigating to login page: {login_url}")
        driver.get(login_url)
        time.sleep(3)  # Wait for page to load
        
        try:
            # Switch to the login iframe
            logger.info("Waiting for login frame to be available")
            WebDriverWait(driver, 20).until(
                EC.frame_to_be_available_and_switch_to_it((By.ID, "login_frame"))
            )
            logger.info("Switched to login frame")
            
            # Click on the password login tab
            logger.info("Clicking on password login tab")
            WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '#mc_log_otp_pre > div.loginwithTab > ul > li.signup_ctc'))
            ).click()
            
            # Fill in email and password
            logger.info("Entering username and password")
            email_input = WebDriverWait(driver, 20).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, '#mc_login > form > div:nth-child(1) > div > input[type=text]'))
            )
            
            password_input = WebDriverWait(driver, 20).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, '#mc_login > form > div:nth-child(2) > div > input[type=password]'))
            )
            
            # Get credentials from parameters or environment variables
            username = username or os.getenv('MONEYCONTROL_USERNAME')
            password = password or os.getenv('MONEYCONTROL_PASSWORD')
            
            if not username or not password:
                logger.error("Username or password not provided and not found in environment variables")
                return False
            
            email_input.send_keys(username)
            password_input.send_keys(password)
            
            # Click on login button
            login_button = driver.find_element(By.CSS_SELECTOR, '#mc_login > form > button.continue.login_verify_btn')
            login_button.click()
            
            # Explicitly click "Continue Without Credit Insights"
            continue_without_credit_score_button = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '#mc_login > form > button.get_otp_signup.without_insights_btn'))
            )
            continue_without_credit_score_button.click()
            
            # Sleep for 4 seconds after clicking the button
            time.sleep(4)
            logger.info("Successfully logged in to MoneyControl")
            return True
        except Exception as e:
            logger.error(f"Error during login frame interaction: {str(e)}")
            return False
            
    except Exception as e:
        logger.error(f"Error during login: {str(e)}")
        return False 