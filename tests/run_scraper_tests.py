#!/usr/bin/env python3
"""
Runner script for scraper tests.

This script provides a command-line interface to run various scraper tests,
either individually or as a complete flow.

Usage:
    python -m tests.run_scraper_tests [--test TEST_NAME] [--all]

Options:
    --test TEST_NAME    Run a specific test (login, scrape, api, flow)
    --all               Run all tests in sequence
"""

import argparse
import asyncio
import os
import sys
import time

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.logger import logger

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Run scraper tests")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--test", choices=["login", "scrape", "api", "flow"],
                      help="Run a specific test")
    group.add_argument("--all", action="store_true",
                      help="Run all tests in sequence")
    
    return parser.parse_args()

async def run_login_test():
    """Run the login test."""
    logger.info("Running login test")
    
    from tests.test_login import test_login
    test_login()
    
    logger.info("Login test completed")

async def run_scraper_test():
    """Run the scraper test."""
    logger.info("Running scraper test")
    
    from tests.test_async_scraper import test_earnings_list_scraper
    await test_earnings_list_scraper()
    
    logger.info("Scraper test completed")

def run_api_test():
    """Run the API test."""
    logger.info("Running API test")
    
    from tests.test_api import test_get_holdings, test_get_market_data, test_get_stock_details
    
    # Run API tests
    test_get_holdings()
    test_get_market_data()
    test_get_stock_details()
    
    logger.info("API test completed")

async def run_flow_test():
    """Run the complete flow test."""
    logger.info("Running complete flow test")
    
    from tests.test_scraper_flow import main as flow_main
    await flow_main()
    
    logger.info("Flow test completed")

async def run_all_tests():
    """Run all tests in sequence."""
    logger.info("Running all tests")
    
    # Run tests in sequence
    await run_login_test()
    time.sleep(2)  # Give time for resources to clean up
    
    await run_scraper_test()
    time.sleep(2)
    
    run_api_test()
    time.sleep(2)
    
    await run_flow_test()
    
    logger.info("All tests completed")

async def main():
    """Main function."""
    args = parse_args()
    
    if args.all:
        await run_all_tests()
    elif args.test == "login":
        await run_login_test()
    elif args.test == "scrape":
        await run_scraper_test()
    elif args.test == "api":
        run_api_test()
    elif args.test == "flow":
        await run_flow_test()

if __name__ == "__main__":
    asyncio.run(main()) 