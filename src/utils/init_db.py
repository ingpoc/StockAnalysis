from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
import asyncio

async def init_db():
    # Connect to MongoDB
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.stock_data
    
    # Sample data
    sample_stocks = [
        {
            "company_name": "Tech Corp",
            "symbol": "TECH",
            "financial_metrics": [
                {
                    "quarter": "2023-Q4",
                    "net_profit_growth": "25.5%",
                    "revenue_growth": "20.1%",
                    "result_date": "2023-12-15",
                    "recommendation": "Buy",
                    "strengths": ["Strong cash flow", "Market leader"],
                    "weaknesses": ["High competition"],
                    "piotroski_score": 8,
                    "estimates": {"revenue": "High", "profit": "Medium"}
                }
            ]
        },
        {
            "company_name": "Finance Ltd",
            "symbol": "FIN",
            "financial_metrics": [
                {
                    "quarter": "2023-Q4",
                    "net_profit_growth": "15.2%",
                    "revenue_growth": "12.3%",
                    "result_date": "2023-12-10",
                    "recommendation": "Hold",
                    "strengths": ["Stable returns", "Strong balance sheet"],
                    "weaknesses": ["Market volatility"],
                    "piotroski_score": 7,
                    "estimates": {"revenue": "Medium", "profit": "Medium"}
                }
            ]
        }
    ]
    
    # Clear existing data
    await db.detailed_financials.delete_many({})
    
    # Insert sample data
    await db.detailed_financials.insert_many(sample_stocks)
    print("Sample data inserted successfully!")

if __name__ == "__main__":
    asyncio.run(init_db())