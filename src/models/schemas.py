from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class FinancialMetric(BaseModel):
    market_cap: Optional[str] = ""
    face_value: Optional[str] = ""
    book_value: Optional[str] = ""
    dividend_yield: Optional[str] = ""
    ttm_eps: Optional[str] = ""
    ttm_pe: Optional[str] = ""
    pb_ratio: Optional[str] = ""
    sector_pe: Optional[str] = ""
    piotroski_score: Optional[str] = ""
    revenue_growth_3yr_cagr: Optional[str] = ""
    net_profit_growth_3yr_cagr: Optional[str] = ""
    operating_profit_growth_3yr_cagr: Optional[str] = ""
    strengths: Optional[str] = ""
    weaknesses: Optional[str] = ""
    technicals_trend: Optional[str] = ""
    fundamental_insights: Optional[str] = ""
    fundamental_insights_description: Optional[str] = ""
    revenue: Optional[str] = ""
    gross_profit: Optional[str] = ""
    net_profit: Optional[str] = ""
    net_profit_growth: Optional[str] = "0%"
    result_date: Optional[str] = None
    gross_profit_growth: Optional[str] = ""
    revenue_growth: Optional[str] = ""
    quarter: Optional[str] = None
    report_type: Optional[str] = ""
    cmp: Optional[str] = ""
    estimates: Optional[str] = ""

    class Config:
        extra = "allow"  # Allow extra fields

class StockData(BaseModel):
    company_name: str
    symbol: str
    financial_metrics: List[FinancialMetric]
    timestamp: Optional[datetime] = Field(default_factory=datetime.now)

    class Config:
        extra = "allow"

class StockResponse(BaseModel):
    stock: StockData
    formatted_metrics: Dict[str, Any]

class MarketOverview(BaseModel):
    quarter: Optional[str] = None  # Made quarter optional
    top_performers: List[Dict[str, Any]] = Field(default_factory=list)
    worst_performers: List[Dict[str, Any]] = Field(default_factory=list)
    latest_results: List[Dict[str, Any]] = Field(default_factory=list)
    all_stocks: List[Dict[str, Any]] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.now)

class FormattedMetric(BaseModel):
    value: float
    display: str
    trend: Optional[str] = None
    description: Optional[str] = None

class AnalysisSentiment(BaseModel):
    score: float
    label: str

class AIAnalysis(BaseModel):
    id: str = Field(alias='_id')
    company_name: str
    symbol: str
    analysis: str
    recommendation: str
    sentiment: AnalysisSentiment
    technical_indicators: Dict[str, Any] = Field(default_factory=dict)
    fundamental_analysis: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        populate_by_name = True
        extra = "allow"

class AIAnalysisHistory(BaseModel):
    analyses: List[AIAnalysis] = Field(default_factory=list)

class AIAnalysisRequest(BaseModel):
    symbol: str
    timeframe: Optional[str] = 'short_term'
    include_technicals: bool = True
    include_fundamentals: bool = True

class AIAnalysisResponse(BaseModel):
    id: str
    content: str
    timestamp: datetime
    recommendation: str