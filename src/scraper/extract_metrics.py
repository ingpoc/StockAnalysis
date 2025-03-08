"""
Module for extracting financial metrics from web pages.
Uses targeted selectors to extract specific financial data.
"""
import re
import logging
from typing import Dict, Any, Optional, List
from bs4 import BeautifulSoup
from datetime import datetime
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchWindowException, InvalidSessionIdException

# Import the centralized logger
from src.utils.logger import logger

def extract_financial_data(card):
    """
    Extract financial data from a result card.
    
    Args:
        card: BeautifulSoup element representing a result card.
        
    Returns:
        Dict[str, Any]: Dictionary of extracted financial data.
    """
    try:
        return {
            "cmp": card.select_one('p.rapidResCardWeb_priceTxt___5MvY').text.strip() if card.select_one('p.rapidResCardWeb_priceTxt___5MvY') else None,
            "revenue": card.select_one('tr:nth-child(1) td:nth-child(2)').text.strip() if card.select_one('tr:nth-child(1) td:nth-child(2)') else None,
            "gross_profit": card.select_one('tr:nth-child(2) td:nth-child(2)').text.strip() if card.select_one('tr:nth-child(2) td:nth-child(2)') else None,
            "net_profit": card.select_one('tr:nth-child(3) td:nth-child(2)').text.strip() if card.select_one('tr:nth-child(3) td:nth-child(2)') else None,
            "net_profit_growth": card.select_one('tr:nth-child(3) td:nth-child(4)').text.strip() if card.select_one('tr:nth-child(3) td:nth-child(4)') else None,
            "gross_profit_growth": card.select_one('tr:nth-child(2) td:nth-child(4)').text.strip() if card.select_one('tr:nth-child(2) td:nth-child(4)') else None,
            "revenue_growth": card.select_one('tr:nth-child(1) td:nth-child(4)').text.strip() if card.select_one('tr:nth-child(1) td:nth-child(4)') else None,
            "quarter": card.select_one('tr th:nth-child(1)').text.strip() if card.select_one('tr th:nth-child(1)') else None,
            "result_date": card.select_one('p.rapidResCardWeb_gryTxtOne__mEhU_').text.strip() if card.select_one('p.rapidResCardWeb_gryTxtOne__mEhU_') else None,
            "report_type": card.select_one('p.rapidResCardWeb_bottomText__p8YzI').text.strip() if card.select_one('p.rapidResCardWeb_bottomText__p8YzI') else None,
        }
    except Exception as e:
        logger.error(f"Error extracting financial data from card: {str(e)}")
        return {}

