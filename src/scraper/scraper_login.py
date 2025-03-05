"""
Login utility for MoneyControl website.
This module handles selenium-based authentication to MoneyControl.
"""
import os
import time
import platform
import subprocess
import logging
import importlib.metadata
import requests
import zipfile
import io
import shutil
from pathlib import Path
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

# Load environment variables
load_dotenv()

# Import the centralized logger
from src.utils.logger import logger

def get_package_version(package_name):
    """
    Get the version of an installed package using importlib.metadata.
    
    Args:
        package_name (str): Name of the package
        
    Returns:
        str: Version of the package or None if not found
    """
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return None

def get_available_chromedriver_versions(major_version):
    """
    Get available ChromeDriver versions for a specific major version.
    
    Args:
        major_version (str): Major version of ChromeDriver (e.g., "132")
        
    Returns:
        list: List of available ChromeDriver versions
    """
    try:
        # URL to check available versions
        url = f"https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json"
        logger.info(f"Checking available ChromeDriver versions for major version {major_version}")
        
        response = requests.get(url)
        response.raise_for_status()
        
        data = response.json()
        versions = []
        
        # Extract versions that match the major version
        for version_info in data.get("versions", []):
            version = version_info.get("version", "")
            if version.startswith(f"{major_version}."):
                # Check if it has chromedriver downloads
                downloads = version_info.get("downloads", {})
                if "chromedriver" in downloads:
                    versions.append(version)
        
        logger.info(f"Found {len(versions)} available ChromeDriver versions for major version {major_version}")
        if versions:
            logger.info(f"Available versions: {', '.join(versions[:5])}...")
        
        return versions
    except Exception as e:
        logger.error(f"Error getting available ChromeDriver versions: {str(e)}")
        return []

def download_chromedriver_manually(version, platform_name="mac"):
    """
    Manually download ChromeDriver for a specific version.
    
    Args:
        version (str): ChromeDriver version to download (e.g., "132.0.6225.0")
        platform_name (str): Platform name (mac, win, linux)
        
    Returns:
        str: Path to the downloaded ChromeDriver executable
    """
    # Create cache directory
    cache_dir = os.path.expanduser("~/.wdm/manual_drivers/chromedriver")
    os.makedirs(cache_dir, exist_ok=True)
    
    # Determine platform-specific details
    if platform_name == "mac":
        if platform.machine() == "arm64" or platform.machine() == "aarch64":
            platform_path = "mac-arm64"
            zip_name = "chromedriver-mac-arm64.zip"
        else:
            platform_path = "mac-x64"
            zip_name = "chromedriver-mac-x64.zip"
    elif platform_name == "win":
        platform_path = "win64"
        zip_name = "chromedriver-win64.zip"
    else:  # linux
        platform_path = "linux64"
        zip_name = "chromedriver-linux64.zip"
    
    # Construct download URL
    major_version = version.split('.')[0]
    download_url = f"https://storage.googleapis.com/chrome-for-testing-public/{version}/{platform_path}/{zip_name}"
    
    # Create version-specific directory
    driver_dir = os.path.join(cache_dir, version)
    driver_path = os.path.join(driver_dir, "chromedriver")
    if platform_name == "win":
        driver_path += ".exe"
    
    # Check if driver already exists
    if os.path.exists(driver_path):
        logger.info(f"ChromeDriver {version} already exists at {driver_path}")
        return driver_path
    
    # Download and extract ChromeDriver
    try:
        logger.info(f"Downloading ChromeDriver {version} from {download_url}")
        response = requests.get(download_url)
        response.raise_for_status()
        
        # Extract the zip file
        with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
            os.makedirs(driver_dir, exist_ok=True)
            
            # Extract all files
            zip_file.extractall(driver_dir)
            
            # Find the chromedriver executable in the extracted files
            chromedriver_path = None
            for root, dirs, files in os.walk(driver_dir):
                for file in files:
                    if file == "chromedriver" or file == "chromedriver.exe":
                        chromedriver_path = os.path.join(root, file)
                        break
                if chromedriver_path:
                    break
            
            if not chromedriver_path:
                raise Exception("ChromeDriver executable not found in the downloaded package")
            
            # Make the driver executable
            os.chmod(chromedriver_path, 0o755)
            
            logger.info(f"Successfully downloaded ChromeDriver {version} to {chromedriver_path}")
            return chromedriver_path
            
    except Exception as e:
        logger.error(f"Failed to download ChromeDriver {version}: {str(e)}")
        return None

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

