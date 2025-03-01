"""
Login utility for MoneyControl website.
This module handles selenium-based authentication to MoneyControl.
"""
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException
)
from dotenv import load_dotenv
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
import platform
import subprocess
import sys

# Load environment variables
load_dotenv()

# Import the centralized logger
from src.utils.logger import logger

def find_chrome_path():
    """
    Find Chrome installation path on the system
    """
    system = platform.system()
    chrome_path = None
    
    if system == "Darwin":  # macOS
        # Default Chrome locations on macOS
        default_paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chrome.app/Contents/MacOS/Chrome"
        ]
        
        # Check each path
        for path in default_paths:
            expanded_path = os.path.expanduser(path)
            if os.path.exists(expanded_path):
                logger.info(f"Found Chrome at: {expanded_path}")
                return expanded_path
                
        # Try using mdfind command to locate Chrome
        try:
            cmd = "mdfind -name 'Google Chrome.app'"
            result = subprocess.check_output(cmd, shell=True, text=True).strip()
            if result:
                chrome_app_path = result.split('\n')[0]
                chrome_binary = os.path.join(chrome_app_path, "Contents/MacOS/Google Chrome")
                if os.path.exists(chrome_binary):
                    logger.info(f"Found Chrome using mdfind at: {chrome_binary}")
                    return chrome_binary
        except:
            logger.warning("Failed to find Chrome using mdfind")
            
    elif system == "Windows":
        # Default Chrome locations on Windows
        for program_files in ["C:\\Program Files", "C:\\Program Files (x86)"]:
            chrome_path = f"{program_files}\\Google\\Chrome\\Application\\chrome.exe"
            if os.path.exists(chrome_path):
                return chrome_path
                
    elif system == "Linux":
        # Try common locations on Linux
        for path in ["/usr/bin/google-chrome", "/usr/bin/chromium-browser", "/usr/bin/chromium"]:
            if os.path.exists(path):
                return path
        
        # Try using which command
        try:
            chrome_path = subprocess.check_output("which google-chrome", shell=True, text=True).strip()
            if chrome_path:
                return chrome_path
        except:
            logger.warning("Failed to find Chrome on Linux")
    
    # Hardcoded fallback for macOS
    if system == "Darwin":
        return "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            
    return None

