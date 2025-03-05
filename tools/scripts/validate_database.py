#!/usr/bin/env python3
"""
Database validation utility script.

This script connects to the MongoDB database and performs validation checks
to ensure data integrity and consistency. It's designed to be run directly
from the command line without requiring test files.

Usage:
    python -m tools.scripts.validate_database [--collection COLLECTION]

Options:
    --collection    Specify a collection to validate (default: all collections)
"""

import asyncio
import argparse
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("db-validator")

# Database configuration
MONGODB_URI = "mongodb://localhost:27017"
DB_NAME = "stock_data"

class DatabaseValidator:
    """Database validation utility."""
    
    def __init__(self):
        """Initialize the database validator."""
        self.client = AsyncIOMotorClient(MONGODB_URI)
        self.db = self.client[DB_NAME]
        self.validation_results = {
            "summary": {},
            "errors": [],
            "warnings": []
        }
    
    async def validate_all(self) -> Dict[str, Any]:
        """Validate all collections in the database."""
        collections = await self.db.list_collection_names()
        
        logger.info(f"Found {len(collections)} collections: {', '.join(collections)}")
        
        self.validation_results["summary"] = {
            "total_collections": len(collections),
            "validated_at": datetime.now().isoformat(),
            "collections": {}
        }
        
        for collection_name in collections:
            logger.info(f"Validating collection: {collection_name}")
            
            collection = self.db[collection_name]
            collection_results = await self.validate_collection(collection_name, collection)
            
            self.validation_results["summary"]["collections"][collection_name] = collection_results
        
        return self.validation_results
    
    async def validate_collection(self, collection_name: str, collection: AsyncIOMotorCollection) -> Dict[str, Any]:
        """Validate a specific collection."""
        results = {
            "document_count": await collection.count_documents({}),
            "fields_checked": 0,
            "issues_found": 0
        }
        
        # Collection-specific validation
        if collection_name == "detailed_financials":
            await self.validate_detailed_financials(collection, results)
        elif collection_name == "holdings":
            await self.validate_holdings(collection, results)
        elif collection_name == "ai_analysis":
            await self.validate_ai_analysis(collection, results)
        else:
            # Generic validation for other collections
            await self.validate_generic(collection, collection_name, results)
        
        return results
    
    async def validate_detailed_financials(self, collection: AsyncIOMotorCollection, results: Dict[str, Any]) -> None:
        """Validate the detailed_financials collection."""
        results["fields_checked"] = 3
        
        # Check for missing required fields
        missing_company_name = await collection.count_documents({"company_name": {"$exists": False}})
        missing_symbol = await collection.count_documents({"symbol": {"$exists": False}})
        missing_financials = await collection.count_documents({"financial_metrics": {"$exists": False}})
        
        if missing_company_name > 0:
            self.add_error("detailed_financials", f"Found {missing_company_name} documents without company_name")
            results["issues_found"] += missing_company_name
        
        if missing_symbol > 0:
            self.add_error("detailed_financials", f"Found {missing_symbol} documents without symbol")
            results["issues_found"] += missing_symbol
        
        if missing_financials > 0:
            self.add_error("detailed_financials", f"Found {missing_financials} documents without financial_metrics")
            results["issues_found"] += missing_financials
        
        # Check for empty financial metrics
        empty_financials = await collection.count_documents({"financial_metrics": {"$size": 0}})
        if empty_financials > 0:
            self.add_warning("detailed_financials", f"Found {empty_financials} documents with empty financial_metrics")
            results["issues_found"] += empty_financials
    
    async def validate_holdings(self, collection: AsyncIOMotorCollection, results: Dict[str, Any]) -> None:
        """Validate the holdings collection."""
        results["fields_checked"] = 4
        
        # Check for missing required fields
        missing_symbol = await collection.count_documents({"symbol": {"$exists": False}})
        missing_company = await collection.count_documents({"company_name": {"$exists": False}})
        missing_quantity = await collection.count_documents({"quantity": {"$exists": False}})
        missing_price = await collection.count_documents({"average_price": {"$exists": False}})
        
        if missing_symbol > 0:
            self.add_error("holdings", f"Found {missing_symbol} documents without symbol")
            results["issues_found"] += missing_symbol
        
        if missing_company > 0:
            self.add_error("holdings", f"Found {missing_company} documents without company_name")
            results["issues_found"] += missing_company
        
        if missing_quantity > 0:
            self.add_error("holdings", f"Found {missing_quantity} documents without quantity")
            results["issues_found"] += missing_quantity
        
        if missing_price > 0:
            self.add_error("holdings", f"Found {missing_price} documents without average_price")
            results["issues_found"] += missing_price
        
        # Check for invalid quantities
        invalid_quantity = await collection.count_documents({"quantity": {"$lte": 0}})
        if invalid_quantity > 0:
            self.add_warning("holdings", f"Found {invalid_quantity} documents with quantity <= 0")
            results["issues_found"] += invalid_quantity
    
    async def validate_ai_analysis(self, collection: AsyncIOMotorCollection, results: Dict[str, Any]) -> None:
        """Validate the ai_analysis collection."""
        results["fields_checked"] = 4
        
        # Check for missing required fields
        missing_symbol = await collection.count_documents({"symbol": {"$exists": False}})
        missing_company = await collection.count_documents({"company_name": {"$exists": False}})
        missing_analysis = await collection.count_documents({"analysis": {"$exists": False}})
        missing_timestamp = await collection.count_documents({"timestamp": {"$exists": False}})
        
        if missing_symbol > 0:
            self.add_error("ai_analysis", f"Found {missing_symbol} documents without symbol")
            results["issues_found"] += missing_symbol
        
        if missing_company > 0:
            self.add_error("ai_analysis", f"Found {missing_company} documents without company_name")
            results["issues_found"] += missing_company
        
        if missing_analysis > 0:
            self.add_error("ai_analysis", f"Found {missing_analysis} documents without analysis")
            results["issues_found"] += missing_analysis
        
        if missing_timestamp > 0:
            self.add_error("ai_analysis", f"Found {missing_timestamp} documents without timestamp")
            results["issues_found"] += missing_timestamp
        
        # Check for empty analysis
        empty_analysis = await collection.count_documents({"analysis": ""})
        if empty_analysis > 0:
            self.add_warning("ai_analysis", f"Found {empty_analysis} documents with empty analysis")
            results["issues_found"] += empty_analysis
    
    async def validate_generic(self, collection: AsyncIOMotorCollection, name: str, results: Dict[str, Any]) -> None:
        """Generic validation for other collections."""
        # Simply count documents for now
        results["document_count"] = await collection.count_documents({})
        results["fields_checked"] = 0
        results["issues_found"] = 0
    
    def add_error(self, collection: str, message: str) -> None:
        """Add an error to the validation results."""
        self.validation_results["errors"].append({
            "collection": collection,
            "message": message,
            "timestamp": datetime.now().isoformat()
        })
        logger.error(f"[{collection}] {message}")
    
    def add_warning(self, collection: str, message: str) -> None:
        """Add a warning to the validation results."""
        self.validation_results["warnings"].append({
            "collection": collection,
            "message": message,
            "timestamp": datetime.now().isoformat()
        })
        logger.warning(f"[{collection}] {message}")
    
    async def check_relationships(self) -> None:
        """Check relationships between collections."""
        # Check if holdings have corresponding financial data
        holdings = await self.db.holdings.distinct("symbol")
        financials = await self.db.detailed_financials.distinct("symbol")
        
        # Convert to sets for easier operations
        holdings_set = set(holdings)
        financials_set = set(financials)
        
        # Holdings without financial data
        missing_financials = holdings_set - financials_set
        if missing_financials:
            self.add_warning(
                "relationships", 
                f"Found {len(missing_financials)} holdings without corresponding financial data: "
                f"{', '.join(list(missing_financials)[:5])}{'...' if len(missing_financials) > 5 else ''}"
            )
        
        # Check if all financials have an AI analysis
        analyses = await self.db.ai_analysis.distinct("symbol")
        analyses_set = set(analyses)
        
        missing_analyses = financials_set - analyses_set
        if missing_analyses:
            self.add_warning(
                "relationships",
                f"Found {len(missing_analyses)} financials without corresponding AI analysis: "
                f"{', '.join(list(missing_analyses)[:5])}{'...' if len(missing_analyses) > 5 else ''}"
            )

