# This file makes the endpoints directory a proper Python package
from src.api.endpoints.portfolio import router as portfolio_router
from src.api.endpoints.market_data import router as market_data_router
from src.api.endpoints.stock import router as stock_router
from src.api.endpoints.analysis import router as analysis_router
from src.api.endpoints.ai_insights import router as ai_insights_router 