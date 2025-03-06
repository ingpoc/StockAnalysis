"""
MoneyControl scraper module for fetching financial data.
"""

from src.scraper.scrapedata import (
    scrape_moneycontrol_earnings,
    scrape_by_result_type,
    scrape_custom_url
)
from src.scraper.browser_setup import setup_webdriver, login_to_moneycontrol
from src.scraper.extract_metrics import (
    extract_financial_data,
    extract_company_info,
    process_financial_data
)
from src.scraper.db_operations import (
    get_db_connection,
    get_db_collection,
    store_financial_data,
    store_multiple_financial_data,
    get_financial_data_by_company,
    get_financial_data_by_symbol,
    remove_quarter_from_all_companies
) 