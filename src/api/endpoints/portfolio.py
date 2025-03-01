from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from typing import List, Optional
from src.models.schemas import Holding, HoldingsList, EnrichedHolding
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
    asset_type: str = Form("stock"),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """Import holdings from CSV file"""
    try:
        # Validate asset_type
        valid_asset_types = ["stock", "crypto", "mutual_fund"]
        if asset_type not in valid_asset_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid asset type. Must be one of: {', '.join(valid_asset_types)}"
            )
            
        # Read the file content
        content = await file.read()
        csv_content = content.decode("utf-8")
        
        # Import holdings from CSV with asset type
        holdings = await portfolio_service.import_holdings_from_csv(csv_content, asset_type)
        return holdings
    except Exception as e:
        logger.error(f"Error importing {asset_type} holdings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/holdings/enriched", response_model=List[EnrichedHolding])
async def get_enriched_holdings(portfolio_service: PortfolioService = Depends(get_portfolio_service)):
    """
    Get all holdings enriched with current price information.
    This endpoint combines portfolio data with current market prices in a single API call.
    """
    try:
        return await portfolio_service.get_batch_enriched_holdings()
    except Exception as e:
        logger.error(f"Error fetching enriched holdings: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 