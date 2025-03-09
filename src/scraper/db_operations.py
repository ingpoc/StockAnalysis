"""
Database operations module for financial data.
Provides functions to store and retrieve financial data from MongoDB.
"""
import os
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo.errors import PyMongoError
from dotenv import load_dotenv
from bson import ObjectId

# Load environment variables
load_dotenv()

# Import the centralized logger
from src.utils.logger import logger
from src.services.market_service import MarketService

# Shared market service instance for cache invalidation
market_service = MarketService()

async def get_db_connection(mongo_uri: Optional[str] = None) -> AsyncIOMotorClient:
    """
    Get a database connection.
    
    Args:
        mongo_uri (str, optional): MongoDB connection URI.
        
    Returns:
        AsyncIOMotorClient: MongoDB client.
    """
    if not mongo_uri:
        mongo_uri = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017')
    
    try:
        client = AsyncIOMotorClient(mongo_uri)
        return client
    except Exception as e:
        logger.error(f"Error connecting to MongoDB: {str(e)}")
        raise

async def get_db_collection(db_name: str = 'stock_analysis', collection_name: str = 'detailed_financials') -> AsyncIOMotorCollection:
    """
    Get a database collection.
    
    Args:
        db_name (str): Database name.
        collection_name (str): Collection name.
        
    Returns:
        AsyncIOMotorCollection: MongoDB collection.
    """
    mongo_uri = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017')
    
    try:
        client = await get_db_connection(mongo_uri)
        db = client[db_name]
        collection = db[collection_name]
        return collection
    except Exception as e:
        logger.error(f"Error getting MongoDB collection: {str(e)}")
        raise

async def store_financial_data(data: Dict[str, Any], collection: AsyncIOMotorCollection) -> bool:
    """
    Store financial data in the database.
    
    Args:
        data (Dict[str, Any]): Financial data.
        collection (AsyncIOMotorCollection): MongoDB collection.
        
    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        # Extract company_name and quarter from data
        company_name = data.get('company_name')
        quarter = data.get('quarter')
        
        if not company_name or not quarter:
            logger.error("Missing company_name or quarter in data")
            return False
        
        # Update or insert financial data
        result = await update_or_insert_company_data(company_name, quarter, data, collection)
        
        # Invalidate the cache for this quarter
        if result and quarter:
            market_service.invalidate_market_data_cache(quarter)
            logger.info(f"Invalidated market data cache for quarter {quarter} after updating {company_name}")
        
        return result
    except Exception as e:
        logger.error(f"Error storing financial data: {str(e)}")
        return False

async def store_multiple_financial_data(data_list: List[Dict[str, Any]], collection: AsyncIOMotorCollection) -> bool:
    """
    Store multiple financial data records in the database.
    
    Args:
        data_list (List[Dict[str, Any]]): List of financial data.
        collection (AsyncIOMotorCollection): MongoDB collection.
        
    Returns:
        bool: True if all successful, False if any failed.
    """
    if not data_list:
        return True
    
    try:
        # Keep track of quarters that need cache invalidation
        quarters_to_invalidate = set()
        
        success = True
        for data in data_list:
            result = await store_financial_data(data, collection)
            
            # Add the quarter to the invalidation set if the operation succeeded
            if result and 'quarter' in data:
                quarters_to_invalidate.add(data['quarter'])
                
            success = success and result
        
        # Invalidate cache for all affected quarters
        for quarter in quarters_to_invalidate:
            market_service.invalidate_market_data_cache(quarter)
            logger.info(f"Invalidated market data cache for quarter {quarter} after batch update")
        
        return success
    except Exception as e:
        logger.error(f"Error storing multiple financial data: {str(e)}")
        return False

async def update_or_insert_company_data(company_name: str, quarter: str, financial_data: Dict[str, Any], 
                                   collection: AsyncIOMotorCollection) -> bool:
    """
    Update or insert company financial data for a specific quarter.
    
    Args:
        company_name (str): Company name.
        quarter (str): Quarter (e.g., 'Q1 2023').
        financial_data (Dict[str, Any]): Financial data.
        collection (AsyncIOMotorCollection): MongoDB collection.
        
    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        # Check if the company already exists
        company = await collection.find_one({'company_name': company_name})
        
        if company:
            logger.info(f"Company {company_name} found in database")
            
            # Check if the company already has metrics for this quarter
            existing_quarters = [metric.get('quarter') for metric in company.get('financial_metrics', [])]
            
            if quarter in existing_quarters:
                logger.info(f"Skipping {company_name} for {quarter} - data already exists in database.")
                return True
            
            # Add new quarter metrics to the company
            logger.info(f"Adding new quarter {quarter} to {company_name}")
            
            # Create a new financial metric
            new_metric = {
                'quarter': quarter,
                'recorded_at': datetime.now(),
                'cmp': financial_data.get('cmp', ''),
                'pe_ratio': financial_data.get('pe_ratio', ''),
                'market_cap': financial_data.get('market_cap', ''),
                'sales': financial_data.get('sales', ''),
                'sales_growth': financial_data.get('sales_growth', ''),
                'ebitda': financial_data.get('ebitda', ''),
                'ebitda_growth': financial_data.get('ebitda_growth', ''),
                'pbt': financial_data.get('pbt', ''),
                'pbt_growth': financial_data.get('pbt_growth', ''),
                'net_profit': financial_data.get('net_profit', ''),
                'net_profit_growth': financial_data.get('net_profit_growth', ''),
                'result_date': financial_data.get('result_date', ''),
                'strengths': financial_data.get('strengths', ''),
                'weaknesses': financial_data.get('weaknesses', ''),
                'opportunities': financial_data.get('opportunities', ''),
                'threats': financial_data.get('threats', ''),
                'financials_url': financial_data.get('financials_url', ''),
                'recommendation': financial_data.get('recommendation', '')
            }
            
            # Update the company with the new financial metric
            result = await collection.update_one(
                {'_id': company['_id']},
                {'$push': {'financial_metrics': new_metric}}
            )
            
            # Invalidate the cache for this quarter
            market_service.invalidate_market_data_cache(quarter)
            logger.info(f"Invalidated market data cache for quarter {quarter} after adding new metrics to {company_name}")
            
            return result.modified_count > 0
        else:
            logger.info(f"Creating new company entry for {company_name}")
            
            # Create a new company entry
            new_company = {
                'company_name': company_name,
                'symbol': financial_data.get('symbol', ''),
                'sector': financial_data.get('sector', ''),
                'industry': financial_data.get('industry', ''),
                'description': financial_data.get('description', ''),
                'created_at': datetime.now(),
                'updated_at': datetime.now(),
                'financial_metrics': [{
                    'quarter': quarter,
                    'recorded_at': datetime.now(),
                    'cmp': financial_data.get('cmp', ''),
                    'pe_ratio': financial_data.get('pe_ratio', ''),
                    'market_cap': financial_data.get('market_cap', ''),
                    'sales': financial_data.get('sales', ''),
                    'sales_growth': financial_data.get('sales_growth', ''),
                    'ebitda': financial_data.get('ebitda', ''),
                    'ebitda_growth': financial_data.get('ebitda_growth', ''),
                    'pbt': financial_data.get('pbt', ''),
                    'pbt_growth': financial_data.get('pbt_growth', ''),
                    'net_profit': financial_data.get('net_profit', ''),
                    'net_profit_growth': financial_data.get('net_profit_growth', ''),
                    'result_date': financial_data.get('result_date', ''),
                    'strengths': financial_data.get('strengths', ''),
                    'weaknesses': financial_data.get('weaknesses', ''),
                    'opportunities': financial_data.get('opportunities', ''),
                    'threats': financial_data.get('threats', ''),
                    'financials_url': financial_data.get('financials_url', ''),
                    'recommendation': financial_data.get('recommendation', '')
                }]
            }
            
            result = await collection.insert_one(new_company)
            
            # Invalidate the cache for this quarter
            market_service.invalidate_market_data_cache(quarter)
            logger.info(f"Invalidated market data cache for quarter {quarter} after creating new company {company_name}")
            
            return result.inserted_id is not None
    except Exception as e:
        logger.error(f"Error updating or inserting company data: {str(e)}")
        return False