def scrape_financial_metrics(driver, stock_link):
    """
    Scrape additional financial metrics from a company's stock page.
    
    Args:
        driver: WebDriver instance.
        stock_link: URL of the company's stock page.
        
    Returns:
        Dict[str, Any]: Dictionary of additional financial metrics.
        str: Company symbol.
    """
    original_window = None
    try:
        # Remember the original window handle
        original_window = driver.current_window_handle
        
        # Open a new tab for the stock page
        driver.execute_script(f"window.open('{stock_link}', '_blank');")
        driver.switch_to.window(driver.window_handles[-1])
        
        # Wait for the page to load
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'body')))
        
        # Parse the page source
        detailed_soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Extract additional metrics
        metrics = {
            "market_cap": detailed_soup.select_one('tr:nth-child(7) td.nsemktcap.bsemktcap').text.strip() if detailed_soup.select_one('tr:nth-child(7) td.nsemktcap.bsemktcap') else None,
            "face_value": detailed_soup.select_one('tr:nth-child(7) td.nsefv.bsefv').text.strip() if detailed_soup.select_one('tr:nth-child(7) td.nsefv.bsefv') else None,
            "book_value": detailed_soup.select_one('tr:nth-child(5) td.nsebv.bsebv').text.strip() if detailed_soup.select_one('tr:nth-child(5) td.nsebv.bsebv') else None,
            "dividend_yield": detailed_soup.select_one('tr:nth-child(6) td.nsedy.bsedy').text.strip() if detailed_soup.select_one('tr:nth-child(6) td.nsedy.bsedy') else None,
            "ttm_eps": detailed_soup.select_one('tr:nth-child(1) td:nth-child(2) span.nseceps.bseceps').text.strip() if detailed_soup.select_one('tr:nth-child(1) td:nth-child(2) span.nseceps.bseceps') else None,
            "ttm_pe": detailed_soup.select_one('tr:nth-child(2) td:nth-child(2) span.nsepe.bsepe').text.strip() if detailed_soup.select_one('tr:nth-child(2) td:nth-child(2) span.nsepe.bsepe') else None,
            "pb_ratio": detailed_soup.select_one('tr:nth-child(3) td:nth-child(2) span.nsepb.bsepb').text.strip() if detailed_soup.select_one('tr:nth-child(3) td:nth-child(2) span.nsepb.bsepb') else None,
            "sector_pe": detailed_soup.select_one('tr:nth-child(4) td.nsesc_ttm.bsesc_ttm').text.strip() if detailed_soup.select_one('tr:nth-child(4) td.nsesc_ttm.bsesc_ttm') else None,
            "piotroski_score": detailed_soup.select_one('div:nth-child(2) div.fpioi div.nof').text.strip() if detailed_soup.select_one('div:nth-child(2) div.fpioi div.nof') else None,
            "revenue_growth_3yr_cagr": detailed_soup.select_one('tr:-soup-contains("Revenue") td:nth-child(2)').text.strip() if detailed_soup.select_one('tr:-soup-contains("Revenue") td:nth-child(2)') else None,
            "net_profit_growth_3yr_cagr": detailed_soup.select_one('tr:-soup-contains("NetProfit") td:nth-child(2)').text.strip() if detailed_soup.select_one('tr:-soup-contains("NetProfit") td:nth-child(2)') else None,
            "operating_profit_growth_3yr_cagr": detailed_soup.select_one('tr:-soup-contains("OperatingProfit") td:nth-child(2)').text.strip() if detailed_soup.select_one('tr:-soup-contains("OperatingProfit") td:nth-child(2)') else None,
            "strengths": detailed_soup.select_one('#swot_ls > a > strong').text.strip() if detailed_soup.select_one('#swot_ls > a > strong') else None,
            "weaknesses": detailed_soup.select_one('#swot_lw > a > strong').text.strip() if detailed_soup.select_one('#swot_lw > a > strong') else None,
            "technicals_trend": detailed_soup.select_one('#techAnalysis a[style*="flex"]').text.strip() if detailed_soup.select_one('#techAnalysis a[style*="flex"]') else None,
            "fundamental_insights": detailed_soup.select_one('#mc_essenclick > div.bx_mceti.mc_insght > div > div').text.strip() if detailed_soup.select_one('#mc_essenclick > div.bx_mceti.mc_insght > div > div') else None,
            "fundamental_insights_description": detailed_soup.select_one('#insight_class').text.strip() if detailed_soup.select_one('#insight_class') else None
        }
        
        # Extract the company symbol
        symbol = detailed_soup.select_one('#company_info > ul > li:nth-child(5) > ul > li:nth-child(2) > p').text.strip() if detailed_soup.select_one('#company_info > ul > li:nth-child(5) > ul > li:nth-child(2) > p') else None
        
        # Check if we collected meaningful data
        if not any(metrics.values()) or not symbol:
            logger.warning("Failed to collect meaningful metrics data from the stock page")
        
        # Close the tab and switch back to the main window
        try:
            driver.close()
            driver.switch_to.window(original_window)
        except Exception as tab_close_error:
            logger.error(f"Error closing tab: {str(tab_close_error)}")
            # If we can't close the tab and switch back, we need to force a failure
            raise
        
        return metrics, symbol
    except (NoSuchWindowException, InvalidSessionIdException) as e:
        # Log a cleaner message without stack trace
        logger.error("Browser window was closed during metrics scraping")
        # Return None for both values to signal incomplete data
        return None, None
    except Exception as e:
        logger.error(f"Error scraping financial metrics: {str(e)}")
        
        # Make sure to switch back to the main window if possible
        try:
            if original_window and original_window in driver.window_handles:
                driver.switch_to.window(original_window)
        except Exception as switch_error:
            logger.error(f"Error switching back to main window: {str(switch_error)}")
        
        # Return None for both values to signal incomplete data
        return None, None

