import requests
import json
import time

# Give the server a moment to start up
print("Waiting for server to start...")
time.sleep(5)

# API base URL
API_BASE_URL = "http://localhost:8000"

def test_endpoint(endpoint, description, method="GET", body=None):
    """Test an API endpoint and print the result"""
    url = f"{API_BASE_URL}{endpoint}"
    print(f"\nTesting {description} at {url}")
    try:
        if method == "GET":
            response = requests.get(url, timeout=5)
        elif method == "POST":
            headers = {"Content-Type": "application/json"}
            response = requests.post(url, headers=headers, json=body, timeout=5)
        else:
            print(f"Unsupported method: {method}")
            return False
            
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            # Try to pretty print JSON response, but only print part of it if it's large
            try:
                data = response.json()
                if isinstance(data, dict) and len(json.dumps(data)) > 1000:
                    # If the response is large, just print the keys
                    if "categories" in data:
                        print(f"Categories: {data['categories']}")
                    else:
                        print(f"Response keys: {list(data.keys())}")
                else:
                    print(f"Response: {json.dumps(data, indent=2)}")
            except Exception as e:
                print(f"Could not parse JSON: {str(e)}")
        else:
            try:
                error_data = response.json()
                print(f"Error response: {json.dumps(error_data, indent=2)}")
            except:
                print(f"Error response (not JSON): {response.text}")
                
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

# Test routes
endpoints = [
    # Standard GET endpoints
    ("/api/documentation", "API documentation endpoint", "GET", None),
    ("/api/v1/quarters", "Quarters endpoint", "GET", None),
    ("/api/v1/market-data", "Market data endpoint", "GET", None),
    
    # Test scraper-specific endpoints
    ("/api/v1/scraper", "Scraper base endpoint (should 404)", "GET", None),
    ("/api/v1/scraper/remove-quarter", "Remove quarter endpoint", "POST", {"quarter": "Q3 FY24-25"})
]

# Run the tests
success_count = 0
for endpoint, description, method, body in endpoints:
    if test_endpoint(endpoint, description, method, body):
        success_count += 1

print(f"\nEndpoint test results: {success_count}/{len(endpoints)} successful") 