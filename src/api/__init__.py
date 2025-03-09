# This file makes the api directory a proper Python package
from fastapi import APIRouter
from src.api.registry import api_router as registry_router

# Create main API router and include the registry router
router = APIRouter()
router.include_router(registry_router)

# Export the API_DOCUMENTATION for external use (e.g., OpenAPI docs enhancement)
from src.api.registry import API_DOCUMENTATION

# The router structure is now centralized and managed in registry.py
# This provides a single place to see all API endpoints while maintaining
# the modularity of individual endpoint files. 