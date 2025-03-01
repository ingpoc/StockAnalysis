from fastapi import APIRouter, HTTPException
from typing import List, Optional
from datetime import datetime
from src.services.ai_service import AIService
import logging

router = APIRouter()
ai_service = AIService()
logger = logging.getLogger(__name__)

@router.get("/{symbol}/analysis-history")
async def get_analysis_history(symbol: str):
    """Get historical AI analyses for a stock"""
    try:
        analyses = await ai_service.get_analysis_history(symbol)
        return {
            "analyses": [
                {
                    "id": str(analysis.id),
                    "timestamp": analysis.timestamp,
                    "label": format_analysis_timestamp(analysis.timestamp)
                }
                for analysis in analyses
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{analysis_id}")
async def get_analysis_content(analysis_id: str):
    """Get specific AI analysis content"""
    try:
        analysis = await ai_service.get_analysis_by_id(analysis_id)
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")
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