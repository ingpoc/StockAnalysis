"""
Schemas for financial data scraped from MoneyControl.
"""
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, validator

class FinancialMetric(BaseModel):
    """Schema for individual financial metrics."""
    quarter: Optional[str] = None
    cmp: Optional[str] = None
    revenue: Optional[str] = None
    gross_profit: Optional[str] = None
    net_profit: Optional[str] = None
    net_profit_growth: Optional[str] = None
    gross_profit_growth: Optional[str] = None
    revenue_growth: Optional[str] = None
    result_date: Optional[str] = None
    report_type: Optional[str] = None
    
    # Additional metrics from detailed scraping
    market_cap: Optional[str] = None
    face_value: Optional[str] = None
    book_value: Optional[str] = None
    dividend_yield: Optional[str] = None
    ttm_eps: Optional[str] = None
    ttm_pe: Optional[str] = None
    pb_ratio: Optional[str] = None
    sector_pe: Optional[str] = None
    piotroski_score: Optional[str] = None
    revenue_growth_3yr_cagr: Optional[str] = None
    net_profit_growth_3yr_cagr: Optional[str] = None
    operating_profit_growth_3yr_cagr: Optional[str] = None
    strengths: Optional[str] = None
    weaknesses: Optional[str] = None
    technicals_trend: Optional[str] = None
    fundamental_insights: Optional[str] = None
    fundamental_insights_description: Optional[str] = None

class CompanyFinancials(BaseModel):
    """Schema for company financial data."""
    company_name: str
    symbol: Optional[str] = None
    financial_metrics: List[FinancialMetric]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    @validator('symbol')
    def validate_symbol(cls, symbol):
        """Validate and format the stock symbol."""
        if symbol:
            # Remove any whitespace
            return symbol.strip()
        return symbol

class ScrapeRequest(BaseModel):
    """Request model for scraping financial data."""
    result_type: str = Field(default="LR", description="Type of results to scrape (LR, BP, WP, PT, NT)")
    url: Optional[str] = Field(default=None, description="Optional URL to scrape")
    refresh_connection: bool = Field(default=False, description="Whether to refresh the database connection before scraping")

class ScrapeResponse(BaseModel):
    """Response model for scraping financial data."""
    success: bool
    message: str
    companies_scraped: int
    data: Optional[List[Dict[str, Any]]] = None

class RemoveQuarterRequest(BaseModel):
    """Schema for remove quarter request parameters."""
    quarter: str = Field(..., description="Quarter to remove (Q1, Q2, Q3, Q4)")

class RemoveQuarterResponse(BaseModel):
    """Schema for remove quarter response."""
    success: bool
    message: str
    documents_updated: int = 0 