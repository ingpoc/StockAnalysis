import aiohttp
import logging
import ssl
import certifi
import json
from typing import Dict, Any
from src.config import settings

logger = logging.getLogger(__name__)

async def analyze_with_xai(stock_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze stock data using xAI's Grok model.
    
    Args:
        stock_data: Dictionary containing stock financial data
        
    Returns:
        Dictionary containing xAI analysis results
    """
    try:
        if not settings.XAI_API_KEY:
            logger.error("XAI_API_KEY not configured")
            return {
                "analysis": "API key not configured",
                "sentiment": {"score": 0.5, "label": "Neutral"},
                "technical_indicators": {},
                "fundamental_analysis": {}
            }

        # Prepare the system prompt and user message
        metrics = stock_data.get("financial_metrics", [])[0] if stock_data.get("financial_metrics") else {}
        
        system_prompt = """You are a professional stock analyst. Analyze the given company's financial metrics 
        and provide a comprehensive analysis including technical indicators, fundamental analysis, and sentiment score. 
        Format your response as a JSON object with the following structure:
        {
            "analysis": "detailed analysis text",
            "sentiment_score": float between 0 and 1,
            "technical_analysis": {key-value pairs of technical indicators},
            "fundamental_analysis": {key-value pairs of fundamental analysis}
        }"""

        user_message = f"""Analyze the following company:
        Company: {stock_data.get('company_name', '')}
        Symbol: {stock_data.get('symbol', '')}
        Financial Metrics: {json.dumps(metrics, indent=2)}
        """

        # Log the request data for debugging
        logger.debug(f"Preparing request to XAI API for symbol: {stock_data.get('symbol', '')}")
        logger.debug(f"Financial metrics: {json.dumps(metrics, indent=2)}")
        
        # Prepare the request payload for Grok
        analysis_data = {
            "model": "grok-2-1212",  # Updated model name per API docs
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "response_format": { "type": "json_object" }
        }

        logger.debug(f"Request payload: {json.dumps(analysis_data, indent=2)}")

        headers = {
            "Authorization": f"Bearer {settings.XAI_API_KEY}",
            "Content-Type": "application/json"
        }

        # Log headers (excluding sensitive info)
        logger.debug("Request headers: Content-Type: application/json")

        # In development mode, disable SSL verification
        if settings.ENVIRONMENT == "development":
            connector = aiohttp.TCPConnector(ssl=False)
            logger.warning("SSL verification disabled in development mode")
        else:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            connector = aiohttp.TCPConnector(ssl=ssl_context)

        api_url = settings.XAI_API_URL or "https://api.x.ai/v1/chat/completions"
        logger.debug(f"Making request to XAI API: {api_url}")
        
        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                async with session.post(
                    api_url,
                    json=analysis_data,
                    headers=headers,
                    timeout=30  # Add timeout
                ) as response:
                    response_text = await response.text()
                    logger.debug(f"XAI API Response Status: {response.status}")
                    logger.debug(f"XAI API Response Headers: {dict(response.headers)}")
                    logger.debug(f"XAI API Response: {response_text}")
                    
                    if response.status != 200:
                        logger.error(f"XAI API error: Status {response.status}, Response: {response_text}")
                        raise Exception(f"XAI API error: {response.status} - {response_text}")
                    
                    result = json.loads(response_text)
                    if 'choices' not in result or not result['choices']:
                        logger.error(f"Invalid response format from XAI API: {result}")
                        raise Exception("Invalid response format from XAI API")
                        
                    analysis_result = json.loads(result['choices'][0]['message']['content'])
                    
                    return {
                        "analysis": analysis_result.get("analysis", ""),
                        "sentiment": {
                            "score": analysis_result.get("sentiment_score", 0.5),
                            "label": get_sentiment_label(analysis_result.get("sentiment_score", 0.5))
                        },
                        "technical_indicators": analysis_result.get("technical_analysis", {}),
                        "fundamental_analysis": analysis_result.get("fundamental_analysis", {})
                    }
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Raw response: {response_text}")
                raise Exception("Failed to parse API response")
            except Exception as e:
                logger.error(f"Request failed: {str(e)}")
                raise

    except aiohttp.ClientError as e:
        logger.error(f"Network error during xAI analysis: {str(e)}")
        raise Exception(f"Network error: {str(e)}")
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON response: {str(e)}")
        raise Exception("Invalid API response format")
    except Exception as e:
        logger.error(f"Unexpected error in xAI analysis: {str(e)}")
        raise Exception(f"Analysis failed: {str(e)}")

def get_sentiment_label(score: float) -> str:
    """Convert sentiment score to label"""
    if score >= 0.7:
        return "Very Bullish"
    elif score >= 0.6:
        return "Bullish"
    elif score >= 0.4:
        return "Neutral"
    elif score >= 0.3:
        return "Bearish"
    else:
        return "Very Bearish" 