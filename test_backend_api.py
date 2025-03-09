import requests
import json

# API base URL
API_BASE_URL = "http://localhost:8000/api/v1"

def test_api_documentation():
    """Test the API documentation endpoint"""
    response = requests.get("http://localhost:8000/api/documentation")
    if response.status_code == 200:
        data = response.json()
        print(f"API has {data['endpoint_count']} endpoints across {len(data['categories'])} categories")
        print("Categories:", data['categories'])
        return True
    else:
        print(f"Error accessing API documentation: {response.status_code}")
        return False

def test_market_data_endpoint():
    """Test the market data endpoint"""
    print("\nTesting Market Data endpoint:")
    response = requests.get(f"{API_BASE_URL}/market-data")
    if response.status_code == 200:
        data = response.json()
        print(f"- Quarter: {data.get('quarter')}")
        print(f"- Top performers: {len(data.get('top_performers', []))} stocks")
        print(f"- Worst performers: {len(data.get('worst_performers', []))} stocks")
        print(f"- Latest results: {len(data.get('latest_results', []))} stocks")
        print(f"- All stocks: {len(data.get('all_stocks', []))} stocks")
        return True
    else:
        print(f"Error accessing market data endpoint: {response.status_code}")
        return False

def test_quarters_endpoint():
    """Test the quarters endpoint"""
    print("\nTesting Quarters endpoint:")
    response = requests.get(f"{API_BASE_URL}/quarters")
    if response.status_code == 200:
        data = response.json()
        print(f"- Available quarters: {data.get('quarters', [])}")
        return True
    else:
        print(f"Error accessing quarters endpoint: {response.status_code}")
        return False

def test_scraper_endpoints():
    """Test the scraper endpoints through our registry structure"""
    print("\nTesting POST endpoints via API structure:")
    
    # This is just a check to verify the endpoint structure, not a real execution
    # In a real test, we would make the actual POST request
    try:
        from src.api.registry import API_DOCUMENTATION
        scraper_endpoints = API_DOCUMENTATION.get("Scraper", [])
        for endpoint in scraper_endpoints:
            print(f"- {endpoint['method']} {endpoint['path']}: {endpoint['description']}")
        return True
    except ImportError:
        print("Could not import API_DOCUMENTATION from registry")
        return False

if __name__ == "__main__":
    # Make sure the backend server is running before executing these tests
    print("Testing backend API using consolidated registry approach...")
    print("-" * 60)
    
    # Test the API documentation endpoint
    test_api_documentation()
    
    # Test specific endpoints
    test_market_data_endpoint()
    test_quarters_endpoint()
    test_scraper_endpoints()
    
    print("-" * 60)
    print("Tests completed!") 