def extract_company_info(soup: BeautifulSoup) -> Dict[str, str]:
    """
    Extract company name and symbol from a BeautifulSoup object.
    
    Args:
        soup (BeautifulSoup): BeautifulSoup object of the page.
        
    Returns:
        Dict[str, str]: Dictionary with company name and symbol.
    """
    company_info = {
        "company_name": None,
        "symbol": None
    }
    
    # Extract company name
    company_name_element = soup.select_one("h1.pcstname")
    if company_name_element and company_name_element.text.strip():
        company_info["company_name"] = company_name_element.text.strip()
    
    # Extract symbol
    symbol_element = soup.select_one(".nsecp_sym")
    if symbol_element and symbol_element.text.strip():
        symbol = symbol_element.text.strip()
        # Remove parentheses if present
        symbol = symbol.replace("(", "").replace(")", "")
        company_info["symbol"] = symbol
    
    return company_info

def extract_quarter(soup: BeautifulSoup) -> Optional[str]:
    """Extract quarter information."""
    quarter_element = soup.select_one('tr th:nth-child(1)')
    if quarter_element and quarter_element.text.strip():
        return clean_text(quarter_element.text.strip())
    return None

def extract_cmp(soup: BeautifulSoup) -> Optional[str]:
    """Extract current market price."""
    cmp_element = soup.select_one('.nsecp')
    if cmp_element and cmp_element.text.strip():
        return clean_text(cmp_element.text.strip())
    return None

def extract_revenue(soup: BeautifulSoup) -> Optional[str]:
    """Extract revenue."""
    revenue_element = soup.select_one('td:contains("Revenue") + td')
    if revenue_element and revenue_element.text.strip():
        return clean_text(revenue_element.text.strip())
    return None

def extract_gross_profit(soup: BeautifulSoup) -> Optional[str]:
    """Extract gross profit."""
    gross_profit_element = soup.select_one('td:contains("Operating Profit") + td')
    if gross_profit_element and gross_profit_element.text.strip():
        return clean_text(gross_profit_element.text.strip())
    return None

def extract_net_profit(soup: BeautifulSoup) -> Optional[str]:
    """Extract net profit."""
    net_profit_element = soup.select_one('td:contains("Net Profit") + td')
    if net_profit_element and net_profit_element.text.strip():
        return clean_text(net_profit_element.text.strip())
    return None

def extract_revenue_growth(soup: BeautifulSoup) -> Optional[str]:
    """Extract revenue growth."""
    revenue_growth_element = soup.select_one('td:contains("Revenue") + td + td')
    if revenue_growth_element and revenue_growth_element.text.strip():
        return clean_text(revenue_growth_element.text.strip())
    return None

def extract_gross_profit_growth(soup: BeautifulSoup) -> Optional[str]:
    """Extract gross profit growth."""
    gross_profit_growth_element = soup.select_one('td:contains("Operating Profit") + td + td')
    if gross_profit_growth_element and gross_profit_growth_element.text.strip():
        return clean_text(gross_profit_growth_element.text.strip())
    return None

def extract_net_profit_growth(soup: BeautifulSoup) -> Optional[str]:
    """Extract net profit growth."""
    net_profit_growth_element = soup.select_one('td:contains("Net Profit") + td + td')
    if net_profit_growth_element and net_profit_growth_element.text.strip():
        return clean_text(net_profit_growth_element.text.strip())
    return None

def extract_result_date(soup: BeautifulSoup) -> Optional[str]:
    """Extract result date."""
    result_date_element = soup.select_one('td:contains("Result Date") + td')
    if result_date_element and result_date_element.text.strip():
        return clean_text(result_date_element.text.strip())
    return None

def extract_report_type(soup: BeautifulSoup) -> Optional[str]:
    """Extract report type."""
    report_type_element = soup.select_one('td:contains("Report Type") + td')
    if report_type_element and report_type_element.text.strip():
        return clean_text(report_type_element.text.strip())
    return None

def extract_market_cap(soup: BeautifulSoup) -> Optional[str]:
    """Extract market capitalization."""
    market_cap_element = soup.select_one('td:contains("Market Cap") + td')
    if market_cap_element and market_cap_element.text.strip():
        return clean_text(market_cap_element.text.strip())
    return None

def extract_face_value(soup: BeautifulSoup) -> Optional[str]:
    """Extract face value."""
    face_value_element = soup.select_one('td:contains("Face Value") + td')
    if face_value_element and face_value_element.text.strip():
        return clean_text(face_value_element.text.strip())
    return None

