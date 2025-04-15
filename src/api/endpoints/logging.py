from fastapi import APIRouter, Body
from typing import List, Dict, Any
import logging
import os
from datetime import datetime

router = APIRouter()

# Setup a dedicated logger for frontend logs
frontend_logger = logging.getLogger("frontend")
frontend_logger.setLevel(logging.INFO)

# Create logs directory if it doesn't exist
logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'logs')
os.makedirs(logs_dir, exist_ok=True)

# Create a file handler that overwrites on each restart
log_file = os.path.join(logs_dir, 'frontend.log')
file_handler = logging.FileHandler(log_file, mode='w')
file_handler.setLevel(logging.INFO)

# Create formatter and add it to the handler
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Add the handler to the logger
frontend_logger.addHandler(file_handler)

@router.post("/frontend-logs")
async def store_frontend_logs(logs: List[Dict[Any, Any]] = Body(...)):
    """
    Store logs sent from the frontend
    
    Each log entry should have:
    - level: 'info', 'warn', 'error'
    - message: log message
    - timestamp: (optional) ISO timestamp
    - details: (optional) additional details
    """
    for log in logs:
        level = log.get("level", "info").lower()
        message = log.get("message", "No message")
        timestamp = log.get("timestamp", datetime.now().isoformat())
        details = log.get("details")
        
        log_message = f"[{timestamp}] {message}"
        if details:
            log_message += f" - Details: {details}"
            
        # Comment out all frontend_logger logging to disable dashboard log output
        # if level == "error":
        #     frontend_logger.error(log_message)
        # elif level == "warn":
        #     frontend_logger.warning(log_message)
        # else:
        #     frontend_logger.info(log_message)
            
    return {"status": "success", "logs_received": len(logs)}
