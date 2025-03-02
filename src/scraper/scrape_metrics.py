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

        # Extract KnowBeforeYouInvest section data
        try:
            logger.info("Starting extraction of KnowBeforeYouInvest section data")
            
            # Log the HTML structure of the KnowBeforeYouInvest section for debugging
            try:
                know_before_section = detailed_soup.select_one('#knowBeforeInvest')
                if know_before_section:
                    logger.info("Found #knowBeforeInvest section")
                    # Log a sample of the HTML to help debug selectors
                    logger.info(f"KnowBeforeYouInvest section HTML sample: {str(know_before_section)[:500]}...")
                else:
                    logger.warning("Could not find #knowBeforeInvest section")
            except Exception as e:
                logger.warning(f"Error examining KnowBeforeYouInvest section: {str(e)}")
            
            # Strengths - try multiple selectors
            strengths_selectors = [
                '#swot_ls > a > strong',
                '.swotls strong',
                '#swot_ls strong',
                '.swot_ls strong'
            ]
            
            for selector in strengths_selectors:
                strengths_element = detailed_soup.select_one(selector)
                if strengths_element:
                    metrics["strengths"] = strengths_element.text.strip()
                    logger.info(f"Found strengths with selector '{selector}': {metrics['strengths']}")
                    break
            
            if not metrics["strengths"]:
                logger.warning(f"No strengths element found with any of these selectors: {strengths_selectors}")
            
            # Weaknesses - try multiple selectors
            weaknesses_selectors = [
                '#swot_lw > a > strong',
                '.swotlw strong',
                '#swot_lw strong',
                '.swot_lw strong'
            ]
            
            for selector in weaknesses_selectors:
                weaknesses_element = detailed_soup.select_one(selector)
                if weaknesses_element:
                    metrics["weaknesses"] = weaknesses_element.text.strip()
                    logger.info(f"Found weaknesses with selector '{selector}': {metrics['weaknesses']}")
                    break
            
            if not metrics["weaknesses"]:
                logger.warning(f"No weaknesses element found with any of these selectors: {weaknesses_selectors}")
            
            # Technicals trend - try multiple selectors
            technicals_selectors = [
                '#techAnalysis a[style*="flex"]',
                '#techAnalysis a',
                '.techAnalysis a'
            ]
            
            for selector in technicals_selectors:
                technicals_element = detailed_soup.select_one(selector)
                if technicals_element:
                    metrics["technicals_trend"] = technicals_element.text.strip()
                    logger.info(f"Found technicals trend with selector '{selector}': {metrics['technicals_trend']}")
                    break
            
            if not metrics["technicals_trend"]:
                logger.warning(f"No technicals trend element found with any of these selectors: {technicals_selectors}")
            
            # Piotroski score - try multiple selectors
            piotroski_selectors = [
                'div:nth-child(2) div.fpioi div.nof',
                '.fpioi .nof',
                '#knowBeforeInvest .fpioi .nof'
            ]
            
            for selector in piotroski_selectors:
                piotroski_element = detailed_soup.select_one(selector)
                if piotroski_element:
                    metrics["piotroski_score"] = piotroski_element.text.strip()
                    logger.info(f"Found Piotroski score with selector '{selector}': {metrics['piotroski_score']}")
                    break
            
            if not metrics["piotroski_score"]:
                logger.warning(f"No Piotroski score element found with any of these selectors: {piotroski_selectors}")
            
            # CAGR values - try multiple selectors
            revenue_cagr_selectors = [
                'tr:-soup-contains("Revenue") td:nth-child(2)',
                'tr:contains("Revenue") td:nth-child(2)',
                '#knowBeforeInvest tr:contains("Revenue") td:nth-child(2)'
            ]
            
            for selector in revenue_cagr_selectors:
                try:
                    revenue_cagr_element = detailed_soup.select_one(selector)
                    if revenue_cagr_element:
                        metrics["revenue_growth_3yr_cagr"] = revenue_cagr_element.text.strip()
                        logger.info(f"Found revenue CAGR with selector '{selector}': {metrics['revenue_growth_3yr_cagr']}")
                        break
                except Exception as e:
                    logger.warning(f"Error with selector '{selector}': {str(e)}")
            
            if not metrics["revenue_growth_3yr_cagr"]:
                logger.warning(f"No revenue CAGR element found with any of these selectors: {revenue_cagr_selectors}")
            
            # Try to find all tables and look for CAGR data
            try:
                tables = detailed_soup.select('table')
                logger.info(f"Found {len(tables)} tables on the page")
                
                for i, table in enumerate(tables):
                    logger.info(f"Table {i+1} content sample: {str(table)[:200]}...")
                    
                    # Look for CAGR related text in the table
                    if 'CAGR' in str(table) or 'Revenue' in str(table) or 'Profit' in str(table):
                        logger.info(f"Table {i+1} might contain CAGR data")
            except Exception as e:
                logger.warning(f"Error examining tables: {str(e)}")
            
            logger.info("Completed extraction of KnowBeforeYouInvest section data")
        except Exception as e:
            logger.warning(f"Error extracting KnowBeforeYouInvest data: {str(e)}")

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