def setup_webdriver():
    """Set up and return Selenium WebDriver"""
    try:
        # Get headless mode setting from environment
        headless_value = os.getenv('HEADLESS', 'true').lower()
        logger.info(f"HEADLESS environment variable: {headless_value}")
        headless_mode = headless_value != "false"
        logger.info(f"Running in headless mode: {headless_mode}")
        
        if headless_mode:
            logger.info("Running Chrome in headless mode")
        else:
            logger.info("Running Chrome with visible browser")
        
        # Find Chrome path
        chrome_path = find_chrome_path()
        if chrome_path:
            logger.info(f"Found Chrome at: {chrome_path}")
            logger.info(f"Setting Chrome binary path to: {chrome_path}")
            
        # Setup Chrome options
        logger.info("Setting up ChromeDriver")
        options = webdriver.ChromeOptions()
        
        # Add options based on headless setting
        if headless_mode:
            options.add_argument('--headless=new')
        
        # Add other standard Chrome options
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        
        # Set binary location if found
        if chrome_path:
            options.binary_location = chrome_path
            
        # DIRECT APPROACH for macOS: Use Homebrew ChromeDriver
        if sys.platform == 'darwin':
            try:
                logger.info("Using direct ChromeDriver approach for macOS")
                
                # First, ensure chromedriver is installed via Homebrew
                os.system("brew install --cask chromedriver 2>/dev/null || brew upgrade --cask chromedriver 2>/dev/null || echo 'Chromedriver installation checked'")
                
                # Check for the Homebrew chromedriver location
                homebrew_path = "/opt/homebrew/bin/chromedriver"
                if os.path.exists(homebrew_path):
                    logger.info(f"Found ChromeDriver at Homebrew path: {homebrew_path}")
                    service = Service(executable_path=homebrew_path)
                    driver = webdriver.Chrome(service=service, options=options)
                    logger.info("Direct ChromeDriver setup successful")
                    return driver
                else:
                    logger.warning(f"ChromeDriver not found at {homebrew_path}")
                    
                # Try other common locations
                other_paths = [
                    "/usr/local/bin/chromedriver",
                    "/usr/bin/chromedriver"
                ]
                
                for path in other_paths:
                    if os.path.exists(path):
                        logger.info(f"Found ChromeDriver at: {path}")
                        service = Service(executable_path=path)
                        driver = webdriver.Chrome(service=service, options=options)
                        logger.info("Direct ChromeDriver setup successful")
                        return driver
                
                # If we got here, we didn't find a chromedriver, so try to download it again
                logger.info("Trying to download ChromeDriver directly")
                # Make sure we're using the executable, not a notice file
                try:
                    from webdriver_manager.chrome import ChromeDriverManager
                    chrome_driver_path = ChromeDriverManager().install()
                    # Verify this isn't pointing to a THIRD_PARTY_NOTICES file
                    if "THIRD_PARTY_NOTICES" in chrome_driver_path:
                        logger.warning(f"Invalid ChromeDriver path detected: {chrome_driver_path}")
                        # Find the proper chromedriver binary in the same directory
                        driver_dir = os.path.dirname(chrome_driver_path)
                        for root, dirs, files in os.walk(driver_dir):
                            for file in files:
                                if file == "chromedriver" or file == "chromedriver.exe":
                                    chrome_driver_path = os.path.join(root, file)
                                    logger.info(f"Found actual chromedriver at: {chrome_driver_path}")
                                    break
                    
                    # Make sure the file is executable
                    if os.path.exists(chrome_driver_path):
                        os.chmod(chrome_driver_path, 0o755)  # Make executable
                        logger.info(f"Made ChromeDriver executable: {chrome_driver_path}")
                        
                    service = Service(executable_path=chrome_driver_path)
                    driver = webdriver.Chrome(service=service, options=options)
                    logger.info("ChromeDriver downloaded and setup successful")
                    return driver
                except Exception as e:
                    logger.error(f"ChromeDriver download failed: {e}")
            except Exception as mac_err:
                logger.error(f"Direct ChromeDriver approach failed: {mac_err}")
            
            # Try Safari as a fallback on macOS
            if sys.platform == 'darwin':
                try:
                    logger.info("Trying Safari as fallback browser")
                    driver = webdriver.Safari()
                    logger.info("Successfully created Safari WebDriver")
                    return driver
                except Exception as safari_error:
                    logger.error(f"Safari fallback failed: {str(safari_error)}")
                    logger.info("To enable Safari WebDriver: Open Safari > Develop menu > Allow Remote Automation")

            # Try Firefox as a final fallback
            try:
                logger.info("Trying Firefox as fallback browser")
                from webdriver_manager.firefox import GeckoDriverManager
                from selenium.webdriver.firefox.service import Service as FirefoxService
                
                firefox_options = webdriver.FirefoxOptions()
                if headless_mode:
                    firefox_options.add_argument('-headless')
                
                # Try to find Firefox on common paths
                firefox_paths = [
                    # macOS
                    "/Applications/Firefox.app/Contents/MacOS/firefox",
                    # Linux
                    "/usr/bin/firefox",
                    # Windows
                    "C:\\Program Files\\Mozilla Firefox\\firefox.exe",
                    "C:\\Program Files (x86)\\Mozilla Firefox\\firefox.exe"
                ]
                
                firefox_binary = None
                for path in firefox_paths:
                    if os.path.exists(path):
                        firefox_binary = path
                        logger.info(f"Found Firefox at: {firefox_binary}")
                        break
                
                if firefox_binary:
                    firefox_options.binary_location = firefox_binary
                
                service = FirefoxService(GeckoDriverManager().install())
                driver = webdriver.Firefox(service=service, options=firefox_options)
                logger.info("Successfully created Firefox WebDriver")
                return driver
            except Exception as firefox_error:
                logger.error(f"Firefox fallback failed: {str(firefox_error)}")
                
            # If all browsers fail
            error_msg = "Failed to create any WebDriver"
            logger.error(error_msg)
            raise Exception(error_msg)
    except Exception as e:
        logger.error(f"Error in setup_webdriver: {str(e)}")
        raise e