def extract_book_value(soup: BeautifulSoup) -> Optional[str]:
    """Extract book value."""
    book_value_element = soup.select_one('td:contains("Book Value") + td')
    if book_value_element and book_value_element.text.strip():
        return clean_text(book_value_element.text.strip())
    return None

def extract_dividend_yield(soup: BeautifulSoup) -> Optional[str]:
    """Extract dividend yield."""
    dividend_yield_element = soup.select_one('td:contains("Dividend Yield") + td')
    if dividend_yield_element and dividend_yield_element.text.strip():
        return clean_text(dividend_yield_element.text.strip())
    return None

def extract_ttm_eps(soup: BeautifulSoup) -> Optional[str]:
    """Extract TTM EPS."""
    ttm_eps_element = soup.select_one('td:contains("TTM EPS") + td')
    if ttm_eps_element and ttm_eps_element.text.strip():
        return clean_text(ttm_eps_element.text.strip())
    return None

def extract_ttm_pe(soup: BeautifulSoup) -> Optional[str]:
    """Extract TTM P/E."""
    ttm_pe_element = soup.select_one('td:contains("TTM P/E") + td')
    if ttm_pe_element and ttm_pe_element.text.strip():
        return clean_text(ttm_pe_element.text.strip())
    return None

def extract_pb_ratio(soup: BeautifulSoup) -> Optional[str]:
    """Extract P/B ratio."""
    pb_ratio_element = soup.select_one('td:contains("P/B Ratio") + td')
    if pb_ratio_element and pb_ratio_element.text.strip():
        return clean_text(pb_ratio_element.text.strip())
    return None

def extract_sector_pe(soup: BeautifulSoup) -> Optional[str]:
    """Extract sector P/E."""
    sector_pe_element = soup.select_one('td:contains("Sector P/E") + td')
    if sector_pe_element and sector_pe_element.text.strip():
        return clean_text(sector_pe_element.text.strip())
    return None

def extract_revenue_growth_3yr_cagr(soup: BeautifulSoup) -> Optional[str]:
    """Extract 3-year revenue growth CAGR."""
    revenue_growth_3yr_cagr_element = soup.select_one('td:contains("Revenue Growth (3Y CAGR)") + td')
    if revenue_growth_3yr_cagr_element and revenue_growth_3yr_cagr_element.text.strip():
        return clean_text(revenue_growth_3yr_cagr_element.text.strip())
    return None

def extract_net_profit_growth_3yr_cagr(soup: BeautifulSoup) -> Optional[str]:
    """Extract 3-year net profit growth CAGR."""
    net_profit_growth_3yr_cagr_element = soup.select_one('td:contains("Net Profit Growth (3Y CAGR)") + td')
    if net_profit_growth_3yr_cagr_element and net_profit_growth_3yr_cagr_element.text.strip():
        return clean_text(net_profit_growth_3yr_cagr_element.text.strip())
    return None

def extract_operating_profit_growth_3yr_cagr(soup: BeautifulSoup) -> Optional[str]:
    """Extract 3-year operating profit growth CAGR."""
    operating_profit_growth_3yr_cagr_element = soup.select_one('td:contains("Operating Profit Growth (3Y CAGR)") + td')
    if operating_profit_growth_3yr_cagr_element and operating_profit_growth_3yr_cagr_element.text.strip():
        return clean_text(operating_profit_growth_3yr_cagr_element.text.strip())
    return None

def extract_piotroski_score(soup: BeautifulSoup) -> Optional[str]:
    """Extract Piotroski score."""
    piotroski_score_element = soup.select_one('td:contains("Piotroski Score") + td')
    if piotroski_score_element and piotroski_score_element.text.strip():
        return clean_text(piotroski_score_element.text.strip())
    return None

def extract_strengths(soup: BeautifulSoup) -> Optional[str]:
    """Extract strengths."""
    strengths_element = soup.select_one('div:contains("Strengths") + div')
    if strengths_element and strengths_element.text.strip():
        return clean_text(strengths_element.text.strip())
    return None

def extract_weaknesses(soup: BeautifulSoup) -> Optional[str]:
    """Extract weaknesses."""
    weaknesses_element = soup.select_one('div:contains("Weaknesses") + div')
    if weaknesses_element and weaknesses_element.text.strip():
        return clean_text(weaknesses_element.text.strip())
    return None

