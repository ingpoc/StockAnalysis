"""
Module for scraping financial metrics from MoneyControl.
"""
import logging
import datetime
from typing import Dict, Any, Optional, Tuple, Union
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    StaleElementReferenceException
)
from motor.motor_asyncio import AsyncIOMotorCollection

logger = logging.getLogger(__name__)

def extract_financial_data(card):
    """
    Extracts basic financial data from a result card element.
    
    Args:
        card (bs4.element.Tag): BeautifulSoup Tag object representing a company result card.
        
    Returns:
        dict: Dictionary containing extracted financial data.
    """
    try:
        # Create a dictionary with all the financial data
        financial_data = {
            "cmp": None,
            "revenue": None,
            "gross_profit": None,
            "net_profit": None,
            "net_profit_growth": None,
            "gross_profit_growth": None,
            "revenue_growth": None,
            "quarter": None,
            "result_date": None,
            "report_type": None,
        }
        
        # Safely extract each piece of data
        try:
            if card.select_one('p.rapidResCardWeb_priceTxt___5MvY'):
                financial_data["cmp"] = card.select_one('p.rapidResCardWeb_priceTxt___5MvY').text.strip()
        except Exception as e:
            logger.debug(f"Error extracting CMP: {str(e)}")
            
        try:
            if card.select_one('tr:nth-child(1) td:nth-child(2)'):
                financial_data["revenue"] = card.select_one('tr:nth-child(1) td:nth-child(2)').text.strip()
        except Exception as e:
            logger.debug(f"Error extracting revenue: {str(e)}")
            
        try:
            if card.select_one('tr:nth-child(2) td:nth-child(2)'):
                financial_data["gross_profit"] = card.select_one('tr:nth-child(2) td:nth-child(2)').text.strip()
        except Exception as e:
            logger.debug(f"Error extracting gross profit: {str(e)}")
            
        try:
            if card.select_one('tr:nth-child(3) td:nth-child(2)'):
                financial_data["net_profit"] = card.select_one('tr:nth-child(3) td:nth-child(2)').text.strip()
        except Exception as e:
            logger.debug(f"Error extracting net profit: {str(e)}")
            
        try:
            if card.select_one('tr:nth-child(3) td:nth-child(4)'):
                financial_data["net_profit_growth"] = card.select_one('tr:nth-child(3) td:nth-child(4)').text.strip()
        except Exception as e:
            logger.debug(f"Error extracting net profit growth: {str(e)}")
            
        try:
            if card.select_one('tr:nth-child(2) td:nth-child(4)'):
                financial_data["gross_profit_growth"] = card.select_one('tr:nth-child(2) td:nth-child(4)').text.strip()
        except Exception as e:
            logger.debug(f"Error extracting gross profit growth: {str(e)}")
            
        try:
            if card.select_one('tr:nth-child(1) td:nth-child(4)'):
                financial_data["revenue_growth"] = card.select_one('tr:nth-child(1) td:nth-child(4)').text.strip()
        except Exception as e:
            logger.debug(f"Error extracting revenue growth: {str(e)}")
            
        try:
            if card.select_one('tr th:nth-child(1)'):
                financial_data["quarter"] = card.select_one('tr th:nth-child(1)').text.strip()
        except Exception as e:
            logger.debug(f"Error extracting quarter: {str(e)}")
            
        try:
            if card.select_one('p.rapidResCardWeb_gryTxtOne__mEhU_'):
                financial_data["result_date"] = card.select_one('p.rapidResCardWeb_gryTxtOne__mEhU_').text.strip()
        except Exception as e:
            logger.debug(f"Error extracting result date: {str(e)}")
            
        try:
            if card.select_one('p.rapidResCardWeb_bottomText__p8YzI'):
                financial_data["report_type"] = card.select_one('p.rapidResCardWeb_bottomText__p8YzI').text.strip()
        except Exception as e:
            logger.debug(f"Error extracting report type: {str(e)}")
            
        return financial_data
    except Exception as e:
        logger.error(f"Error extracting financial data: {str(e)}")
        return {}

