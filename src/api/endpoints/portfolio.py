from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from typing import List, Optional
from src.models.schemas import Holding, HoldingsList
from src.services.portfolio_service import PortfolioService
from bson import ObjectId
from bson.errors import InvalidId
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

def get_portfolio_service():
    return PortfolioService()

@router.get("/holdings", response_model=List[Holding])
async def get_holdings(portfolio_service: PortfolioService = Depends(get_portfolio_service)):
    """Get all holdings"""
    try:
        return await portfolio_service.get_holdings()
    except Exception as e:
        logger.error(f"Error fetching holdings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/holdings", response_model=Holding)
async def add_holding(holding: Holding, portfolio_service: PortfolioService = Depends(get_portfolio_service)):
    """Add a new holding"""
    try:
        return await portfolio_service.add_holding(holding)
    except Exception as e:
        logger.error(f"Error adding holding: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/holdings/{holding_id}", response_model=Optional[Holding])
async def update_holding(
    holding_id: str, 
    holding: Holding, 
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """Update an existing holding"""
    try:
        # Validate holding_id is a valid ObjectId
        try:
            ObjectId(holding_id)
        except InvalidId:
            raise HTTPException(status_code=400, detail="Invalid holding ID format")
            
        updated_holding = await portfolio_service.update_holding(holding_id, holding)
        if not updated_holding:
            raise HTTPException(status_code=404, detail="Holding not found")
        return updated_holding
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating holding: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/holdings/{holding_id}")
async def delete_holding(
    holding_id: str, 
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """Delete a holding"""
    try:
        # Validate holding_id is a valid ObjectId
        try:
            ObjectId(holding_id)
        except InvalidId:
            raise HTTPException(status_code=400, detail="Invalid holding ID format")
            
        success = await portfolio_service.delete_holding(holding_id)
        if not success:
            raise HTTPException(status_code=404, detail="Holding not found")
        return {"message": "Holding deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting holding: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/holdings")
async def clear_holdings(portfolio_service: PortfolioService = Depends(get_portfolio_service)):
    """Clear all holdings"""
    try:
        deleted_count = await portfolio_service.clear_holdings()
        return {"message": f"Deleted {deleted_count} holdings"}
    except Exception as e:
        logger.error(f"Error clearing holdings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/holdings/import", response_model=List[Holding])
async def import_holdings(
    file: UploadFile = File(...),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """Import holdings from CSV file"""
    try:
        # Read the file content
        content = await file.read()
        csv_content = content.decode("utf-8")
        
        # Import holdings from CSV
        holdings = await portfolio_service.import_holdings_from_csv(csv_content)
        return holdings
    except Exception as e:
        logger.error(f"Error importing holdings: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 