from pydantic_settings import BaseSettings
from typing import Optional, List, Union
from pydantic import ConfigDict

class Settings(BaseSettings):
    # Environment settings
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    
    # API settings
    API_PREFIX: str = "/api/v1"
    
    # MongoDB settings
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "stock_data"
    
    # Redis settings
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_DB: int = 0
    
    # API Keys
    NEWS_API_KEY: Optional[str] = None
    XAI_API_KEY: str = ""
    
    # API URLs
    XAI_API_URL: str = "https://api.x.ai/v1/chat/completions"
    
    # Cache settings
    CACHE_TTL: int = 300
    
    # Rate limiting
    ENABLE_RATE_LIMIT: bool = False
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # CORS
    ALLOWED_ORIGINS: str = '["http://localhost:3000", "https://localhost:3000"]'
    
    # Twitter API Settings
    TWITTER_CONSUMER_KEY: Optional[str] = None
    TWITTER_CONSUMER_SECRET: Optional[str] = None
    TWITTER_ACCESS_TOKEN: Optional[str] = None
    TWITTER_ACCESS_TOKEN_SECRET: Optional[str] = None
    TWITTER_BEARER_TOKEN: Optional[str] = None

    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra='allow'  # This allows extra fields in the environment
    )

    def validate(self) -> None:
        if not self.XAI_API_KEY:
            raise ValueError("XAI_API_KEY must be set in environment variables")
        if not self.XAI_API_URL:
            raise ValueError("XAI_API_URL must be set in environment variables")

settings = Settings()