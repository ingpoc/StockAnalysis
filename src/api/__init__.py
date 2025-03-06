# This file makes the api directory a proper Python package
from fastapi import APIRouter
from src.api.endpoints import (
    portfolio_router,
    market_data_router,
    stock_router, 
    analysis_router,
    ai_insights_router,
    database_management_router
)
from src.routers.scraper import router as scraper_router

# Create main API router
router = APIRouter()

# Include all endpoints
router.include_router(portfolio_router, prefix="/portfolio", tags=["portfolio"])
router.include_router(market_data_router, tags=["market"])
router.include_router(stock_router, prefix="/stock", tags=["stock"])

# Special case: Include analysis router twice
# Once with /stock prefix for analysis-history and refresh-analysis
router.include_router(analysis_router, prefix="/stock", tags=["analysis"])
# And once with /analysis prefix for retrieving analysis by ID
router.include_router(analysis_router, prefix="/analysis", tags=["analysis"])

# AI insights routes
router.include_router(ai_insights_router, prefix="/ai_insights", tags=["ai"])

# Include the scraper router
router.include_router(scraper_router, tags=["scraper"])

# Include the database management router
router.include_router(database_management_router, prefix="/database", tags=["database"])

# Endpoint URL structure:
# /portfolio/holdings - Portfolio management
# /market-data - Market overview data
# /quarters - Available quarters
# /stock/{symbol} - Stock details
# /stock/{symbol}/analysis-history - Analysis history
# /stock/{symbol}/refresh-analysis - Generate new analysis
# /analysis/{analysis_id} - Get specific analysis content
# /ai_insights/* - Additional AI insight endpoints
# /scraper/scrape - Scrape financial data from MoneyControl
# /scraper/companies - Get all companies' financial data
# /scraper/company/{company_name} - Get financial data for a specific company
# /database/backup - Backup the database
# /database/restore - Restore the database from a backup
# /database/check - Check the database structure and content
# /database/backups - List all available database backups

# Add other routers as needed
# router.include_router(market_router, prefix="/market-data", tags=["market"])
# router.include_router(stock_router, prefix="/stock", tags=["stock"])
# router.include_router(analysis_router, prefix="/analysis", tags=["analysis"]) 