async def get_financial_data_by_company(company_name: str, collection: AsyncIOMotorCollection) -> Optional[Dict[str, Any]]:
    """
    Get financial data for a company.
    
    Args:
        company_name (str): Company name.
        collection (AsyncIOMotorCollection): MongoDB collection.
        
    Returns:
        Dict[str, Any]: Financial data.
    """
    try:
        return await collection.find_one({'company_name': company_name})
    except Exception as e:
        logger.error(f"Error getting financial data for {company_name}: {str(e)}")
        return None

async def get_financial_data_by_symbol(symbol: str, collection: AsyncIOMotorCollection) -> Optional[Dict[str, Any]]:
    """
    Get financial data for a company by symbol.
    
    Args:
        symbol (str): Company symbol.
        collection (AsyncIOMotorCollection): MongoDB collection.
        
    Returns:
        Dict[str, Any]: Financial data.
    """
    try:
        return await collection.find_one({'symbol': symbol})
    except Exception as e:
        logger.error(f"Error getting financial data for symbol {symbol}: {str(e)}")
        return None

async def remove_quarter_from_all_companies(quarter: str, collection: AsyncIOMotorCollection) -> int:
    """
    Remove a specific quarter's financial metrics from all companies.
    
    Args:
        quarter (str): Quarter to remove (e.g., 'Q1 2023').
        collection (AsyncIOMotorCollection): MongoDB collection.
        
    Returns:
        int: Number of companies updated.
    """
    try:
        # Pull all financial metrics with the specified quarter
        result = await collection.update_many(
            {}, 
            {'$pull': {'financial_metrics': {'quarter': quarter}}}
        )
        
        # Invalidate cache for this quarter
        market_service.invalidate_market_data_cache(quarter)
        logger.info(f"Invalidated market data cache for quarter {quarter} after removing it from all companies")
        
        logger.info(f"Removed quarter {quarter} from {result.modified_count} companies")
        return result.modified_count
    except Exception as e:
        logger.error(f"Error removing quarter {quarter} from companies: {str(e)}")
        return 0 