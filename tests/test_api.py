import requests
import json
import os
import pandas as pd
from io import StringIO
from datetime import datetime

# Base URL for all API requests
BASE_URL = "http://localhost:8000/api/v1"

# Note: These tests use symbols that are known to exist in the database.
# Using non-existent symbols will result in 404 or 500 errors.
# Current valid symbols include: "JUBLPHARMA", "SHAKTIPUMP"

# Portfolio API Tests

def test_get_holdings():
    """Test the GET /portfolio/holdings endpoint"""
    print("\n=== Testing GET /portfolio/holdings ===")
    
    try:
        response = requests.get(f"{BASE_URL}/portfolio/holdings")
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            holdings = response.json()
            print(f"Success! Retrieved {len(holdings)} holdings")
            if holdings:
                print(f"First holding: {json.dumps(holdings[0], indent=2)}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {str(e)}")

def test_add_holding():
    """Test the POST /portfolio/holdings endpoint"""
    print("\n=== Testing POST /portfolio/holdings ===")
    
    # Sample holding data
    new_holding = {
        "symbol": "TEST",
        "company_name": "Test Company Inc.",
        "quantity": 100,
        "average_price": 123.45,
        "purchase_date": "2024-03-01T00:00:00",
        "notes": "Test holding for API testing"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/portfolio/holdings",
            json=new_holding
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code in (200, 201):
            created_holding = response.json()
            print(f"Success! Created holding with ID: {created_holding.get('_id')}")
            print(json.dumps(created_holding, indent=2))
            return created_holding
        else:
            print(f"Error: {response.text}")
            return None
    except Exception as e:
        print(f"Exception: {str(e)}")
        return None

def test_update_holding(holding_id=None):
    """Test the PUT /portfolio/holdings/{id} endpoint"""
    if not holding_id:
        print("\nSkipping update test - no holding ID provided")
        return
    
    print(f"\n=== Testing PUT /portfolio/holdings/{holding_id} ===")
    
    # Updated holding data
    updated_holding = {
        "symbol": "TEST",
        "company_name": "Test Company Inc. (Updated)",
        "quantity": 150,
        "average_price": 130.75,
        "purchase_date": "2024-03-01T00:00:00",
        "notes": "Updated test holding"
    }
    
    try:
        response = requests.put(
            f"{BASE_URL}/portfolio/holdings/{holding_id}",
            json=updated_holding
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            updated = response.json()
            print("Success! Holding updated:")
            print(json.dumps(updated, indent=2))
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {str(e)}")

def test_delete_holding(holding_id=None):
    """Test the DELETE /portfolio/holdings/{id} endpoint"""
    if not holding_id:
        print("\nSkipping delete test - no holding ID provided")
        return
    
    print(f"\n=== Testing DELETE /portfolio/holdings/{holding_id} ===")
    
    try:
        response = requests.delete(f"{BASE_URL}/portfolio/holdings/{holding_id}")
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Success! {result.get('message', 'Holding deleted')}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {str(e)}")

def test_import_holdings_from_csv():
    """Test the POST /portfolio/holdings/import endpoint"""
    print("\n=== Testing POST /portfolio/holdings/import ===")
    
    # Create a test CSV with sample data
    csv_data = """symbol,company_name,quantity,average_price,purchase_date,notes
AAPL,Apple Inc.,15,175.25,2025-03-01T00:00:00,Imported via CSV test
MSFT,Microsoft Corp,10,400.50,2025-03-01T00:00:00,Imported via CSV test
GOOGL,Alphabet Inc.,5,155.75,2025-03-01T00:00:00,Imported via CSV test
"""
    
    # Save as temporary file
    temp_file_path = "temp_holdings.csv"
    with open(temp_file_path, "w") as f:
        f.write(csv_data)
    
    try:
        # Open the file and send it
        with open(temp_file_path, "rb") as f:
            files = {"file": ("holdings.csv", f, "text/csv")}
            response = requests.post(
                f"{BASE_URL}/portfolio/holdings/import",
                files=files
            )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            imported_holdings = response.json()
            print(f"Success! Imported {len(imported_holdings)} holdings")
            print("First imported holding:")
            print(json.dumps(imported_holdings[0], indent=2))
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {str(e)}")
    finally:
        # Clean up temporary file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            print(f"Removed temporary file: {temp_file_path}")

# Market Data API Tests

def test_get_market_data():
    """Test the GET /market-data endpoint"""
    print("\n=== Testing GET /market-data ===")
    
    try:
        response = requests.get(f"{BASE_URL}/market-data")
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("Success! Received market data overview")
            print(f"Quarter: {data.get('quarter')}")
            print(f"Last Updated: {data.get('last_updated')}")
            print(f"Top Performers Count: {len(data.get('top_performers', []))}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {str(e)}")

def test_get_quarters():
    """Test the GET /quarters endpoint"""
    print("\n=== Testing GET /quarters ===")
    
    try:
        response = requests.get(f"{BASE_URL}/quarters")
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            quarters = data.get('quarters', [])
            print(f"Success! Retrieved {len(quarters)} quarters")
            if quarters:
                print(f"Available quarters: {', '.join(quarters[:5])}")
                if len(quarters) > 5:
                    print(f"...and {len(quarters) - 5} more")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {str(e)}")

# Stock Data API Tests

def test_get_stock_details():
    """Test the GET /stock/{symbol} endpoint"""
    # Use a symbol that exists in the database to avoid 404/500 errors
    symbol = "JUBLPHARMA"  # Valid symbol in the database
    print(f"\n=== Testing GET /stock/{symbol} ===")
    
    try:
        response = requests.get(f"{BASE_URL}/stock/{symbol}")
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Success! Retrieved details for {symbol}")
            stock_data = data.get('stock', {})
            print(f"Company Name: {stock_data.get('company_name')}")
            print(f"Symbol: {stock_data.get('symbol')}")
            print(f"Last Updated: {stock_data.get('timestamp')}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {str(e)}")

# AI Analysis API Tests

def test_get_analysis_history():
    """Test the GET /stock/{symbol}/analysis-history endpoint"""
    # Use a symbol that has analysis data to avoid 404 errors
    symbol = "SHAKTIPUMP"  # Valid symbol with analysis history
    print(f"\n=== Testing GET /stock/{symbol}/analysis-history ===")
    
    try:
        response = requests.get(f"{BASE_URL}/stock/{symbol}/analysis-history")
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            analyses = data.get('analyses', [])
            print(f"Success! Retrieved {len(analyses)} analyses for {symbol}")
            if analyses:
                print("Most recent analysis:")
                print(json.dumps(analyses[0], indent=2))
                return analyses[0].get('id')
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {str(e)}")
    return None

def test_get_analysis_content(analysis_id=None):
    """Test the GET /analysis/{analysis_id} endpoint"""
    if not analysis_id:
        print("\nSkipping analysis content test - no analysis ID provided")
        return
    
    print(f"\n=== Testing GET /analysis/{analysis_id} ===")
    
    try:
        response = requests.get(f"{BASE_URL}/analysis/{analysis_id}")
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            analysis = response.json()
            print(f"Success! Retrieved analysis content")
            print(f"Symbol: {analysis.get('symbol')}")
            print(f"Company: {analysis.get('company_name')}")
            print(f"Recommendation: {analysis.get('recommendation')}")
            print(f"Timestamp: {analysis.get('timestamp')}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {str(e)}")

def test_refresh_analysis():
    """Test the POST /stock/{symbol}/refresh-analysis endpoint"""
    # Use a symbol that exists in the database to avoid 404/500 errors
    symbol = "JUBLPHARMA"  # Valid symbol in the database
    print(f"\n=== Testing POST /stock/{symbol}/refresh-analysis ===")
    
    try:
        response = requests.post(f"{BASE_URL}/stock/{symbol}/refresh-analysis")
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Success! Generated new analysis for {symbol}")
            print(f"Analysis ID: {data.get('id')}")
            print(f"Recommendation: {data.get('recommendation')}")
            print(f"Timestamp: {data.get('timestamp')}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {str(e)}")

# Run tests
if __name__ == "__main__":
    print("Running API Tests...")
    
    # Portfolio tests
    test_get_holdings()
    new_holding = test_add_holding()
    holding_id = new_holding.get('_id') if new_holding else None
    test_update_holding(holding_id)
    test_delete_holding(holding_id)
    test_import_holdings_from_csv()
    
    # Market data tests
    test_get_market_data()
    test_get_quarters()
    
    # Stock data tests
    test_get_stock_details()
    
    # AI analysis tests
    analysis_id = test_get_analysis_history()
    test_get_analysis_content(analysis_id)
    test_refresh_analysis()
    
    print("\nAPI Testing Complete!") 