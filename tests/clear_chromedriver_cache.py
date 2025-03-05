#!/usr/bin/env python
"""
Utility script to clear the ChromeDriver cache.
This can be useful when switching between browsers or when browser versions change.
"""
import os
import sys
import logging

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import the clear_chromedriver_cache function
from src.scraper.scraper_login import clear_chromedriver_cache
from src.utils.logger import logger

def main():
    """Main function to clear the ChromeDriver cache."""
    logger.setLevel(logging.INFO)
    
    print("Clearing ChromeDriver cache...")
    success = clear_chromedriver_cache()
    
    if success:
        print("ChromeDriver cache cleared successfully.")
        print("Next time you run the scraper, a fresh ChromeDriver will be downloaded.")
    else:
        print("Failed to clear ChromeDriver cache. See logs for details.")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())