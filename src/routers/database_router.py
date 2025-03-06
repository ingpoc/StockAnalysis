"""
API router for database operations.
"""
from fastapi import APIRouter

from src.utils.database import backup_router, restore_router, validate_router

# Create a combined router for all database operations
router = APIRouter(
    prefix="/database",
    tags=["database"],
    responses={404: {"description": "Not found"}},
)

# Include all database routers
router.include_router(backup_router, prefix="")
router.include_router(restore_router, prefix="")
router.include_router(validate_router, prefix="") 