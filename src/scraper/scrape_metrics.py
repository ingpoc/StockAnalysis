"""
Module for scraping financial metrics from MoneyControl.
"""
import logging
import datetime
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

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
    try:
        driver.execute_script(f"window.open('{stock_link}', '_blank');")
        driver.switch_to.window(driver.window_handles[-1])
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'body')))
        
        detailed_soup = BeautifulSoup(driver.page_source, 'html.parser')
        
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

        # Extract company symbol
        symbol = detailed_soup.select_one('#company_info > ul > li:nth-child(5) > ul > li:nth-child(2) > p').text.strip() if detailed_soup.select_one('#company_info > ul > li:nth-child(5) > ul > li:nth-child(2) > p') else None

        driver.close()
        driver.switch_to.window(driver.window_handles[0])

        return metrics, symbol
    except Exception as e:
        logger.error(f"Error scraping financial metrics: {str(e)}")
        
        # Make sure to close the new tab and switch back
        try:
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
        except:
            pass
            
        return None, None

def process_result_card(card, driver, db_collection=None):
    """
    Processes a company result card and saves the data to the database.
    
    Args:
        card (bs4.element.Tag): BeautifulSoup Tag object representing a company result card.
        driver (webdriver.Chrome): Chrome WebDriver instance.
        db_collection (Collection, optional): MongoDB collection to store the data.
        
    Returns:
        dict: Dictionary with the processed company data.
    """
    try:
        company_name = card.select_one('h3 a').text.strip() if card.select_one('h3 a') else None
        if not company_name:
            logger.warning("Skipping card due to missing company name.")
            return None

        stock_link = card.select_one('h3 a')['href']
        if not stock_link:
            logger.warning(f"Skipping {company_name} due to missing stock link.")
            return None

        logger.info(f"Processing stock: {company_name}")

        # Extract basic financial data from the card
        financial_data = extract_financial_data(card)
        
        # Check if this company already exists in the database with this quarter's data
        if db_collection:
            existing_company = db_collection.find_one({"company_name": company_name})
            if existing_company:
                existing_quarters = [metric['quarter'] for metric in existing_company.get('financial_metrics', [])]
                if financial_data['quarter'] in existing_quarters:
                    logger.info(f"{company_name} already has data for {financial_data['quarter']}. Skipping.")
                    return None

        # Fetch additional metrics from the stock's page
        additional_metrics, symbol = scrape_financial_metrics(driver, stock_link)
        
        if additional_metrics:
            financial_data.update(additional_metrics)

        # Prepare the complete company data
        stock_data = {
            "company_name": company_name,
            "symbol": symbol,
            "financial_metrics": financial_data,
            "timestamp": datetime.datetime.utcnow()
        }

        # Save to database if a collection was provided
        if db_collection and financial_data['quarter'] is not None:
            if existing_company:
                logger.info(f"Adding new data for {company_name} - {financial_data['quarter']}")
                db_collection.update_one(
                    {"company_name": company_name},
                    {"$push": {"financial_metrics": financial_data}}
                )
            else:
                logger.info(f"Creating new entry for {company_name}")
                stock_data = {
                    "company_name": company_name,
                    "symbol": symbol,
                    "financial_metrics": [financial_data],
                    "timestamp": datetime.datetime.utcnow()
                }
                db_collection.insert_one(stock_data)

        logger.info(f"Data for {company_name} processed successfully.")
        return stock_data

    except Exception as e:
        logger.error(f"Error processing result card: {str(e)}")
        return None 