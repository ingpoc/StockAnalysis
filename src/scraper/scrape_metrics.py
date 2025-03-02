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
import re

logger = logging.getLogger(__name__)

def extract_financial_data(card_soup: BeautifulSoup) -> Dict[str, Any]:
    """
    Extract financial data from a result card.
    
    Args:
        card_soup (BeautifulSoup): BeautifulSoup object of the result card.
        
    Returns:
        Dict[str, Any]: Dictionary of financial data.
    """
    try:
        logger.info("Extracting financial data from result card")
        
        # Initialize with None to indicate data not found
        financial_data = {
            "quarter": None,
            "cmp": None,
            "revenue": None,
            "gross_profit": None,
            "net_profit": None,
            "net_profit_growth": None,
            "gross_profit_growth": None,
            "revenue_growth": None,
            "result_date": None,
            "report_type": None
        }
        
        # Try to extract quarter information - try multiple selectors
        try:
            # Primary selector for quarter
            quarter_element = card_soup.select_one('tr th:nth-child(1)')
            if quarter_element and quarter_element.text.strip():
                financial_data["quarter"] = quarter_element.text.strip()
                logger.info(f"Found quarter: {financial_data['quarter']}")
            
            # Alternative selectors if primary fails
            if not financial_data["quarter"]:
                alt_selectors = [
                    '.quarterPeriod', 
                    'th:contains("Quarter")', 
                    'th:contains("Q")', 
                    '.qprd',
                    '[class*="quarter"]',
                    '[class*="period"]'
                ]
                
                for selector in alt_selectors:
                    try:
                        element = None
                        if ':contains' in selector:
                            # Handle custom contains selector
                            tag_name = selector.split(':contains')[0]
                            search_text = selector.split('(')[1].split(')')[0].replace('"', '')
                            elements = card_soup.find_all(tag_name)
                            for el in elements:
                                if search_text in el.text:
                                    element = el
                                    break
                        else:
                            element = card_soup.select_one(selector)
                            
                        if element and element.text.strip():
                            financial_data["quarter"] = element.text.strip()
                            logger.info(f"Found quarter with alternate selector '{selector}': {financial_data['quarter']}")
                            break
                    except Exception as e:
                        logger.debug(f"Error with alternate selector '{selector}': {str(e)}")
            
            # If still not found, try to extract from any text that looks like a quarter
            if not financial_data["quarter"]:
                all_text = card_soup.get_text()
                quarter_patterns = [
                    r'Q[1-4]\s+\d{4}',                  # Q1 2023
                    r'Q[1-4]\s+FY\d{2}',                # Q1 FY23
                    r'Q[1-4]\s+FY\d{2}-\d{2}',          # Q1 FY23-24
                    r'Quarter\s+[1-4]\s+\d{4}',         # Quarter 1 2023
                    r'Quarter\s+[1-4]\s+FY\d{2}',       # Quarter 1 FY23
                    r'Quarter\s+[1-4]\s+FY\d{2}-\d{2}'  # Quarter 1 FY23-24
                ]
                
                for pattern in quarter_patterns:
                    match = re.search(pattern, all_text)
                    if match:
                        financial_data["quarter"] = match.group(0)
                        logger.info(f"Found quarter with regex pattern: {financial_data['quarter']}")
                        break
        except Exception as e:
            logger.warning(f"Error extracting quarter: {str(e)}")
            
        # If quarter still not found, use current quarter as fallback
        if not financial_data["quarter"]:
            current_month = datetime.datetime.now().month
            current_year = datetime.datetime.now().year
            quarter = (current_month - 1) // 3 + 1
            financial_data["quarter"] = f"Q{quarter} FY{str(current_year)[2:]}-{str(current_year+1)[2:]}"
            logger.info(f"Using default quarter: {financial_data['quarter']}")
        
        # Try to extract Current Market Price (CMP)
        try:
            # Try multiple selectors for CMP
            cmp_selectors = [
                'tr td.clrAcl span.rGrn, tr td.clrAcl span.rRed',
                'td[class*="cmp"] span',
                '.currentPrice',
                'span[class*="price"]',
                '.price',
                'td:contains("CMP")',
                '.stock-price',
                '.stprice',
                '.priceinfo span',
                '.price_wrapper span',
                '.stock_price',
                '.nse_bse_sub_prices span:first-child',
                '.stock_details .price',
                '.stock-current-price'
            ]
            
            for selector in cmp_selectors:
                try:
                    element = None
                    if ':contains' in selector:
                        # Handle custom contains selector
                        tag_name = selector.split(':contains')[0]
                        search_text = selector.split('(')[1].split(')')[0].replace('"', '')
                        elements = card_soup.find_all(tag_name)
                        for el in elements:
                            if search_text in el.text:
                                # Get the next sibling or child that might contain the price
                                next_el = el.find_next()
                                if next_el:
                                    element = next_el
                                break
                    else:
                        element = card_soup.select_one(selector)
                        
                    if element and element.text.strip():
                        financial_data["cmp"] = element.text.strip()
                        logger.info(f"Found CMP with selector '{selector}': {financial_data['cmp']}")
                        break
                except Exception as e:
                    logger.debug(f"Error with CMP selector '{selector}': {str(e)}")
                    
            # If still not found, try to find any element with price-like content
            if not financial_data["cmp"]:
                # Look for elements containing ₹ symbol or Rs.
                price_patterns = [
                    r'₹\s*[\d,.]+',
                    r'Rs\.\s*[\d,.]+',
                    r'INR\s*[\d,.]+',
                    r'NSE\s*:\s*[\d,.]+',
                    r'BSE\s*:\s*[\d,.]+',
                    r'CMP\s*:\s*[\d,.]+',
                    r'Price\s*:\s*[\d,.]+',
                    r'Current\s*Price\s*:\s*[\d,.]+',
                ]
                
                all_text = card_soup.get_text()
                for pattern in price_patterns:
                    match = re.search(pattern, all_text)
                    if match:
                        financial_data["cmp"] = match.group(0)
                        logger.info(f"Found CMP with regex pattern: {financial_data['cmp']}")
                        break
        except Exception as e:
            logger.warning(f"Error extracting CMP: {str(e)}")
        
        # Helper function to extract metric with multiple selectors
        def extract_metric(metric_name, primary_selector, alternate_selectors=None):
            try:
                element = card_soup.select_one(primary_selector)
                if element and element.text.strip():
                    value = element.text.strip()
                    financial_data[metric_name] = value
                    logger.info(f"Found {metric_name}: {value}")
                    return True
                
                if alternate_selectors:
                    for selector in alternate_selectors:
                        try:
                            element = card_soup.select_one(selector)
                            if element and element.text.strip():
                                value = element.text.strip()
                                financial_data[metric_name] = value
                                logger.info(f"Found {metric_name} with alternate selector '{selector}': {value}")
                                return True
                        except Exception as e:
                            logger.debug(f"Error with alternate {metric_name} selector '{selector}': {str(e)}")
                            
                return False
            except Exception as e:
                logger.warning(f"Error extracting {metric_name}: {str(e)}")
                return False
        
        # Extract revenue
        extract_metric("revenue", 'tr td:nth-child(2)', [
            '.revenue', 
            'td:contains("Revenue")', 
            'td:contains("Sales")',
            'td[class*="revenue"]',
            'td[class*="sales"]'
        ])
        
        # Extract net profit
        extract_metric("net_profit", 'tr td:nth-child(3)', [
            '.netProfit', 
            'td:contains("Net Profit")', 
            'td:contains("PAT")',
            'td[class*="profit"]',
            'td[class*="pat"]'
        ])
        
        # Extract revenue growth
        extract_metric("revenue_growth", 'tr td:nth-child(5)', [
            '.revenueGrowth', 
            'td:contains("Revenue Growth")', 
            'td:contains("Sales Growth")',
            'td[class*="revGrowth"]',
            'td[class*="salesGrowth"]'
        ])
        
        # Extract net profit growth
        extract_metric("net_profit_growth", 'tr td:nth-child(6)', [
            '.netProfitGrowth', 
            'td:contains("Net Profit Growth")', 
            'td:contains("PAT Growth")',
            'td[class*="profitGrowth"]',
            'td[class*="patGrowth"]'
        ])
        
        # Extract result date if available
        try:
            # Try multiple selectors for result date
            date_selectors = [
                'tr td.boardMeetDate',
                '.resultDate',
                'td:contains("Result Date")',
                'td[class*="date"]',
                '.resdate',
                '.resultdate',
                '.date-time',
                '.resinfo',
                '.result_date',
                '.board_meeting',
                '.meeting_date',
                '.announcement_date',
                '.date_info',
                '.result_announcement',
                '.result_info span',
                '.date_container'
            ]
            
            for selector in date_selectors:
                try:
                    element = None
                    if ':contains' in selector:
                        # Handle custom contains selector
                        tag_name = selector.split(':contains')[0]
                        search_text = selector.split('(')[1].split(')')[0].replace('"', '')
                        elements = card_soup.find_all(tag_name)
                        for el in elements:
                            if search_text in el.text:
                                # Get the next sibling or child that might contain the date
                                next_el = el.find_next()
                                if next_el:
                                    element = next_el
                                else:
                                    element = el
                                break
                    else:
                        element = card_soup.select_one(selector)
                        
                    if element and element.text.strip():
                        date_text = element.text.strip()
                        if date_text and re.search(r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{1,2}\s+[A-Za-z]+\s+\d{2,4}', date_text):
                            financial_data["result_date"] = date_text
                            logger.info(f"Found result date with selector '{selector}': {financial_data['result_date']}")
                            break
                except Exception as e:
                    logger.debug(f"Error with result date selector '{selector}': {str(e)}")
                    
            # If still not found, try to find any element with date-like content
            if not financial_data["result_date"]:
                # Look for date patterns in the text
                date_patterns = [
                    r'Result\s*Date\s*:\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{1,2}\s+[A-Za-z]+\s+\d{2,4})',
                    r'Board\s*Meeting\s*Date\s*:\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{1,2}\s+[A-Za-z]+\s+\d{2,4})',
                    r'Announced\s*on\s*:\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{1,2}\s+[A-Za-z]+\s+\d{2,4})',
                    r'Published\s*on\s*:\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{1,2}\s+[A-Za-z]+\s+\d{2,4})',
                    r'Date\s*:\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{1,2}\s+[A-Za-z]+\s+\d{2,4})'
                ]
                
                all_text = card_soup.get_text()
                for pattern in date_patterns:
                    match = re.search(pattern, all_text)
                    if match:
                        financial_data["result_date"] = match.group(1)
                        logger.info(f"Found result date with regex pattern: {financial_data['result_date']}")
                        break
                        
            # If still not found, try to extract from any text that looks like a date
            if not financial_data["result_date"]:
                all_text = card_soup.get_text()
                date_patterns = [
                    r'\d{1,2}[-/]\d{1,2}[-/]\d{4}',  # DD-MM-YYYY or DD/MM/YYYY
                    r'\d{1,2}[-/]\d{1,2}[-/]\d{2}',   # DD-MM-YY or DD/MM/YY
                    r'\d{1,2}\s+[A-Za-z]+\s+\d{4}',   # DD Month YYYY
                    r'\d{1,2}\s+[A-Za-z]+\s+\d{2}'    # DD Month YY
                ]
                
                for pattern in date_patterns:
                    match = re.search(pattern, all_text)
                    if match:
                        financial_data["result_date"] = match.group(0)
                        logger.info(f"Found result date with general date pattern: {financial_data['result_date']}")
                        break
        except Exception as e:
            logger.warning(f"Error extracting result date: {str(e)}")
        
        # Set report type to quarterly by default
        financial_data["report_type"] = "Quarterly"
        
        logger.info("Financial data extraction completed successfully")
        
        # Return the extracted data
        return financial_data
        
    except Exception as e:
        logger.error(f"Error in extract_financial_data: {str(e)}")
        # Return empty dictionary with structure intact
        return {
            "quarter": None,
            "cmp": None,
            "revenue": None,
            "gross_profit": None,
            "net_profit": None,
            "net_profit_growth": None,
            "gross_profit_growth": None,
            "revenue_growth": None,
            "result_date": None,
            "report_type": None
        }

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
                    
                    # Check if relevant keywords exist on the page (similar to test script approach)
                    html_content = str(detailed_soup)
                    keywords = ['strengths', 'weaknesses', 'technicals', 'piotroski', 'cagr']
                    keywords_found = False
                    
                    for keyword in keywords:
                        if keyword in html_content.lower():
                            logger.info(f"Found keyword '{keyword}' on the page")
                            keywords_found = True
                    
                    if not keywords_found:
                        logger.warning("No relevant keywords found on the page")
            except Exception as e:
                logger.warning(f"Error examining KnowBeforeYouInvest section: {str(e)}")
            
            # Strengths - try multiple selectors
            strengths_selectors = [
                '#swot_ls > a > strong',
                '.swotdiv .strengths strong',
                '.swotleft strong',
                '.swot_str strong',
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
                # Try with select instead of select_one
                for selector in strengths_selectors:
                    strengths_elements = detailed_soup.select(selector)
                    if strengths_elements:
                        metrics["strengths"] = strengths_elements[0].text.strip()
                        logger.info(f"Found strengths with selector array '{selector}': {metrics['strengths']}")
                        break
                if not metrics["strengths"]:
                    logger.warning(f"No strengths element found with any of these selectors: {strengths_selectors}")
            
            # Weaknesses - try multiple selectors
            weaknesses_selectors = [
                '#swot_lw > a > strong',
                '.swotdiv .weaknesses strong',
                '.swotright strong',
                '.swot_weak strong',
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
                # Try with select instead of select_one
                for selector in weaknesses_selectors:
                    weaknesses_elements = detailed_soup.select(selector)
                    if weaknesses_elements:
                        metrics["weaknesses"] = weaknesses_elements[0].text.strip()
                        logger.info(f"Found weaknesses with selector array '{selector}': {metrics['weaknesses']}")
                        break
                if not metrics["weaknesses"]:
                    logger.warning(f"No weaknesses element found with any of these selectors: {weaknesses_selectors}")
            
            # Technicals trend - try multiple selectors
            technicals_selectors = [
                '#techAnalysis a[style*="flex"]',
                '.techDiv p strong',
                '.techAnls strong',
                '.technicals strong',
                '#dMoving_Averages strong',  # Added from test script
                'table td:contains("Moving Averages") + td strong'  # Added from test script
            ]
            
            for selector in technicals_selectors:
                try:
                    technicals_element = detailed_soup.select_one(selector)
                    if technicals_element:
                        metrics["technicals_trend"] = technicals_element.text.strip()
                        logger.info(f"Found technicals_trend with selector '{selector}': {metrics['technicals_trend']}")
                        break
                except Exception as e:
                    logger.debug(f"Error with selector '{selector}': {str(e)}")
            
            if not metrics["technicals_trend"]:
                # Try with select instead of select_one
                for selector in technicals_selectors:
                    try:
                        technicals_elements = detailed_soup.select(selector)
                        if technicals_elements:
                            metrics["technicals_trend"] = technicals_elements[0].text.strip()
                            logger.info(f"Found technicals_trend with selector array '{selector}': {metrics['technicals_trend']}")
                            break
                    except Exception as e:
                        logger.debug(f"Error with selector array '{selector}': {str(e)}")
            
            # Piotroski score - try multiple selectors
            piotroski_selectors = [
                'div:nth-child(2) div.fpioi div.nof',
                '.piotroski_score',
                '.pio_score span',
                '#piotroskiScore',
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
                # Try with select instead of select_one
                for selector in piotroski_selectors:
                    piotroski_elements = detailed_soup.select(selector)
                    if piotroski_elements:
                        metrics["piotroski_score"] = piotroski_elements[0].text.strip()
                        logger.info(f"Found Piotroski score with selector array '{selector}': {metrics['piotroski_score']}")
                        break
                if not metrics["piotroski_score"]:
                    logger.warning(f"No Piotroski score element found with any of these selectors: {piotroski_selectors}")
            
            # Try to find CAGR data in tables (similar to test script approach)
            try:
                # Find all tables on the page
                tables = detailed_soup.find_all('table')
                logger.info(f"Found {len(tables)} tables on the page")
                
                # Check each table for CAGR data
                for i, table in enumerate(tables[:30]):  # Limit to first 30 tables for performance
                    table_html = str(table)
                    if 'cagr' in table_html.lower() or 'growth' in table_html.lower():
                        logger.info(f"Table {i+1} might contain CAGR data")
                        
                        # Save table HTML for debugging
                        try:
                            with open(f"logs/table_{i+1}.html", "w", encoding="utf-8") as f:
                                f.write(table_html)
                            logger.info(f"Saved table HTML to logs/table_{i+1}.html")
                        except Exception as e:
                            logger.debug(f"Error saving table HTML: {str(e)}")
                        
                        # Look for specific CAGR values
                        if 'profit grwth 3yr cagr' in table_html.lower() or 'profit growth 3yr cagr' in table_html.lower():
                            # Extract the value using various methods
                            try:
                                # Method 1: Look for specific cell pattern
                                cagr_cell = table.select_one('td:contains("Profit Grwth 3Yr CAGR") + td span')
                                if cagr_cell:
                                    metrics["net_profit_growth_3yr_cagr"] = float(cagr_cell.text.strip())
                                    logger.info(f"Found net_profit_growth_3yr_cagr: {metrics['net_profit_growth_3yr_cagr']}")
                            except Exception as e:
                                logger.debug(f"Error extracting net_profit_growth_3yr_cagr: {str(e)}")
                        
                        if 'sales grwth 3yr cagr' in table_html.lower() or 'sales growth 3yr cagr' in table_html.lower():
                            try:
                                # Method 1: Look for specific cell pattern
                                cagr_cell = table.select_one('td:contains("Sales Grwth 3Yr CAGR") + td span')
                                if cagr_cell:
                                    metrics["revenue_growth_3yr_cagr"] = float(cagr_cell.text.strip())
                                    logger.info(f"Found revenue_growth_3yr_cagr: {metrics['revenue_growth_3yr_cagr']}")
                            except Exception as e:
                                logger.debug(f"Error extracting revenue_growth_3yr_cagr: {str(e)}")
            except Exception as e:
                logger.warning(f"Error searching for CAGR data in tables: {str(e)}")
            
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