def login_to_moneycontrol(driver, username, password, target_url=None):
    """
    Login to MoneyControl with the provided credentials and optionally redirect to a target URL.
    
    Args:
        driver: Selenium WebDriver instance
        username: MoneyControl username
        password: MoneyControl password
        target_url: Optional URL to navigate to after login
        
    Returns:
        bool: True if login successful, False otherwise
    """
    try:
        # Use the direct mobile login URL with redirection parameter
        if target_url:
            login_url = f"https://m.moneycontrol.com/login.php?cpurl={target_url}"
            logger.info(f"Navigating to MoneyControl mobile login page with redirect URL: {login_url}")
        else:
            login_url = "https://m.moneycontrol.com/login.php"
            logger.info(f"Navigating to MoneyControl mobile login page: {login_url}")
            
        driver.get(login_url)
            
        # Switch to the login iframe
        logger.info("Waiting for login iframe")
        WebDriverWait(driver, 20).until(
            EC.frame_to_be_available_and_switch_to_it((By.ID, "login_frame"))
        )
        
        # Click on the password login tab
        logger.info("Clicking on password login tab")
        WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, '#mc_log_otp_pre > div.loginwithTab > ul > li.signup_ctc'))
        ).click()
        
        # Fill in email and password
        logger.info(f"Entering username: {username}")
        email_input = WebDriverWait(driver, 20).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, '#mc_login > form > div:nth-child(1) > div > input[type=text]'))
        )
        
        logger.info("Entering password")
        password_input = WebDriverWait(driver, 20).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, '#mc_login > form > div:nth-child(2) > div > input[type=password]'))
        )
        
        email_input.send_keys(username)
        password_input.send_keys(password)
        
        # Click on login button
        logger.info("Clicking login button")
        login_button = driver.find_element(By.CSS_SELECTOR, '#mc_login > form > button.continue.login_verify_btn')
        login_button.click()
        
        try:
            # Explicitly click "Continue Without Credit Insights" if present
            logger.info("Looking for 'Continue Without Credit Insights' button")
            continue_without_credit_score_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '#mc_login > form > button.get_otp_signup.without_insights_btn'))
            )
            logger.info("Clicking 'Continue Without Credit Insights' button")
            continue_without_credit_score_button.click()
        except (TimeoutException, NoSuchElementException) as e:
            logger.info("No 'Continue Without Credit Insights' button found, continuing...")
        
        # Wait for login to complete
        time.sleep(5)
        
        # Check if login was successful
        if "moneycontrol.com" in driver.current_url:
            logger.info("Login successful")
            
            # If we're not automatically redirected to target_url, do it manually
            if target_url and target_url not in driver.current_url:
                logger.info(f"Navigating to target URL: {target_url}")
                driver.get(target_url)
                time.sleep(3)  # Wait for page to load
                logger.info(f"Successfully navigated to: {driver.current_url}")
                
            return True
        else:
            logger.warning("Login may have failed. Current URL is: %s", driver.current_url)
            return False
        
    except TimeoutException as e:
        logger.error("Timeout while logging in: %s", str(e))
        return False
    except NoSuchElementException as e:
        logger.error("Element not found during login: %s", str(e))
        return False
    except Exception as e:
        logger.error("Error during login: %s", str(e))
        return False 