def scrape_financial_metrics(driver, stock_link):
    """
    Scrapes detailed financial metrics from a stock's page.
    
    Args:
        driver (webdriver.Chrome): Chrome WebDriver instance.
        stock_link (str): URL to the stock's page.
        
    Returns:
        tuple: (metrics_dict, symbol_str) - Dictionary with financial metrics and stock symbol.
    """
    original_window = driver.current_window_handle
    try:
        # Open a new tab and navigate to the stock page
        driver.execute_script(f"window.open('{stock_link}', '_blank');")
        driver.switch_to.window(driver.window_handles[-1])
        
        # Wait for the page to load
        try:
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'body')))
        except TimeoutException:
            logger.warning(f"Timeout waiting for stock page to load: {stock_link}")
            driver.close()
            driver.switch_to.window(original_window)
            return None, None
        
        # Initialize metrics dictionary with default None values
        metrics = {
            "market_cap": None,
            "face_value": None,
            "book_value": None,
            "dividend_yield": None,
            "ttm_eps": None,
            "ttm_pe": None,
            "pb_ratio": None,
            "sector_pe": None,
            "piotroski_score": None,
            "revenue_growth_3yr_cagr": None,
            "net_profit_growth_3yr_cagr": None,
            "operating_profit_growth_3yr_cagr": None,
            "strengths": None,
            "weaknesses": None,
            "technicals_trend": None,
            "fundamental_insights": None,
            "fundamental_insights_description": None
        }
        
        detailed_soup = BeautifulSoup(driver.page_source, 'html.parser')
        symbol = None
        
        # Safely extract each metric
        try:
            if detailed_soup.select_one('tr:nth-child(7) td.nsemktcap.bsemktcap'):
                metrics["market_cap"] = detailed_soup.select_one('tr:nth-child(7) td.nsemktcap.bsemktcap').text.strip()
        except Exception as e:
            logger.debug(f"Error extracting market cap: {str(e)}")
            
        try:
            if detailed_soup.select_one('tr:nth-child(7) td.nsefv.bsefv'):
                metrics["face_value"] = detailed_soup.select_one('tr:nth-child(7) td.nsefv.bsefv').text.strip()
        except Exception as e:
            logger.debug(f"Error extracting face value: {str(e)}")
            
        try:
            if detailed_soup.select_one('tr:nth-child(5) td.nsebv.bsebv'):
                metrics["book_value"] = detailed_soup.select_one('tr:nth-child(5) td.nsebv.bsebv').text.strip()
        except Exception as e:
            logger.debug(f"Error extracting book value: {str(e)}")
            
        try:
            if detailed_soup.select_one('tr:nth-child(6) td.nsedy.bsedy'):
                metrics["dividend_yield"] = detailed_soup.select_one('tr:nth-child(6) td.nsedy.bsedy').text.strip()
        except Exception as e:
            logger.debug(f"Error extracting dividend yield: {str(e)}")
            
        try:
            if detailed_soup.select_one('tr:nth-child(1) td:nth-child(2) span.nseceps.bseceps'):
                metrics["ttm_eps"] = detailed_soup.select_one('tr:nth-child(1) td:nth-child(2) span.nseceps.bseceps').text.strip()
        except Exception as e:
            logger.debug(f"Error extracting TTM EPS: {str(e)}")
            
        try:
            if detailed_soup.select_one('tr:nth-child(2) td:nth-child(2) span.nsepe.bsepe'):
                metrics["ttm_pe"] = detailed_soup.select_one('tr:nth-child(2) td:nth-child(2) span.nsepe.bsepe').text.strip()
        except Exception as e:
            logger.debug(f"Error extracting TTM PE: {str(e)}")
            
        try:
            if detailed_soup.select_one('tr:nth-child(3) td:nth-child(2) span.nsepb.bsepb'):
                metrics["pb_ratio"] = detailed_soup.select_one('tr:nth-child(3) td:nth-child(2) span.nsepb.bsepb').text.strip()
        except Exception as e:
            logger.debug(f"Error extracting PB ratio: {str(e)}")
            
        try:
            if detailed_soup.select_one('tr:nth-child(4) td.nsesc_ttm.bsesc_ttm'):
                metrics["sector_pe"] = detailed_soup.select_one('tr:nth-child(4) td.nsesc_ttm.bsesc_ttm').text.strip()
        except Exception as e:
            logger.debug(f"Error extracting sector PE: {str(e)}")
            
        # Extract company symbol
        try:
            if detailed_soup.select_one('#company_info > ul > li:nth-child(5) > ul > li:nth-child(2) > p'):
                symbol = detailed_soup.select_one('#company_info > ul > li:nth-child(5) > ul > li:nth-child(2) > p').text.strip()
        except Exception as e:
            logger.debug(f"Error extracting symbol: {str(e)}")
            
        # Try alternative selectors for symbol if the primary one failed
        if not symbol:
            try:
                # Try to find symbol in the page title
                title = detailed_soup.select_one('title')
                if title and '(' in title.text and ')' in title.text:
                    symbol_part = title.text.split('(')[1].split(')')[0]
                    if symbol_part:
                        symbol = symbol_part
            except Exception as e:
                logger.debug(f"Error extracting symbol from title: {str(e)}")

        # Close the tab and switch back to the original window
        driver.close()
        driver.switch_to.window(original_window)

        return metrics, symbol
        
    except Exception as e:
        logger.error(f"Error scraping financial metrics: {str(e)}")
        
        # Make sure to close the new tab and switch back
        try:
            # Check if we're not in the original window
            if driver.current_window_handle != original_window:
                driver.close()
                driver.switch_to.window(original_window)
        except Exception as close_error:
            logger.error(f"Error closing tab: {str(close_error)}")
            
        return None, None

