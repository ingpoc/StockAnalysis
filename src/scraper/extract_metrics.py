"""
Module for extracting financial metrics from web pages.
Uses targeted selectors to extract specific financial data.
"""
import re
import logging
from typing import Dict, Any, Optional, List
from bs4 import BeautifulSoup
from datetime import datetime

# Import the centralized logger
from src.utils.logger import logger

def extract_financial_data(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    Extract financial data from a BeautifulSoup object.
    
    Args:
        soup (BeautifulSoup): BeautifulSoup object of the page.
        
    Returns:
        Dict[str, Any]: Dictionary of financial data.
    """
    logger.info("Extracting financial data")
    
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
        "report_type": None,
        # Advanced metrics
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
        "fundamental_insights": None
    }
    
    try:
        # Log the HTML for debugging
        logger.debug(f"HTML to extract from: {soup}")
        
        # Extract quarter information
        # Based on the search results, it might be in a format like "Q3 FY24-25"
        quarter_selectors = [
            '.EarningUpdateCard_btmDtTmStrip__V03pl',  # New class for quarter info
            'table th:contains("Q3")',
            'table th:contains("Q")',
            'div:contains("Q3 FY")',
            'div:contains("Q")',
            'span:contains("Q3")',
            'span:contains("Q")'
        ]
        
        for selector in quarter_selectors:
            try:
                quarter_element = soup.select_one(selector)
                if quarter_element:
                    quarter_text = quarter_element.text.strip()
                    # Extract quarter using regex
                    quarter_match = re.search(r'Q[1-4]\s*FY\d{2}-\d{2}', quarter_text)
                    if quarter_match:
                        financial_data["quarter"] = quarter_match.group(0)
                        break
            except Exception as e:
                logger.warning(f"Error extracting quarter with selector {selector}: {str(e)}")
        
        # Extract CMP (Current Market Price)
        # Based on the search results, it might be in a format like "14.98 (1.56%)"
        cmp_selectors = [
            '.EarningUpdateCard_stkData__rEKCf',  # New class for stock data
            'div:contains("%")',
            'span:contains("%")',
            'h3 + div'  # Div after h3
        ]
        
        for selector in cmp_selectors:
            try:
                cmp_element = soup.select_one(selector)
                if cmp_element:
                    cmp_text = cmp_element.text.strip()
                    # Extract CMP using regex
                    cmp_match = re.search(r'\d+\.\d+\s*\(\-?\d+\.\d+%\)', cmp_text)
                    if cmp_match:
                        financial_data["cmp"] = cmp_match.group(0)
                        break
            except Exception as e:
                logger.warning(f"Error extracting CMP with selector {selector}: {str(e)}")
        
        # Extract revenue, gross profit, and net profit
        # Look for green/red text elements which might contain growth percentages
        growth_selectors = [
            '.EarningUpdateCard_greentxt__6okOx',  # New class for green text (positive growth)
            '.EarningUpdateCard_redtxt__C7thr',    # New class for red text (negative growth)
            '.green',
            '.red',
            'span.up',
            'span.down'
        ]
        
        growth_elements = []
        for selector in growth_selectors:
            try:
                elements = soup.select(selector)
                growth_elements.extend(elements)
            except Exception as e:
                logger.warning(f"Error finding growth elements with selector {selector}: {str(e)}")
        
        # Process growth elements
        if growth_elements:
            logger.info(f"Found {len(growth_elements)} growth elements")
            
            # Try to identify which growth element corresponds to which metric
            for i, element in enumerate(growth_elements):
                text = element.text.strip()
                
                # Check if it's a percentage
                if '%' in text:
                    # Determine which metric this growth percentage belongs to
                    if i == 0 or 'revenue' in text.lower() or 'sales' in text.lower():
                        financial_data["revenue_growth"] = text
                    elif i == 1 or 'gross' in text.lower() or 'operating' in text.lower():
                        financial_data["gross_profit_growth"] = text
                    elif i == 2 or 'net' in text.lower() or 'profit' in text.lower():
                        financial_data["net_profit_growth"] = text
        
        # Extract actual values for revenue, gross profit, and net profit
        # These might be near the growth percentages or in separate elements
        value_selectors = [
            'div:contains("Rs.")',
            'div:contains("₹")',
            'span:contains("Rs.")',
            'span:contains("₹")'
        ]
        
        value_elements = []
        for selector in value_selectors:
            try:
                elements = soup.select(selector)
                value_elements.extend(elements)
            except Exception as e:
                logger.warning(f"Error finding value elements with selector {selector}: {str(e)}")
        
        # Process value elements
        if value_elements:
            logger.info(f"Found {len(value_elements)} value elements")
            
            # Try to identify which value element corresponds to which metric
            for i, element in enumerate(value_elements):
                text = element.text.strip()
                
                # Check if it contains a currency symbol or "cr" (crore)
                if 'Rs.' in text or '₹' in text or 'cr' in text.lower():
                    # Extract the numeric value
                    value_match = re.search(r'\d+(\.\d+)?', text)
                    if value_match:
                        value = value_match.group(0)
                        
                        # Determine which metric this value belongs to
                        if i == 0 or 'revenue' in text.lower() or 'sales' in text.lower():
                            financial_data["revenue"] = value
                        elif i == 1 or 'gross' in text.lower() or 'operating' in text.lower():
                            financial_data["gross_profit"] = value
                        elif i == 2 or 'net' in text.lower() or 'profit' in text.lower():
                            financial_data["net_profit"] = value
        
        # Extract result date
        date_selectors = [
            '.EarningUpdateCard_btmDtTmStrip__V03pl',  # New class for date info
            'div:contains("Result Date")',
            'span:contains("Result Date")',
            'div:contains("Date")',
            'span:contains("Date")'
        ]
        
        for selector in date_selectors:
            try:
                date_element = soup.select_one(selector)
                if date_element:
                    date_text = date_element.text.strip()
                    # Extract date using regex
                    date_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}', date_text)
                    if date_match:
                        financial_data["result_date"] = date_match.group(0)
                        break
            except Exception as e:
                logger.warning(f"Error extracting result date with selector {selector}: {str(e)}")
        
        # Extract report type (Standalone/Consolidated)
        report_selectors = [
            'div:contains("Standalone")',
            'div:contains("Consolidated")',
            'span:contains("Standalone")',
            'span:contains("Consolidated")'
        ]
        
        for selector in report_selectors:
            try:
                report_element = soup.select_one(selector)
                if report_element:
                    report_text = report_element.text.strip()
                    if 'standalone' in report_text.lower():
                        financial_data["report_type"] = "Standalone"
                        break
                    elif 'consolidated' in report_text.lower():
                        financial_data["report_type"] = "Consolidated"
                        break
            except Exception as e:
                logger.warning(f"Error extracting report type with selector {selector}: {str(e)}")
        
        # If we couldn't extract the data using the above methods, try a more general approach
        if not any([financial_data["revenue"], financial_data["gross_profit"], financial_data["net_profit"]]):
            logger.warning("Could not extract financial data using specific selectors, trying general approach")
            
            # Get all text from the card
            all_text = soup.get_text()
            
            # Look for patterns like "Revenue: 123 cr" or "Net Profit: 45 cr"
            revenue_match = re.search(r'Revenue:?\s*(\d+(\.\d+)?)', all_text)
            if revenue_match:
                financial_data["revenue"] = revenue_match.group(1)
            
            gross_profit_match = re.search(r'Gross Profit:?\s*(\d+(\.\d+)?)', all_text)
            if gross_profit_match:
                financial_data["gross_profit"] = gross_profit_match.group(1)
            
            net_profit_match = re.search(r'Net Profit:?\s*(\d+(\.\d+)?)', all_text)
            if net_profit_match:
                financial_data["net_profit"] = net_profit_match.group(1)
            
            # Look for growth percentages
            revenue_growth_match = re.search(r'Revenue Growth:?\s*(\-?\d+(\.\d+)?%)', all_text)
            if revenue_growth_match:
                financial_data["revenue_growth"] = revenue_growth_match.group(1)
            
            gross_profit_growth_match = re.search(r'Gross Profit Growth:?\s*(\-?\d+(\.\d+)?%)', all_text)
            if gross_profit_growth_match:
                financial_data["gross_profit_growth"] = gross_profit_growth_match.group(1)
            
            net_profit_growth_match = re.search(r'Net Profit Growth:?\s*(\-?\d+(\.\d+)?%)', all_text)
            if net_profit_growth_match:
                financial_data["net_profit_growth"] = net_profit_growth_match.group(1)
        
        return financial_data
    except Exception as e:
        logger.error(f"Error extracting financial data: {str(e)}")
        return financial_data

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