def extract_technicals_trend(soup: BeautifulSoup) -> Optional[str]:
    """Extract technicals trend."""
    technicals_trend_element = soup.select_one('div:contains("Technical Trend") + div')
    if technicals_trend_element and technicals_trend_element.text.strip():
        return clean_text(technicals_trend_element.text.strip())
    return None

def extract_fundamental_insights(soup: BeautifulSoup) -> Optional[str]:
    """Extract fundamental insights."""
    fundamental_insights_element = soup.select_one('div:contains("Fundamental Insights") + div')
    if fundamental_insights_element and fundamental_insights_element.text.strip():
        return clean_text(fundamental_insights_element.text.strip())
    return None

def clean_text(text: str) -> str:
    """
    Clean text by removing extra whitespace and normalizing.
    
    Args:
        text (str): Text to clean.
        
    Returns:
        str: Cleaned text.
    """
    if not text:
        return ""
    
    # Replace non-breaking spaces and other whitespace characters
    text = text.replace("\xa0", " ").replace("\t", " ").replace("\n", " ")
    
    # Remove multiple spaces
    while "  " in text:
        text = text.replace("  ", " ")
    
    return text.strip()

def process_financial_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process and clean financial data.
    
    Args:
        data (Dict[str, Any]): Raw financial data.
        
    Returns:
        Dict[str, Any]: Processed financial data.
    """
    processed_data = {}
    
    for key, value in data.items():
        if value is None:
            processed_data[key] = None
            continue
            
        if "growth" in key or "yield" in key:
            # Clean percentage values
            processed_data[key] = clean_percentage(value)
        elif "profit" in key or "revenue" in key or "market_cap" in key or "eps" in key:
            # Clean monetary values
            processed_data[key] = clean_monetary_value(value)
        elif key == "quarter":
            # Clean quarter information
            processed_data[key] = clean_quarter(value)
        elif key == "result_date":
            # Clean date
            processed_data[key] = clean_date(value)
        else:
            # Default cleaning
            processed_data[key] = value
    
    return processed_data

def clean_monetary_value(value: str) -> str:
    """Clean monetary value."""
    if not value:
        return value
        
    # Remove currency symbols and commas
    value = re.sub(r'[₹$€£,]', '', value)
    
    # Handle crore and lakh
    value = value.lower()
    if 'cr' in value or 'crore' in value:
        value = re.sub(r'cr.*|crore.*', '', value)
        try:
            value_float = float(value.strip())
            value = f"{value_float} Cr"
        except ValueError:
            pass
    elif 'lakh' in value or 'lac' in value:
        value = re.sub(r'lakh.*|lac.*', '', value)
        try:
            value_float = float(value.strip())
            value = f"{value_float} Lakh"
        except ValueError:
            pass
    
    return value.strip()

def clean_percentage(value: str) -> str:
    """Clean percentage value."""
    if not value:
        return value
        
    # Remove everything except digits, decimal point, and minus sign
    value = re.sub(r'[^0-9\.\-]', '', value)
    
    # Add percentage sign if not present
    if value and not value.endswith('%'):
        value = f"{value}%"
    
    return value

def clean_quarter(quarter: str) -> str:
    """Clean quarter information."""
    if not quarter:
        return quarter
        
    # Standardize quarter format
    quarter = quarter.strip()
    
    # Convert "Quarter 1 2023" to "Q1 2023"
    quarter = re.sub(r'Quarter\s+(\d)\s+(\d{4})', r'Q\1 \2', quarter)
    
    # Convert "Quarter 1 FY23" to "Q1 FY23"
    quarter = re.sub(r'Quarter\s+(\d)\s+FY(\d{2})', r'Q\1 FY\2', quarter)
    
    return quarter

def clean_date(date_str: str) -> str:
    """Clean date string."""
    if not date_str:
        return date_str
        
    # Try to parse the date
    date_formats = [
        '%d-%m-%Y',
        '%d/%m/%Y',
        '%Y-%m-%d',
        '%Y/%m/%d',
        '%d-%b-%Y',
        '%d %b %Y',
        '%d %B %Y',
        '%b %d, %Y',
        '%B %d, %Y'
    ]
    
    date_str = date_str.strip()
    
    for date_format in date_formats:
        try:
            date_obj = datetime.strptime(date_str, date_format)
            return date_obj.strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    # If we couldn't parse the date, return it as is
    return date_str 