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

def setup_webdriver(headless=False):
    """
    Set up and configure the WebDriver for scraping.
    
    Args:
        headless (bool): Whether to run the browser in headless mode. Default is False to show the browser.
        
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
        # If skip_login is True, go directly to target_url or return True
        if skip_login:
            if target_url:
                logger.info(f"Skipping login and navigating directly to target URL: {target_url}")
                driver.get(target_url)
                time.sleep(3)  # Wait for page to load
            else:
                logger.info("Skipping login as requested")
            return True
        
        # Use the mobile login URL with redirect parameter
        login_url = f"https://m.moneycontrol.com/login.php"
        if target_url:
            login_url = f"https://m.moneycontrol.com/login.php?cpurl={target_url}"
        
        logger.info(f"Navigating to login page: {login_url}")
        driver.get(login_url)
        time.sleep(3)  # Wait for page to load
        
        # Enhanced ad removal function - to be called repeatedly if needed
        def remove_ad_overlays():
            """Remove ad overlays and return True if successful, False otherwise."""
            try:
                logger.info("Removing ad overlays before login...")
                
                # Check for reward ad units which are particularly problematic
                reward_ads = driver.find_elements(By.CSS_SELECTOR, 'ins[id*="REWARD"]')
                if reward_ads:
                    logger.info(f"Found {len(reward_ads)} reward ad elements")
                    
                    # More specific targeting for reward ads
                    driver.execute_script("""
                        // Remove specific reward ads
                        const rewardAds = document.querySelectorAll('ins[id*="REWARD"]');
                        rewardAds.forEach(ad => {
                            if (ad.parentNode) {
                                ad.parentNode.removeChild(ad);
                            }
                        });
                    """)
                
                # Remove all types of ads and overlays
                driver.execute_script("""
                    // Remove all Google ad iframes
                    const adIframes = document.querySelectorAll('iframe[id^="google_ads_iframe"]');
                    adIframes.forEach(iframe => {
                        if (iframe.parentNode) {
                            iframe.parentNode.removeChild(iframe);
                        }
                    });
                    
                    // Remove all ad containers
                    const adContainers = document.querySelectorAll('div[id*="google_ads"], div[id*="ad_container"], div[class*="ad-"], div[id*="ad-"]');
                    adContainers.forEach(container => {
                        if (container.parentNode) {
                            container.parentNode.removeChild(container);
                        }
                    });
                    
                    // Remove any overlay divs
                    const overlays = document.querySelectorAll('div[class*="overlay"], div[id*="overlay"], .modal, .popup, div[style*="position: fixed"]');
                    overlays.forEach(overlay => {
                        if (overlay.parentNode) {
                            overlay.parentNode.removeChild(overlay);
                        }
                    });
                    
                    // Remove any fixed position elements that might be blocking
                    const fixedElements = document.querySelectorAll('div[style*="z-index"][style*="position: fixed"], div[style*="position: fixed"][style*="z-index"]');
                    fixedElements.forEach(el => {
                        if (el.parentNode) {
                            el.parentNode.removeChild(el);
                        }
                    });
                    
                    // Remove inline styles that might be blocking clicks
                    document.querySelectorAll('body, html').forEach(el => {
                        el.style.overflow = 'auto';
                        el.style.position = 'static';
                    });
                    
                    // Remove specific HTML structure often used for ads
                    const adWrappers = document.querySelectorAll('div[class*="adWrapper"], div[id*="adWrapper"]');
                    adWrappers.forEach(wrapper => {
                        if (wrapper.parentNode) {
                            wrapper.parentNode.removeChild(wrapper);
                        }
                    });
                """)
                
                # Also try to click on any close buttons
                try:
                    close_buttons = driver.find_elements(By.CSS_SELECTOR, '.close-btn, .closeBtn, .close, button[aria-label="Close"], button[title="Close"]')
                    for btn in close_buttons:
                        try:
                            btn.click()
                            logger.info("Clicked on close button for an overlay")
                            time.sleep(0.5)
                        except:
                            pass
                except:
                    pass
                
                # Wait for a moment after removing ads
                time.sleep(2)
                
                # Check for any remaining ad iframes (just for logging)
                remaining_ads = driver.find_elements(By.CSS_SELECTOR, "iframe[id^='google_ads_iframe']")
                if remaining_ads:
                    logger.info(f"Still found {len(remaining_ads)} ad iframes after removal attempt")
                    return False
                else:
                    logger.info("Successfully removed all ad iframes")
                    return True
                    
            except Exception as e:
                logger.warning(f"Error while handling ad overlays: {str(e)}")
                return False
        
        # Attempt to remove ads multiple times if needed
        for attempt in range(3):
            if remove_ad_overlays():
                break
            logger.info(f"Ad removal attempt {attempt+1} completed, trying again...")
            time.sleep(1)
        
        # Now try to interact with the login frame
        max_login_attempts = 3
        for attempt in range(max_login_attempts):
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
                
                # Switch back to default content
                driver.switch_to.default_content()
                
                # Navigate to target URL if provided
                if target_url:
                    logger.info(f"Opening page: {target_url}")
                    driver.get(target_url)
                    time.sleep(2)
                
                return True
            
            except Exception as e:
                logger.error(f"Login attempt {attempt+1} failed: {str(e)}")
                
                # Switch back to the default content
                try:
                    driver.switch_to.default_content()
                except:
                    pass
                
                # If not the last attempt, try removing ads again and retry
                if attempt < max_login_attempts - 1:
                    logger.info("Removing ads and retrying login...")
                    remove_ad_overlays()
                    time.sleep(2)
                else:
                    logger.error("All login attempts failed.")
                    return False
        
        return False
            
    except Exception as e:
        logger.error(f"Error during login: {str(e)}")
        return False 