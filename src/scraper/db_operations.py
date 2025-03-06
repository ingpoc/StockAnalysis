"""
Database operations module for financial data.
Provides functions to store and retrieve financial data from MongoDB.
"""
import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo.errors import PyMongoError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the centralized logger
from src.utils.logger import logger

async def get_db_connection() -> Optional[AsyncIOMotorClient]:
    """
    Get a MongoDB connection.
    
    Returns:
        AsyncIOMotorClient: MongoDB client or None if connection failed.
    """
    try:
        connection_string = os.getenv('MONGODB_CONNECTION_STRING')
        if not connection_string:
            logger.error("MongoDB connection string not found in environment variables")
            return None
        
        logger.info("Connecting to MongoDB")
        client = AsyncIOMotorClient(connection_string)
        logger.info("Connected to MongoDB successfully")
        return client
    except PyMongoError as e:
        logger.error(f"Error connecting to MongoDB: {str(e)}")
        return None

async def get_db_collection(collection_name: Optional[str] = None) -> Optional[AsyncIOMotorCollection]:
    """
    Get a MongoDB collection.
    
    Args:
        collection_name (str, optional): Name of the collection.
        
    Returns:
        AsyncIOMotorCollection: MongoDB collection or None if connection failed.
    """
    try:
        client = await get_db_connection()
        if not client:
            return None
        
        database_name = os.getenv('MONGODB_DATABASE_NAME')
        if not database_name:
            logger.error("MongoDB database name not found in environment variables")
            return None
        
        collection_name = collection_name or os.getenv('MONGODB_FINANCIALS_COLLECTION', 'detailed_financials')
        
        logger.info(f"Getting collection: {collection_name}")
        db = client[database_name]
        collection = db[collection_name]
        return collection
    except PyMongoError as e:
        logger.error(f"Error getting MongoDB collection: {str(e)}")
        return None

async def store_financial_data(financial_data: Dict[str, Any], collection: Optional[AsyncIOMotorCollection] = None) -> bool:
    """
    Store financial data in MongoDB.
    
    Args:
        financial_data (Dict[str, Any]): Financial data to store.
        collection (AsyncIOMotorCollection, optional): MongoDB collection.
        
    Returns:
        bool: True if data was stored successfully, False otherwise.
    """
    try:
        # Get collection if not provided
        if not collection:
            collection = await get_db_collection()
            if not collection:
                return False
        
        # Add timestamp if not present
        if "timestamp" not in financial_data:
            financial_data["timestamp"] = datetime.utcnow()
        
        # Store the data
        logger.info(f"Storing financial data for {financial_data.get('company_name', 'unknown company')}")
        await collection.insert_one(financial_data)
        logger.info("Financial data stored successfully")
        return True
    except PyMongoError as e:
        logger.error(f"Error storing financial data: {str(e)}")
        return False

async def store_multiple_financial_data(financial_data_list: List[Dict[str, Any]], collection: Optional[AsyncIOMotorCollection] = None) -> bool:
    """
    Store multiple financial data entries in MongoDB.
    
    Args:
        financial_data_list (List[Dict[str, Any]]): List of financial data to store.
        collection (AsyncIOMotorCollection, optional): MongoDB collection.
        
    Returns:
        bool: True if data was stored successfully, False otherwise.
    """
    try:
        # Get collection if not provided
        if not collection:
            collection = await get_db_collection()
            if not collection:
                return False
        
        # Add timestamp if not present
        for financial_data in financial_data_list:
            if "timestamp" not in financial_data:
                financial_data["timestamp"] = datetime.utcnow()
        
        # Store the data
        logger.info(f"Storing {len(financial_data_list)} financial data entries")
        await collection.insert_many(financial_data_list)
        logger.info("Financial data stored successfully")
        return True
    except PyMongoError as e:
        logger.error(f"Error storing multiple financial data entries: {str(e)}")
        return False

async def get_financial_data_by_company(company_name: str, limit: int = 0, collection: Optional[AsyncIOMotorCollection] = None) -> List[Dict[str, Any]]:
    """
    Get financial data for a specific company.
    
    Args:
        company_name (str): Name of the company.
        limit (int, optional): Maximum number of documents to return (0 for no limit).
        collection (AsyncIOMotorCollection, optional): MongoDB collection.
        
    Returns:
        List[Dict[str, Any]]: Financial data for the company.
    """
    try:
        # Get collection if not provided
        if collection is None:
            collection = await get_db_collection()
            if collection is None:
                return []
        
        # Query for the company
        query = {"company_name": {"$regex": company_name, "$options": "i"}}
        
        # Execute the query
        logger.info(f"Getting financial data for company: {company_name}")
        cursor = collection.find(query)
        
        # Apply limit if specified
        if limit > 0:
            cursor = cursor.limit(limit)
        
        # Get the results
        financial_data = await cursor.to_list(length=None)
        logger.info(f"Found {len(financial_data)} financial data entries for company: {company_name}")
        return financial_data
    except PyMongoError as e:
        logger.error(f"Error getting financial data for company {company_name}: {str(e)}")
        return []

async def get_financial_data_by_symbol(symbol: str, limit: int = 0, collection: Optional[AsyncIOMotorCollection] = None) -> List[Dict[str, Any]]:
    """
    Get financial data for a specific stock symbol.
    
    Args:
        symbol (str): Stock symbol.
        limit (int, optional): Maximum number of documents to return (0 for no limit).
        collection (AsyncIOMotorCollection, optional): MongoDB collection.
        
    Returns:
        List[Dict[str, Any]]: Financial data for the symbol.
    """
    try:
        # Get collection if not provided
        if not collection:
            collection = await get_db_collection()
            if not collection:
                return []
        
        # Query for the symbol
        query = {"symbol": symbol.upper()}
        
        # Execute the query
        logger.info(f"Getting financial data for symbol: {symbol}")
        cursor = collection.find(query)
        
        # Apply limit if specified
        if limit > 0:
            cursor = cursor.limit(limit)
        
        # Get the results
        financial_data = await cursor.to_list(length=None)
        logger.info(f"Found {len(financial_data)} financial data entries for symbol: {symbol}")
        return financial_data
    except PyMongoError as e:
        logger.error(f"Error getting financial data for symbol {symbol}: {str(e)}")
        return []

async def remove_quarter_from_all_companies(quarter: str, collection: Optional[AsyncIOMotorCollection] = None) -> int:
    """
    Remove a specific quarter from all companies.
    
    Args:
        quarter (str): Quarter to remove (e.g., "Q1 2023").
        collection (AsyncIOMotorCollection, optional): MongoDB collection.
        
    Returns:
        int: Number of documents deleted.
    """
    try:
        # Get collection if not provided
        if not collection:
            collection = await get_db_collection()
            if not collection:
                return 0
        
        # Query for the quarter
        query = {"financial_metrics.quarter": {"$regex": quarter, "$options": "i"}}
        
        # Execute the query
        logger.info(f"Removing quarter {quarter} from all companies")
        result = await collection.delete_many(query)
        deleted_count = result.deleted_count
        logger.info(f"Removed quarter {quarter} from {deleted_count} documents")
        return deleted_count
    except PyMongoError as e:
        logger.error(f"Error removing quarter {quarter} from all companies: {str(e)}")
        return 0 