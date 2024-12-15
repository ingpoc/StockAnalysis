import base64
import os
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def load_portfolio_indicator() -> str:
    """Load portfolio indicator SVG and convert to base64"""
    try:
        with open('assets/portfolio_indicator.svg', 'r') as f:
            svg_content = f.read()
        encoded_svg = base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
        return f'data:image/svg+xml;base64,{encoded_svg}'
    except FileNotFoundError:
        logger.error("Portfolio indicator SVG file not found")
        return ''

@lru_cache(maxsize=1)
def load_ai_indicator() -> str:
    """Load AI indicator SVG based on settings"""
    try:
        from src.utils.database import DatabaseConnection

        # Get selected AI API from settings
        settings_doc = DatabaseConnection.get_collection('settings').find_one(
            {'_id': 'ai_api_selection'}
        )
        selected_api = settings_doc.get('selected_api', 'perplexity') if settings_doc else 'perplexity'
        
        # Choose SVG file based on API
        svg_filename = 'xAI_indicator.svg' if selected_api == 'xai' else 'ai_indicator.svg'

        # Load and encode SVG
        with open(f'assets/{svg_filename}', 'r') as f:
            svg_content = f.read()
        encoded_svg = base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
        return f'data:image/svg+xml;base64,{encoded_svg}'
    except FileNotFoundError:
        logger.error(f"AI indicator SVG file not found")
        return ''
    except Exception as e:
        logger.error(f"Error loading AI indicator: {str(e)}")
        return ''