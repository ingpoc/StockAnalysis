from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from src.api import router
from src.api.registry import API_DOCUMENTATION
from src.utils.database import connect_to_mongodb, close_mongodb_connection, ensure_indexes
from src.utils.cache import init_redis
from src.config import settings
import logging
from src.utils.logging_config import setup_logging

# Configure logging to write to file
logger = setup_logging()


app = FastAPI(
    title="Stock Analysis API",
    description="API for stock analysis and financial data",
    version="1.0.0",
)

# Global exception handler for consistent error responses
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTP error: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error": str(exc)}
    )

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the API router
app.include_router(router, prefix=settings.API_PREFIX)

@app.on_event("startup")
async def startup_db_client():
    """Initialize MongoDB connection and Redis on startup"""
    logger.info("Starting up database connection")
    await connect_to_mongodb()
    await ensure_indexes()
    logger.info("Database connection established")
    await init_redis()

@app.on_event("shutdown")
async def shutdown_db_client():
    """Close MongoDB connection on shutdown"""
    logger.info("Shutting down database connection")
    await close_mongodb_connection()
    logger.info("Database connection closed")

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