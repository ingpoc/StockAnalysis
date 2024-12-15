import re
from typing import Dict, Any, List, Optional
import pandas as pd
from datetime import datetime
from cachetools import TTLCache

# Cache for market data (5 minutes TTL)
market_data_cache = TTLCache(maxsize=10, ttl=300)

def process_estimates(estimate_str: str) -> dict:
    """Process estimate string into structured data"""
    try:
        if not estimate_str or estimate_str == 'N/A':
            return {'value': 0, 'type': 'neutral', 'display': 'N/A'}
            
        parts = estimate_str.split(':')
        if len(parts) != 2:
            return {'value': 0, 'type': 'neutral', 'display': estimate_str}
            
        value = float(parts[1].strip().replace('%', ''))
        type = 'beats' if 'Beats' in parts[0] else 'misses'
        
        return {
            'value': value,
            'type': type,
            'display': estimate_str
        }
    except Exception:
        return {'value': 0, 'type': 'neutral', 'display': 'N/A'}

def parse_numeric(value: str) -> float:
    """Parse numeric values from strings, handling percentages and commas"""
    try:
        if isinstance(value, (int, float)):
            return float(value)
            
        clean_value = value.replace(',', '').replace('%', '')
        if '(' in clean_value:
            clean_value = clean_value.split('(')[0].strip()
            
        return float(clean_value)
    except (ValueError, AttributeError):
        return 0.0

def extract_numeric(value: str) -> int:
    """Extract numeric value from strings like 'Strengths (8)'"""
    try:
        if isinstance(value, (int, float)):
            return int(value)
        match = re.search(r'\((\d+)\)', value)
        if match:
            return int(match.group(1))
        return int(''.join(filter(str.isdigit, str(value))))
    except (ValueError, AttributeError):
        return 0

def process_stock_data(stock_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process individual stock data"""
    if not stock_data.get('financial_metrics'):
        return None

    latest = stock_data['financial_metrics'][0]
    
    return {
        'company_name': stock_data['company_name'],
        'symbol': stock_data['symbol'],
        'net_profit_growth': parse_numeric(latest['net_profit_growth']),
        'cmp': parse_numeric(latest['cmp']),
        'strengths': extract_numeric(latest['strengths']),
        'weaknesses': extract_numeric(latest['weaknesses']),
        'piotroski_score': extract_numeric(latest['piotroski_score']),
        'estimates': process_estimates(latest['estimates']),
        'result_date': latest['result_date'],
        'quarter': latest['quarter'],
        'recommendation': latest.get('recommendation', 'N/A')
    }

def prepare_market_overview(stocks: List[Dict[str, Any]], quarter: Optional[str] = None) -> Dict[str, Any]:
    """Prepare market overview data with caching"""
    cache_key = f"overview_{quarter or 'latest'}"
    
    if cache_key in market_data_cache:
        return market_data_cache[cache_key]
        
    processed_stocks = []
    for stock in stocks:
        processed = process_stock_data(stock)
        if processed:
            processed_stocks.append(processed)
    
    if not processed_stocks:
        return {
            'quarter': quarter or 'N/A',
            'top_performers': [],
            'worst_performers': [],
            'latest_results': [],
            'all_stocks': [],
            'last_updated': datetime.now()
        }
        
    df = pd.DataFrame(processed_stocks)
    
    result = {
        'quarter': quarter or df.iloc[0]['quarter'],
        'top_performers': df.nlargest(10, 'net_profit_growth').to_dict('records'),
        'worst_performers': df.nsmallest(10, 'net_profit_growth').to_dict('records'),
        'latest_results': df.sort_values('result_date', ascending=False).head(10).to_dict('records'),
        'all_stocks': processed_stocks,
        'last_updated': datetime.now()
    }
    
    market_data_cache[cache_key] = result
    return result