def find_brave_path():
    """
    Find the path to the Brave browser executable.
    
    Returns:
        str: Path to Brave browser executable or None if not found.
    """
    # Common Brave browser paths by platform
    if platform.system() == "Darwin":  # macOS
        paths = [
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            os.path.expanduser("~/Applications/Brave Browser.app/Contents/MacOS/Brave Browser")
        ]
    elif platform.system() == "Windows":
        paths = [
            "C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe",
            "C:\\Program Files (x86)\\BraveSoftware\\Brave-Browser\\Application\\brave.exe",
            os.path.expanduser("~\\AppData\\Local\\BraveSoftware\\Brave-Browser\\Application\\brave.exe")
        ]
    else:  # Linux and others
        paths = [
            "/usr/bin/brave-browser",
            "/usr/bin/brave",
            "/snap/bin/brave",
            "/opt/brave.com/brave/brave-browser"
        ]
    
    # Check if any of the paths exist
    for path in paths:
        if os.path.exists(path):
            logger.info(f"Found Brave browser at: {path}")
            return path
    
    # If Brave is not found in common locations, try to find it using 'which' command on Unix-like systems
    if platform.system() != "Windows":
        try:
            brave_path = subprocess.check_output(["which", "brave-browser"], text=True).strip()
            if brave_path:
                logger.info(f"Found Brave browser using 'which' command at: {brave_path}")
                return brave_path
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
    
    logger.warning("Brave browser not found in common locations")
    return None

