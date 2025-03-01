"""
Logger configuration for the application.
"""
import logging
import sys

# Configure the root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Create a logger instance that can be imported by other modules
logger = logging.getLogger("stock_analysis") 