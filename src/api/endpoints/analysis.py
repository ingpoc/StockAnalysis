from fastapi import APIRouter, HTTPException
from typing import List, Optional
from datetime import datetime
from src.services.ai_service import AIService
import logging
from src.utils.cache import get_from_cache, set_to_cache, CACHE_EXPIRY_SHORT, get_cache_key

router = APIRouter()
ai_service = AIService()
logger = logging.getLogger(__name__)

@router.get("/{symbol}/analysis-history")
async def get_analysis_history(symbol: str):
    """Get historical AI analyses for a stock"""
    cache_key = get_cache_key("analysis_history", symbol)
    cached_data = await get_from_cache(cache_key)
    if cached_data:
        return cached_data
    try:
        analyses = await ai_service.get_analysis_history(symbol)
        response = {
            "analyses": [
                {
                    "id": str(analysis.id),
                    "timestamp": analysis.timestamp,
                    "label": format_analysis_timestamp(analysis.timestamp)
                }
                for analysis in analyses
            ]
        }
        await set_to_cache(cache_key, response, CACHE_EXPIRY_SHORT)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{analysis_id}")
async def get_analysis_content(analysis_id: str):
    """Get specific AI analysis content"""
    cache_key = get_cache_key("analysis_content", analysis_id)
    cached_data = await get_from_cache(cache_key)
    if cached_data:
        return cached_data
    try:
        analysis = await ai_service.get_analysis_by_id(analysis_id)
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")
        await set_to_cache(cache_key, analysis.dict(), CACHE_EXPIRY_SHORT)
        return analysis
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{symbol}/refresh-analysis")
async def refresh_analysis(symbol: str):
    """Generate new AI analysis for a stock"""
    try:
        logger.info(f"Starting refresh analysis for symbol: {symbol}")
        new_analysis = await ai_service.analyze_stock(symbol)
        logger.info(f"Successfully generated analysis for {symbol}")
        return {
            "id": str(new_analysis.id),
            "content": new_analysis.content,
            "timestamp": new_analysis.timestamp,
            "recommendation": new_analysis.recommendation
        }
    except Exception as e:
        logger.error(f"Error in refresh_analysis endpoint for {symbol}: {str(e)}")
        logger.exception("Full traceback:")  # This will log the full stack trace
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate analysis: {str(e)}"
        )

def format_analysis_timestamp(timestamp: datetime) -> str:
    """Format timestamp for display in dropdown"""
    now = datetime.now()
    if timestamp.date() == now.date():
        return f"Today {timestamp.strftime('%H:%M')}"
    elif timestamp.date() == now.date():
        return f"Yesterday {timestamp.strftime('%H:%M')}"
    else:
        return timestamp.strftime('%d %B %Y') 