def setup_webdriver():
    """Set up and return Selenium WebDriver"""
    try:
        # Get headless mode setting from environment
        headless_value = os.getenv('HEADLESS', 'true').lower()
        logger.info(f"HEADLESS environment variable: {headless_value}")
        headless_mode = headless_value != "false"
        logger.info(f"Running in headless mode: {headless_mode}")
        
        # Get browser setting from environment (default to chrome)
        browser = os.getenv('BROWSER', 'chrome').lower()
        logger.info(f"BROWSER environment variable: {browser}")
        
        # Setup Chrome options
        logger.info(f"Setting up WebDriver for {browser}")
        options = webdriver.ChromeOptions()
        
        # Add options based on headless setting
        if headless_mode:
            options.add_argument('--headless=new')
        
        # Add other standard browser options
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        
        # Add options to block ads and improve stability
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-popup-blocking')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-infobars')
        options.add_argument('--mute-audio')
        
        # Find browser binary and determine browser version
        browser_binary = None
        browser_version = None
        chrome_type = None
        
        if browser == 'brave':
            browser_binary = find_brave_path()
            if browser_binary:
                logger.info(f"Using Brave at: {browser_binary}")
                options.binary_location = browser_binary
                chrome_type = ChromeType.BRAVE
                
                # Get Brave version
                try:
                    if platform.system() == "Windows":
                        import winreg
                        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\BraveSoftware\Brave-Browser\BLBeacon") as key:
                            browser_version = winreg.QueryValueEx(key, "version")[0]
                    else:
                        # For macOS and Linux, use the browser binary to get version
                        version_output = subprocess.check_output([browser_binary, "--version"], text=True)
                        version_parts = version_output.split()
                        for i, part in enumerate(version_parts):
                            if part.lower() == "version":
                                browser_version = version_parts[i+1]
                                break
                        if not browser_version and len(version_parts) > 0:
                            # Try to extract version from the output
                            for part in version_parts:
                                if part[0].isdigit():
                                    browser_version = part
                                    break
                    
                    if browser_version:
                        logger.info(f"Detected Brave version: {browser_version}")
                except Exception as e:
                    logger.warning(f"Could not determine Brave version: {str(e)}")
            else:
                logger.warning("Brave browser not found. Falling back to Chrome.")
                browser = 'chrome'  # Fall back to Chrome
        
        if browser == 'chrome':
            browser_binary = find_chrome_path()
            if browser_binary:
                logger.info(f"Using Chrome at: {browser_binary}")
                options.binary_location = browser_binary
                chrome_type = ChromeType.GOOGLE
        
        # Use ChromeDriverManager to get the correct version
        logger.info(f"Using ChromeDriverManager to get matching ChromeDriver version for {browser}")
        
        # Check webdriver-manager version to use the appropriate API
        wdm_version = get_package_version("webdriver-manager")
        logger.info(f"Detected webdriver-manager version: {wdm_version}")
        
        if chrome_type == ChromeType.BRAVE and browser_version:
            # For Brave, use the detected version to get a compatible ChromeDriver
            major_version = browser_version.split('.')[0]
            logger.info(f"Using Brave major version {major_version} for ChromeDriver")
            
            # Handle different webdriver-manager versions
            if wdm_version and wdm_version.startswith("4."):
                # For webdriver-manager 4.x, use environment variable
                logger.info("Using webdriver-manager 4.x API")
                
                # Try to manually download the exact matching ChromeDriver version
                try:
                    # For Brave 132, we need ChromeDriver 132
                    # Get available versions for this major version
                    available_versions = get_available_chromedriver_versions(major_version)
                    
                    if available_versions:
                        # Use the first available version
                        chromedriver_version = available_versions[0]
                        logger.info(f"Using available ChromeDriver version {chromedriver_version}")
                    else:
                        # Fall back to known versions if API check fails
                        if major_version == "132":
                            # Update to a known working version for Brave 132
                            chromedriver_version = "132.0.6243.0"  # Try this version for 132
                        elif major_version == "133":
                            chromedriver_version = "133.0.6943.0"  # Known working version for 133
                        else:
                            # For other versions, use a default format
                            chromedriver_version = f"{major_version}.0.6243.0"
                    
                    logger.info(f"Attempting to manually download ChromeDriver version {chromedriver_version}")
                    
                    # Determine platform
                    if platform.system() == "Windows":
                        platform_name = "win"
                    elif platform.system() == "Darwin":  # macOS
                        platform_name = "mac"
                    else:
                        platform_name = "linux"
                    
                    # Download the driver
                    driver_path = download_chromedriver_manually(chromedriver_version, platform_name)
                    
                    if driver_path and os.path.exists(driver_path):
                        logger.info(f"Successfully downloaded ChromeDriver {chromedriver_version}")
                        
                        # Create a service with the manually downloaded driver
                        service = Service(executable_path=driver_path)
                        
                        # Create the driver with the service and options
                        driver = webdriver.Chrome(service=service, options=options)
                        return driver
                    else:
                        logger.warning(f"Failed to manually download ChromeDriver {chromedriver_version}, falling back to WebDriverManager")
                except Exception as e:
                    logger.warning(f"Error during manual ChromeDriver download: {str(e)}")
                    logger.warning("Falling back to WebDriverManager")
                
                # Fall back to WebDriverManager if manual download fails
                # Try to force exact version match for ChromeDriver
                try:
                    # For Brave 132, try to download ChromeDriver 132
                    if major_version == "132":
                        # Try to download a specific version that's known to work with Brave 132
                        logger.info("Attempting to download ChromeDriver 132 using direct approach")
                        
                        # Try multiple known versions that might work with Brave 132
                        # If we already have available_versions from the API, use those
                        versions_to_try = available_versions[:3] if available_versions else ["132.0.6243.0", "132.0.6225.0", "132.0.6195.0"]
                        
                        for version_to_try in versions_to_try:
                            logger.info(f"Trying ChromeDriver version {version_to_try}")
                            driver_path = download_chromedriver_manually(version_to_try, platform_name)
                            if driver_path and os.path.exists(driver_path):
                                logger.info(f"Successfully downloaded ChromeDriver {version_to_try}")
                                service = Service(executable_path=driver_path)
                                driver = webdriver.Chrome(service=service, options=options)
                                return driver
                    
                    # If we get here, none of the specific versions worked
                    logger.warning("Could not find a compatible ChromeDriver version, using WebDriverManager")
                except Exception as e:
                    logger.warning(f"Error during direct ChromeDriver download: {str(e)}")
                
                # If all else fails, try WebDriverManager with environment variables
                os.environ['WDM_CHROMEDRIVER_VERSION'] = 'latest'  # Reset any previous setting
                os.environ['WDM_CHROME_VERSION'] = major_version
                
                # In webdriver-manager 4.x, Brave browser support might be limited
                # Fall back to using Chrome driver directly
                logger.info("Using Chrome driver for Brave browser (compatibility mode)")
                chrome_type = ChromeType.GOOGLE
                
                # Create a custom ChromeDriverManager that will download the exact matching version
                driver_manager = ChromeDriverManager(chrome_type=chrome_type)
            else:
                # For older versions, use version parameter
                logger.info("Using webdriver-manager 3.x API")
                try:
                    driver_manager = ChromeDriverManager(chrome_type=chrome_type, version=f"{major_version}.0.0.0")
                except TypeError:
                    # Fallback if version parameter doesn't work
                    logger.warning("Version parameter not supported, using environment variable instead")
                    os.environ['WDM_CHROME_VERSION'] = major_version
                    # Fall back to Chrome driver
                    chrome_type = ChromeType.GOOGLE
                    driver_manager = ChromeDriverManager(chrome_type=chrome_type)
        else:
            # Default behavior - get latest ChromeDriver
            driver_manager = ChromeDriverManager(chrome_type=chrome_type)
            
        driver_path = driver_manager.install()
        
        # Find the actual chromedriver executable
        if "THIRD_PARTY_NOTICES" in driver_path:
            driver_dir = os.path.dirname(driver_path)
            for root, dirs, files in os.walk(driver_dir):
                for file in files:
                    if file == "chromedriver" or file == "chromedriver.exe":
                        driver_path = os.path.join(root, file)
                        logger.info(f"Found actual ChromeDriver at: {driver_path}")
                        break
                if "chromedriver" in files or "chromedriver.exe" in files:
                    break
        
        if not os.path.exists(driver_path):
            raise Exception(f"ChromeDriver executable not found")
        
        # Make sure the ChromeDriver is executable
        os.chmod(driver_path, 0o755)
        logger.info(f"Set executable permissions for ChromeDriver at: {driver_path}")
        
        # Create ChromeDriver service
        service = Service(executable_path=driver_path)
        
        # Create and return the WebDriver
        driver = webdriver.Chrome(service=service, options=options)
        
        # Set page load timeout
        driver.set_page_load_timeout(30)
        
        logger.info(f"WebDriver setup successful for {browser}")
        return driver
        
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