async def process_result_card(card, driver, db_collection=None):
    """
    Processes a company result card and saves the data to the database.
    
    Args:
        card (bs4.element.Tag): BeautifulSoup Tag object representing a company result card.
        driver (webdriver.Chrome): Chrome WebDriver instance.
        db_collection (AsyncIOMotorCollection, optional): MongoDB collection to store the data.
        
    Returns:
        dict: Dictionary with the processed company data.
    """
    try:
        company_name = card.select_one('h3 a').text.strip() if card.select_one('h3 a') else None
        if not company_name:
            logger.warning("Skipping card due to missing company name.")
            return None

        stock_link = card.select_one('h3 a')['href'] if card.select_one('h3 a') and 'href' in card.select_one('h3 a').attrs else None
        if not stock_link:
            logger.warning(f"Skipping {company_name} due to missing stock link.")
            return None

        logger.info(f"Processing stock: {company_name}")

        # Extract basic financial data from the card
        financial_data = extract_financial_data(card)
        if not financial_data or not financial_data.get('quarter'):
            logger.warning(f"Skipping {company_name} due to missing quarter information.")
            return None
        
        # Check if this company already exists in the database with this quarter's data
        existing_company = None
        if db_collection is not None:
            try:
                existing_company = await db_collection.find_one({"company_name": company_name})
                if existing_company is not None:
                    existing_quarters = [metric.get('quarter') for metric in existing_company.get('financial_metrics', []) if metric.get('quarter')]
                    if financial_data.get('quarter') in existing_quarters:
                        logger.info(f"{company_name} already has data for {financial_data.get('quarter')}. Skipping.")
                        return None
            except Exception as e:
                logger.error(f"Error checking existing data for {company_name}: {str(e)}")
                # Continue with the scraping even if the database check fails

        # Fetch additional metrics from the stock's page
        additional_metrics, symbol = None, None
        try:
            additional_metrics, symbol = scrape_financial_metrics(driver, stock_link)
        except Exception as e:
            logger.error(f"Error fetching additional metrics for {company_name}: {str(e)}")
            # Continue with basic data if additional metrics fail

        if additional_metrics is not None:
            financial_data.update(additional_metrics)

        # Prepare the complete company data
        stock_data = {
            "company_name": company_name,
            "symbol": symbol,
            "financial_metrics": financial_data,
            "timestamp": datetime.datetime.utcnow()
        }

        # Save to database if a collection was provided
        if db_collection is not None and financial_data.get('quarter') is not None:
            try:
                if existing_company is not None:
                    logger.info(f"Adding new data for {company_name} - {financial_data.get('quarter')}")
                    await db_collection.update_one(
                        {"company_name": company_name},
                        {"$push": {"financial_metrics": financial_data}}
                    )
                else:
                    logger.info(f"Creating new entry for {company_name}")
                    new_stock_data = {
                        "company_name": company_name,
                        "symbol": symbol,
                        "financial_metrics": [financial_data],
                        "timestamp": datetime.datetime.utcnow()
                    }
                    await db_collection.insert_one(new_stock_data)
                    
                logger.info(f"Data for {company_name} (quarter {financial_data.get('quarter')}) processed successfully.")
            except Exception as e:
                logger.error(f"Database error for {company_name}: {str(e)}")
                # Return the data even if database operation fails
        
        return stock_data

    except Exception as e:
        logger.error(f"Error processing result card: {str(e)}")
        return None