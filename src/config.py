import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    # MongoDB settings
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    DB_NAME = os.getenv("DB_NAME", "stock_data")
    
    # API Keys
    NEWS_API_KEY = os.getenv("NEWS_API_KEY")
    XAI_API_KEY = os.getenv("XAI_API_KEY")
    
    # Cache settings
    CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))  # 5 minutes default
    
    # API settings
    API_VERSION = "v1"
    API_PREFIX = f"/api/{API_VERSION}"

settings = Settings()