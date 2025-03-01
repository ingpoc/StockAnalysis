# This file makes the api directory a proper Python package
from fastapi import APIRouter
from src.api.endpoints import (
    portfolio_router,
    market_data_router,
    stock_router, 
    analysis_router,
    ai_insights_router
)

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

# Endpoint URL structure:
# /portfolio/holdings - Portfolio management
# /market-data - Market overview data
# /quarters - Available quarters
# /stock/{symbol} - Stock details
# /stock/{symbol}/analysis-history - Analysis history
# /stock/{symbol}/refresh-analysis - Generate new analysis
# /analysis/{analysis_id} - Get specific analysis content
# /ai_insights/* - Additional AI insight endpoints

# Add other routers as needed
# router.include_router(market_router, prefix="/market-data", tags=["market"])
# router.include_router(stock_router, prefix="/stock", tags=["stock"])
# router.include_router(analysis_router, prefix="/analysis", tags=["analysis"]) 