def print_validation_results(results: Dict[str, Any]) -> None:
    """Print validation results in a readable format."""
    summary = results["summary"]
    print("\n" + "=" * 80)
    print(f"DATABASE VALIDATION RESULTS - {summary.get('validated_at', 'Unknown')}")
    print("=" * 80)
    
    print(f"\nFound {summary.get('total_collections', 0)} collections:\n")
    
    for collection_name, collection_results in summary.get("collections", {}).items():
        print(f"  • {collection_name}:")
        print(f"    - Documents: {collection_results.get('document_count', 0)}")
        print(f"    - Fields checked: {collection_results.get('fields_checked', 0)}")
        print(f"    - Issues found: {collection_results.get('issues_found', 0)}")
    
    if results.get("errors", []):
        print("\nERRORS:")
        for error in results["errors"]:
            print(f"  • [{error['collection']}] {error['message']}")
    
    if results.get("warnings", []):
        print("\nWARNINGS:")
        for warning in results["warnings"]:
            print(f"  • [{warning['collection']}] {warning['message']}")
    
    if not results.get("errors", []) and not results.get("warnings", []):
        print("\nNo issues found! Database validation passed.")
    
    print("\n" + "=" * 80 + "\n")

async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Validate MongoDB database for StockAnalysis")
    parser.add_argument(
        "--collection",
        help="Specific collection to validate (default: all collections)",
        default=None
    )
    args = parser.parse_args()
    
    validator = DatabaseValidator()
    results = await validator.validate_all()
    await validator.check_relationships()
    
    print_validation_results(results)

if __name__ == "__main__":
    asyncio.run(main()) 