def clear_chromedriver_cache():
    """
    Clear the ChromeDriver cache to fix browser compatibility issues.
    This is useful when switching between browsers or when browser versions change.
    
    Returns:
        bool: True if the cache was cleared successfully, False otherwise
    """
    try:
        # Clear the WebDriverManager cache
        wdm_cache_dir = os.path.expanduser("~/.wdm/drivers/chromedriver")
        logger.info(f"Clearing ChromeDriver cache at {wdm_cache_dir}")
        
        if os.path.exists(wdm_cache_dir):
            if platform.system() == "Windows":
                # On Windows, some files might be locked, so use shutil.rmtree with ignore_errors
                import shutil
                shutil.rmtree(wdm_cache_dir, ignore_errors=True)
            else:
                # On Unix-like systems, use subprocess for better error handling
                import subprocess
                subprocess.run(["rm", "-rf", wdm_cache_dir], check=True)
        
        # Clear the manual driver cache
        manual_cache_dir = os.path.expanduser("~/.wdm/manual_drivers/chromedriver")
        if os.path.exists(manual_cache_dir):
            logger.info(f"Clearing manual ChromeDriver cache at {manual_cache_dir}")
            if platform.system() == "Windows":
                import shutil
                shutil.rmtree(manual_cache_dir, ignore_errors=True)
            else:
                import subprocess
                subprocess.run(["rm", "-rf", manual_cache_dir], check=True)
        
        logger.info("ChromeDriver cache cleared successfully")
        return True
    except Exception as e:
        logger.error(f"Error clearing ChromeDriver cache: {str(e)}")
        return False 