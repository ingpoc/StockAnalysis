import sys
import os
import asyncio
from fastapi.testclient import TestClient
from src.main import app
from src.api.registry import API_DOCUMENTATION

# Create a test client
client = TestClient(app)

def test_api_documentation():
    """Test the API documentation endpoint"""
    response = client.get("/api/documentation")
    assert response.status_code == 200
    data = response.json()
    print(f"API has {data['endpoint_count']} endpoints across {len(data['categories'])} categories")
    
def test_market_data_endpoint():
    """Test the market data endpoint"""
    print("\nTesting Market Data endpoint:")
    response = client.get("/api/v1/market-data")
    assert response.status_code == 200
    data = response.json()
    print(f"- Quarter: {data.get('quarter')}")
    print(f"- Top performers: {len(data.get('top_performers', []))} stocks")
    print(f"- Worst performers: {len(data.get('worst_performers', []))} stocks")
    print(f"- Latest results: {len(data.get('latest_results', []))} stocks")
    print(f"- All stocks: {len(data.get('all_stocks', []))} stocks")

def test_quarters_endpoint():
    """Test the quarters endpoint"""
    print("\nTesting Quarters endpoint:")
    response = client.get("/api/v1/quarters")
    assert response.status_code == 200
    data = response.json()
    print(f"- Available quarters: {data.get('quarters', [])}")

if __name__ == "__main__":
    # Test the API documentation endpoint
    test_api_documentation()
    
    # Test specific endpoints
    test_market_data_endpoint()
    test_quarters_endpoint() 