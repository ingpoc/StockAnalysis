#!/usr/bin/env python3
"""
Database validation utility.

This module provides functions to validate the database structure and data integrity.
It can be used as a standalone script or imported as a module.
"""
import asyncio
import argparse
import logging
import os
import sys
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from bson import ObjectId

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("db-validator")

# Database configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGODB_DATABASE_NAME", "stock_data")

# Create router for API endpoints
router = APIRouter(
    prefix="/database",
    tags=["database"],
    responses={404: {"description": "Not found"}},
)

class DatabaseValidator:
    """Database validation utility."""
    
    def __init__(self):
        """Initialize the database validator."""
        # Initialize errors and warnings lists
        self.errors = []
        self.warnings = []
        
        # We'll connect to MongoDB in validate_all method
        self.client = None
        self.db = None
    
    async def validate_all(self) -> Dict[str, Any]:
        """
        Validate all collections in the database.
        
        Returns:
            Dict[str, Any]: Validation results.
        """
        try:
            # Connect to MongoDB
            mongodb_uri = os.getenv('MONGODB_CONNECTION_STRING', 'mongodb://localhost:27017')
            db_name = os.getenv('MONGODB_DATABASE_NAME', 'stock_data')
            
            self.client = AsyncIOMotorClient(mongodb_uri)
            self.db = self.client[db_name]
            
            logger.info(f"Validating all collections in database {db_name}")
            
            # Initialize results
            results = {
                "status": "success",
                "errors": [],
                "warnings": [],
                "summary": {
                    "collections_checked": 0,
                    "collections_summary": {}
                }
            }
            
            # Get all collection names
            collection_names = await self.db.list_collection_names()
            logger.info(f"Found {len(collection_names)} collections: {', '.join(collection_names)}")
            
            # Validate each collection
            for collection_name in collection_names:
                collection = self.db[collection_name]
                collection_results = await self.validate_collection(collection_name, collection)
                
                # Add collection summary to results
                results["summary"]["collections_summary"][collection_name] = collection_results
                results["summary"]["collections_checked"] += 1
            
            # Check relationships between collections
            await self.check_relationships()
            
            # Add errors and warnings
            results["errors"] = [{"collection": e[0], "message": e[1]} for e in self.errors]
            results["warnings"] = [{"collection": w[0], "message": w[1]} for w in self.warnings]
            
            # Set status based on errors
            if results["errors"]:
                results["status"] = "error"
            elif results["warnings"]:
                results["status"] = "warning"
            
            return results
        except Exception as e:
            logger.error(f"Error validating database: {str(e)}")
            return {
                "status": "error",
                "errors": [{"collection": "global", "message": str(e)}],
                "warnings": [],
                "summary": {"collections_checked": 0}
            }
    
    async def validate_collection(self, collection_name: str, collection: AsyncIOMotorCollection) -> Dict[str, Any]:
        """
        Validate a collection.
        
        Args:
            collection_name (str): Name of the collection.
            collection (AsyncIOMotorCollection): MongoDB collection.
            
        Returns:
            Dict[str, Any]: Collection validation results.
        """
        logger.info(f"Validating collection: {collection_name}")
        
        # Initialize collection results
        collection_results = {
            "name": collection_name,
            "document_count": 0,
            "sample_fields": [],
            "quarters": []
        }
        
        try:
            # Count documents
            document_count = await collection.count_documents({})
            collection_results["document_count"] = document_count
            logger.info(f"Collection {collection_name} has {document_count} documents")
            
            # Get a sample document
            if document_count > 0:
                sample = await collection.find_one()
                if sample:
                    # Convert ObjectId to string
                    if "_id" in sample and isinstance(sample["_id"], ObjectId):
                        sample["_id"] = str(sample["_id"])
                    
                    # Get sample fields
                    collection_results["sample_fields"] = list(sample.keys())
                    
                    # Extract quarters if available
                    if collection_name == "detailed_financials" and "quarter" in sample:
                        # Get distinct quarters
                        quarters = await collection.distinct("quarter")
                        collection_results["quarters"] = quarters
                        logger.info(f"Found {len(quarters)} quarters in {collection_name}")
            
            # Validate specific collections
            if collection_name == "detailed_financials":
                await self.validate_detailed_financials(collection, collection_results)
            elif collection_name == "holdings":
                await self.validate_holdings(collection, collection_results)
            elif collection_name == "ai_analysis":
                await self.validate_ai_analysis(collection, collection_results)
            else:
                await self.validate_generic(collection, collection_name, collection_results)
        
        except Exception as e:
            logger.error(f"Error validating collection {collection_name}: {str(e)}")
            self.add_error(collection_name, f"Validation error: {str(e)}")
        
        return collection_results
    
    async def validate_detailed_financials(self, collection: AsyncIOMotorCollection, results: Dict[str, Any]) -> None:
        """
        Validate the detailed_financials collection.
        
        Args:
            collection (AsyncIOMotorCollection): MongoDB collection.
            results (Dict[str, Any]): Results dictionary to update.
        """
        logger.info("Validating detailed_financials collection")
        
        # Check if collection is empty
        if results["document_count"] == 0:
            self.add_warning("detailed_financials", "Collection is empty")
            return
        
        # Check for required fields in a sample document
        sample = await collection.find_one()
        if not sample:
            self.add_warning("detailed_financials", "Could not retrieve sample document")
            return
        
        required_fields = ["company_name", "symbol", "quarter", "financial_metrics"]
        missing_fields = [field for field in required_fields if field not in sample]
        
        if missing_fields:
            self.add_error("detailed_financials", f"Missing required fields: {', '.join(missing_fields)}")
        
        # Check financial_metrics structure
        if "financial_metrics" in sample:
            metrics = sample["financial_metrics"]
            if not isinstance(metrics, list):
                self.add_error("detailed_financials", "financial_metrics is not a list")
            elif len(metrics) == 0:
                self.add_warning("detailed_financials", "financial_metrics list is empty")
            else:
                # Check first metrics item
                first_metric = metrics[0]
                if not isinstance(first_metric, dict):
                    self.add_error("detailed_financials", "financial_metrics item is not a dictionary")
                else:
                    # Check for key metrics
                    key_metrics = ["revenue", "net_profit", "gross_profit"]
                    missing_metrics = [metric for metric in key_metrics if metric not in first_metric]
                    if missing_metrics:
                        self.add_warning("detailed_financials", f"Missing key metrics: {', '.join(missing_metrics)}")
        
        # Check for duplicate entries
        company_counts = {}
        async for doc in collection.aggregate([
            {"$group": {"_id": {"company": "$company_name", "quarter": "$quarter"}, "count": {"$sum": 1}}},
            {"$match": {"count": {"$gt": 1}}}
        ]):
            company = doc["_id"]["company"]
            quarter = doc["_id"]["quarter"]
            count = doc["count"]
            company_counts[f"{company}_{quarter}"] = count
            self.add_warning("detailed_financials", f"Duplicate entries for {company} in quarter {quarter}: {count}")
        
        # Add duplicate info to results
        if company_counts:
            results["duplicates"] = company_counts
    
    async def validate_holdings(self, collection: AsyncIOMotorCollection, results: Dict[str, Any]) -> None:
        """
        Validate the holdings collection.
        
        Args:
            collection (AsyncIOMotorCollection): Collection to validate.
            results (Dict[str, Any]): Validation results to update.
        """
        logger.info("Validating holdings collection")
        
        # Check for documents without symbol
        missing_symbol = await collection.count_documents({"symbol": {"$exists": False}})
        if missing_symbol > 0:
            self.add_error("holdings", f"Found {missing_symbol} documents without symbol")
        
        # Check for documents without quantity
        missing_quantity = await collection.count_documents({"quantity": {"$exists": False}})
        if missing_quantity > 0:
            self.add_error("holdings", f"Found {missing_quantity} documents without quantity")
        
        # Check for documents without purchase_price
        missing_price = await collection.count_documents({"purchase_price": {"$exists": False}})
        if missing_price > 0:
            self.add_error("holdings", f"Found {missing_price} documents without purchase_price")
        
        # Check for documents with invalid quantity (non-positive)
        invalid_quantity = await collection.count_documents({"quantity": {"$lte": 0}})
        if invalid_quantity > 0:
            self.add_warning("holdings", f"Found {invalid_quantity} documents with non-positive quantity")
        
        # Check for documents with invalid purchase_price (negative)
        invalid_price = await collection.count_documents({"purchase_price": {"$lt": 0}})
        if invalid_price > 0:
            self.add_warning("holdings", f"Found {invalid_price} documents with negative purchase_price")
        
        # Check for duplicate holdings (same symbol)
        pipeline = [
            {"$group": {"_id": "$symbol", "count": {"$sum": 1}}},
            {"$match": {"count": {"$gt": 1}}}
        ]
        duplicates = await collection.aggregate(pipeline).to_list(length=None)
        if duplicates:
            duplicate_symbols = [d["_id"] for d in duplicates]
            self.add_warning("holdings", f"Found {len(duplicates)} duplicate holdings: {', '.join(duplicate_symbols)}")
    
    async def validate_ai_analysis(self, collection: AsyncIOMotorCollection, results: Dict[str, Any]) -> None:
        """
        Validate the ai_analysis collection.
        
        Args:
            collection (AsyncIOMotorCollection): Collection to validate.
            results (Dict[str, Any]): Validation results to update.
        """
        logger.info("Validating ai_analysis collection")
        
        # Check for documents without symbol
        missing_symbol = await collection.count_documents({"symbol": {"$exists": False}})
        if missing_symbol > 0:
            self.add_error("ai_analysis", f"Found {missing_symbol} documents without symbol")
        
        # Check for documents without analysis_type
        missing_type = await collection.count_documents({"analysis_type": {"$exists": False}})
        if missing_type > 0:
            self.add_error("ai_analysis", f"Found {missing_type} documents without analysis_type")
        
        # Check for documents without content
        missing_content = await collection.count_documents({"content": {"$exists": False}})
        if missing_content > 0:
            self.add_error("ai_analysis", f"Found {missing_content} documents without content")
        
        # Check for documents without timestamp
        missing_timestamp = await collection.count_documents({"timestamp": {"$exists": False}})
        if missing_timestamp > 0:
            self.add_warning("ai_analysis", f"Found {missing_timestamp} documents without timestamp")
        
        # Check for duplicate analyses (same symbol and type)
        pipeline = [
            {"$group": {"_id": {"symbol": "$symbol", "type": "$analysis_type"}, "count": {"$sum": 1}}},
            {"$match": {"count": {"$gt": 1}}}
        ]
        duplicates = await collection.aggregate(pipeline).to_list(length=None)
        if duplicates:
            duplicate_entries = [f"{d['_id']['symbol']}:{d['_id']['type']}" for d in duplicates]
            self.add_warning("ai_analysis", f"Found {len(duplicates)} duplicate analyses: {', '.join(duplicate_entries)}")
    
    async def validate_generic(self, collection: AsyncIOMotorCollection, name: str, results: Dict[str, Any]) -> None:
        """
        Validate a generic collection.
        
        Args:
            collection (AsyncIOMotorCollection): Collection to validate.
            name (str): Name of the collection.
            results (Dict[str, Any]): Validation results to update.
        """
        logger.info(f"Performing generic validation for collection: {name}")
        
        # Get a sample document to check fields
        sample = await collection.find_one()
        if sample:
            fields = list(sample.keys())
            results["sample_fields"] = fields
    
    def add_error(self, collection: str, message: str) -> None:
        """
        Add an error to the validation results.
        
        Args:
            collection (str): Name of the collection.
            message (str): Error message.
        """
        logger.error(f"[{collection}] {message}")
        self.errors.append((collection, message))
    
    def add_warning(self, collection: str, message: str) -> None:
        """
        Add a warning to the validation results.
        
        Args:
            collection (str): Name of the collection.
            message (str): Warning message.
        """
        logger.warning(f"[{collection}] {message}")
        self.warnings.append((collection, message))
    
    async def check_relationships(self) -> None:
        """Check relationships between collections."""
        logger.info("Checking relationships between collections")
        
        # Check if all holdings have corresponding financial data
        if "holdings" in await self.db.list_collection_names() and "detailed_financials" in await self.db.list_collection_names():
            holdings = self.db["holdings"]
            financials = self.db["detailed_financials"]
            
            # Get all holding symbols
            holding_symbols = await holdings.distinct("symbol")
            
            # Check each symbol
            for symbol in holding_symbols:
                financial_doc = await financials.find_one({"symbol": symbol})
                if not financial_doc:
                    self.add_warning("relationships", f"Holding with symbol '{symbol}' has no corresponding financial data")
            
            # Check if all AI analyses have corresponding financial data
            if "ai_analysis" in await self.db.list_collection_names():
                analyses = self.db["ai_analysis"]
                
                # Get all analysis symbols
                analysis_symbols = await analyses.distinct("symbol")
                
                # Check each symbol
                for symbol in analysis_symbols:
                    financial_doc = await financials.find_one({"symbol": symbol})
                    if not financial_doc:
                        self.add_warning("relationships", f"Analysis with symbol '{symbol}' has no corresponding financial data")

