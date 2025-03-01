"""
Test script for the MoneyControl scraper.
"""
import asyncio
import logging
import os
from dotenv import load_dotenv
from src.scraper.moneycontrol_scraper import scrape_moneycontrol_earnings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("scraper_test.log")
    ]
)

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

async def test_scraper():
    """
    Test the MoneyControl scraper with different result types.
    """
    # URLs for different result types
    urls = {
        "Latest Results": "https://www.moneycontrol.com/stocks/marketinfo/earnings/results.php",
        "Best Performer": "https://www.moneycontrol.com/stocks/marketinfo/earnings/results.php?tab=BP",
        "Worst Performer": "https://www.moneycontrol.com/stocks/marketinfo/earnings/results.php?tab=WP",
        "Positive Turnaround": "https://www.moneycontrol.com/stocks/marketinfo/earnings/results.php?tab=PT",
        "Negative Turnaround": "https://www.moneycontrol.com/stocks/marketinfo/earnings/results.php?tab=NT"
    }
    
    # Test with the Latest Results URL first
    url = urls["Latest Results"]
    logger.info(f"Testing scraper with URL: {url}")
    
    try:
        results = await scrape_moneycontrol_earnings(url)
        logger.info(f"Scraping completed. Found {len(results)} results.")
        
        # Print the first result for verification
        if results:
            logger.info(f"First result: {results[0]['company_name']}")
            logger.info(f"Financial metrics: {results[0]['financial_metrics']}")
        else:
            logger.warning("No results found.")
            
    except Exception as e:
        logger.error(f"Error during scraping test: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_scraper()) 