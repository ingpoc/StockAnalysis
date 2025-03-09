from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api import router
from src.api.registry import API_DOCUMENTATION
from src.utils.database import connect_to_mongodb, close_mongodb_connection, ensure_indexes
from src.config import settings
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Stock Analysis API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the API router
app.include_router(router, prefix=settings.API_PREFIX)

@app.on_event("startup")
async def startup_db_client():
    logger.info("Starting up database connection...")
    await connect_to_mongodb()
    # Create database indexes for optimized query performance
    await ensure_indexes()
    logger.info("Database initialization complete")

@app.on_event("shutdown")
async def shutdown_db_client():
    await close_mongodb_connection()

@app.get("/")
async def root():
    return {"message": "Welcome to Stock Analysis API"}

@app.get("/api/documentation")
async def api_documentation():
    """
    Get a structured documentation of all available API endpoints.
    This endpoint serves as a single source of truth for the API structure.
    """
    return {
        "documentation": API_DOCUMENTATION,
        "endpoint_count": sum(len(endpoints) for endpoints in API_DOCUMENTATION.values()),
        "categories": list(API_DOCUMENTATION.keys())
    }