@router.get("/validate", response_model=Dict[str, Any])
async def api_validate_database():
    """
    API endpoint to validate the database.
    
    Returns:
        Dict[str, Any]: Validation results.
    """
    try:
        logger.info("Starting database validation via API endpoint")
        validator = DatabaseValidator()
        logger.info("Created DatabaseValidator instance")
        results = await validator.validate_all()
        logger.info(f"Validation completed with results: {json.dumps(results, default=str)[:200]}...")
        return results
    except Exception as e:
        logger.error(f"Error validating database: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error validating database: {str(e)}")

def print_validation_results(results: Dict[str, Any]) -> None:
    """
    Print validation results in a readable format.
    
    Args:
        results (Dict[str, Any]): Validation results.
    """
    print("\n=== Database Validation Results ===")
    
    # Print summary
    summary = results["summary"]
    print(f"\nDatabase: {summary['database']}")
    print(f"Collections: {summary['collections_count']}")
    print(f"Errors: {summary['errors_count']}")
    print(f"Warnings: {summary['warnings_count']}")
    
    # Print collection summary
    print("\nCollection Summary:")
    for name, info in summary.get("collections_summary", {}).items():
        print(f"  - {name}: {info['document_count']} documents")
    
    # Print errors
    if results["errors"]:
        print("\nErrors:")
        for error in results["errors"]:
            print(f"  - [{error['collection']}] {error['message']}")
    
    # Print warnings
    if results["warnings"]:
        print("\nWarnings:")
        for warning in results["warnings"]:
            print(f"  - [{warning['collection']}] {warning['message']}")
    
    print("\nValidation completed at:", results["timestamp"])

async def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description="Validate MongoDB database")
    parser.add_argument("--collection", help="Specific collection to validate")
    args = parser.parse_args()
    
    validator = DatabaseValidator()
    
    if args.collection:
        # Validate specific collection
        if args.collection not in await validator.db.list_collection_names():
            print(f"Error: Collection '{args.collection}' not found")
            sys.exit(1)
        
        results = await validator.validate_collection(args.collection, validator.db[args.collection])
    else:
        # Validate all collections
        results = await validator.validate_all()
    
    print_validation_results(results)
    
    # Exit with error code if there are errors
    if results["errors"]:
        sys.exit(1)
    else:
        sys.exit(0)

def validate_database() -> Dict[str, Any]:
    """
    Validate the database structure and data integrity.
    
    Returns:
        Dict[str, Any]: Validation results
    """
    # For non-async contexts
    if not asyncio.get_event_loop().is_running():
        validator = DatabaseValidator()
        return asyncio.run(validator.validate_all())
    else:
        # For async contexts
        async def _validate():
            validator = DatabaseValidator()
            return await validator.validate_all()
        return asyncio.create_task(_validate())

if __name__ == "__main__":
    asyncio.run(main()) 