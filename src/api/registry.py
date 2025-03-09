"""
API Registry - Central registry of all API endpoints in the application.

This file provides a complete overview of all available endpoints and serves as
the single source of truth for the API structure.
"""
from fastapi import APIRouter
from typing import Dict, List, Tuple, Any

# Import all endpoint routers
from src.api.endpoints.portfolio import router as portfolio_router
from src.api.endpoints.market_data import router as market_data_router
from src.api.endpoints.stock import router as stock_router
from src.api.endpoints.analysis import router as analysis_router
from src.api.endpoints.ai_insights import router as ai_insights_router
from src.api.endpoints.database_management import router as database_management_router
from src.routers.scraper_router import router as scraper_router

# Create main API router without prefix (prefix is added in main.py)
api_router = APIRouter()

# Dictionary of all routers with their prefixes and tags
ROUTER_CONFIG: List[Tuple[APIRouter, str, List[str]]] = [
    # (router, prefix, tags)
    (portfolio_router, "/portfolio", ["portfolio"]),
    (market_data_router, "", ["market"]),  # Root endpoints like /market-data
    (stock_router, "/stock", ["stock"]),
    (analysis_router, "/analysis", ["analysis"]),
    (analysis_router, "/stock", ["analysis"]),  # Mounted twice with different prefixes
    (ai_insights_router, "/ai/insights", ["ai"]),
    (database_management_router, "/admin", ["database"]),
    (scraper_router, "/scraper", ["scraper"]),
]

# Register all routers
for router, prefix, tags in ROUTER_CONFIG:
    api_router.include_router(router, prefix=prefix, tags=tags)

# Complete API documentation for reference
API_DOCUMENTATION = {
    "Market Data": [
        {
            "method": "GET",
            "path": "/market-data",
            "description": "Fetches market overview data including top/worst performers and latest results",
            "params": {
                "quarter": "(optional) Specific quarter to fetch data for",
                "force_refresh": "(optional) Boolean to force refresh cache"
            }
        },
        {
            "method": "GET",
            "path": "/quarters",
            "description": "Retrieves a list of all available quarters in the database",
            "params": {
                "force_refresh": "(optional) Boolean to force refresh cache"
            }
        }
    ],
    "Stock": [
        {
            "method": "GET",
            "path": "/stock/{symbol}",
            "description": "Gets detailed financial information for a specific stock",
            "params": {
                "symbol": "Stock ticker symbol"
            }
        },
        {
            "method": "POST",
            "path": "/stock/batch",
            "description": "Fetches details for multiple stocks in a single request",
            "body": "Array of stock symbols"
        },
        {
            "method": "POST",
            "path": "/stock/{symbol}/refresh-analysis",
            "description": "Triggers a refresh of the analysis for a specific stock",
            "params": {
                "symbol": "Stock ticker symbol"
            }
        }
    ],
    "Portfolio": [
        {
            "method": "GET",
            "path": "/portfolio/holdings",
            "description": "Retrieves all holdings in the user's portfolio"
        },
        {
            "method": "GET",
            "path": "/portfolio/holdings/enriched",
            "description": "Gets holdings with current price and performance data"
        },
        {
            "method": "POST",
            "path": "/portfolio/holdings",
            "description": "Adds a new holding to the portfolio",
            "body": "Holding details"
        },
        {
            "method": "PUT",
            "path": "/portfolio/holdings/{holding_id}",
            "description": "Updates an existing holding",
            "params": {
                "holding_id": "ID of the holding to update"
            },
            "body": "Updated holding details"
        },
        {
            "method": "DELETE",
            "path": "/portfolio/holdings/{holding_id}",
            "description": "Removes a holding from the portfolio",
            "params": {
                "holding_id": "ID of the holding to delete"
            }
        },
        {
            "method": "DELETE",
            "path": "/portfolio/holdings",
            "description": "Clears all holdings from the portfolio"
        },
        {
            "method": "POST",
            "path": "/portfolio/import-csv",
            "description": "Imports holdings from a CSV file",
            "body": "CSV data"
        }
    ],
    "Analysis": [
        {
            "method": "GET",
            "path": "/analysis/{symbol}",
            "description": "Gets the AI-generated analysis for a stock",
            "params": {
                "symbol": "Stock ticker symbol"
            }
        },
        {
            "method": "GET", 
            "path": "/analysis/{symbol}/history",
            "description": "Retrieves historical analyses for a stock",
            "params": {
                "symbol": "Stock ticker symbol"
            }
        },
        {
            "method": "POST",
            "path": "/analysis/{symbol}/refresh",
            "description": "Triggers a new analysis generation for a stock",
            "params": {
                "symbol": "Stock ticker symbol"
            }
        }
    ],
    "AI Insights": [
        {
            "method": "GET",
            "path": "/ai/insights/{symbol}",
            "description": "Retrieves AI-generated insights for a stock",
            "params": {
                "symbol": "Stock ticker symbol"
            }
        }
    ],
    "Database Management": [
        {
            "method": "POST",
            "path": "/admin/backup-database",
            "description": "Creates a backup of the database"
        },
        {
            "method": "POST", 
            "path": "/admin/restore",
            "description": "Restores the database from a backup",
            "body": "Backup file details"
        },
        {
            "method": "GET",
            "path": "/admin/database-stats",
            "description": "Gets statistics about the database"
        }
    ],
    "Scraper": [
        {
            "method": "POST",
            "path": "/scraper/scrape",
            "description": "Triggers the scraping process for financial data",
            "body": "Scraping parameters and options"
        },
        {
            "method": "POST",
            "path": "/scraper/remove-quarter",
            "description": "Removes all scraped data for a specific quarter",
            "body": "Quarter to remove (e.g., {'quarter': 'Q1 2023'})"
        }
    ]
}

def get_all_endpoints() -> Dict[str, List[Dict[str, Any]]]:
    """
    Return the complete API documentation.
    
    Returns:
        Dict[str, List[Dict[str, Any]]]: Structured documentation of all endpoints.
    """
    return API_DOCUMENTATION 