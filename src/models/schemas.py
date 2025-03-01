from pydantic import BaseModel, Field, GetJsonSchemaHandler
from typing import List, Optional, Dict, Any, Annotated, Union
from datetime import datetime
from bson import ObjectId
from pydantic_core import CoreSchema, core_schema
from pydantic.json_schema import JsonSchemaValue

class PyObjectId(str):
    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: type[Any],
        _handler: GetJsonSchemaHandler,
    ) -> CoreSchema:
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.union_schema([
                core_schema.str_schema(),
                core_schema.is_instance_schema(ObjectId),
            ]),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda x: str(x) if isinstance(x, ObjectId) else x
            ),
        )

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

class RisksOpportunities(BaseModel):
    risks: List[str]
    opportunities: List[str]

class AnalysisContent(BaseModel):
    sentiment_summary: str
    key_factors: List[str]
    news_impact: List[str]
    risks_opportunities: RisksOpportunities
    forward_outlook: str

class AIAnalysis(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    company_name: str
    symbol: str
    analysis: Union[str, AnalysisContent]  # Allow both string and structured format
    sentiment: Dict[str, Any] = Field(default_factory=lambda: {"score": 0.5, "label": "Neutral"})
    technical_indicators: Dict[str, Any] = Field(default_factory=dict)
    fundamental_analysis: Dict[str, Any] = Field(default_factory=dict)
    recommendation: str = "No recommendation"
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        populate_by_name = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
        arbitrary_types_allowed = True

    @classmethod
    def from_mongo(cls, data: dict):
        """Convert MongoDB document to AIAnalysis model with backward compatibility"""
        if not data:
            return None
            
        if "_id" in data:
            data["id"] = str(data["_id"])
            
        # Handle old format conversion
        if isinstance(data.get("analysis"), str):
            analysis_text = data["analysis"]
            
            # Clean up the text
            analysis_text = analysis_text.replace('*', '')  # Remove asterisks
            
            # Split by sections and clean up
            sections = [s.strip() for s in analysis_text.split('\n') if s.strip()]
            
            # Initialize structured sections
            sentiment_summary = ""
            key_factors = []
            news_impact = []
            risks = []
            opportunities = []
            forward_outlook = ""
            
            current_section = None
            
            # Parse the sections
            for line in sections:
                line = line.strip()
                if not line:
                    continue
                    
                # Check for section headers
                lower_line = line.lower()
                if "fundamental metrics" in lower_line:
                    current_section = "fundamental"
                    continue
                elif "recent news" in lower_line:
                    current_section = "news"
                    continue
                elif "recommendation" in lower_line:
                    current_section = "recommendation"
                    continue
                elif "risks" in lower_line:
                    current_section = "risks"
                    continue
                elif "opportunities" in lower_line:
                    current_section = "opportunities"
                    continue
                
                # Clean up the line
                cleaned_line = line.strip(':-. ')
                if not cleaned_line:
                    continue
                
                # Add content to appropriate section
                if current_section == "fundamental":
                    key_factors.append(cleaned_line)
                elif current_section == "news":
                    news_impact.append(cleaned_line)
                elif current_section == "recommendation":
                    forward_outlook = cleaned_line
                elif current_section == "risks":
                    risks.append(cleaned_line)
                elif current_section == "opportunities":
                    opportunities.append(cleaned_line)
                elif not current_section and cleaned_line:  # Unclassified content goes to key factors
                    key_factors.append(cleaned_line)
            
            data["analysis"] = {
                "sentiment_summary": sentiment_summary or "Analysis based on historical data",
                "key_factors": [f for f in key_factors if f],  # Filter out empty strings
                "news_impact": [n for n in news_impact if n],  # Filter out empty strings
                "risks_opportunities": {
                    "risks": risks,
                    "opportunities": opportunities
                },
                "forward_outlook": forward_outlook
            }
        elif isinstance(data.get("analysis"), dict):
            # Handle case where analysis is a dict but risks_opportunities is a list
            analysis = data["analysis"]
            if isinstance(analysis.get("risks_opportunities"), list):
                analysis["risks_opportunities"] = {
                    "risks": analysis["risks_opportunities"],
                    "opportunities": []
                }
            elif not isinstance(analysis.get("risks_opportunities"), dict):
                analysis["risks_opportunities"] = {
                    "risks": [],
                    "opportunities": []
                }
            
        return cls.model_validate(data)

class AIAnalysisHistory(BaseModel):
    analyses: List[AIAnalysis] = Field(default_factory=list)

class AIAnalysisRequest(BaseModel):
    symbol: str
    timeframe: Optional[str] = 'short_term'
    include_technicals: bool = True
    include_fundamentals: bool = True

class AIAnalysisResponse(BaseModel):
    id: str
    content: Union[str, Dict[str, Any]]  # Allow both string and structured format
    timestamp: datetime
    recommendation: str

    class Config:
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }

class Holding(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    symbol: str
    company_name: str
    quantity: int
    average_price: float
    purchase_date: Optional[datetime] = None
    notes: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    asset_type: Optional[str] = "stock"  # 'stock', 'crypto', or 'mutual_fund'
    folio_number: Optional[str] = None  # For mutual funds

    class Config:
        populate_by_name = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
        arbitrary_types_allowed = True

class HoldingsList(BaseModel):
    holdings: List[Holding] = Field(default_factory=list)
    
class EnrichedHolding(Holding):
    """Holding with current market price data"""
    current_price: Optional[float] = None
    current_value: Optional[float] = None
    gain_loss: Optional[float] = None
    gain_loss_percentage: Optional[float] = None
    has_error: bool = False
    error_message: Optional[str] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
        arbitrary_types_allowed = True