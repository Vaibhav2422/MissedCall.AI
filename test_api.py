import requests
import json

# Test the API endpoints
BASE_URL = "http://127.0.0.1:8000"

def test_explain_endpoint():
    """Test the explain endpoint with various scenarios"""
    
    # Test case 1: Strong context (bank number with SMS)
    print("Testing strong context scenario...")
    data1 = {
        "phone_number": "8888888888",
        "caller_label": "Bank",
        "user_language": "hi"
    }
    
    response1 = requests.post(f"{BASE_URL}/explain", json=data1)
    print(f"Status: {response1.status_code}")
    print(f"Response: {json.dumps(response1.json(), indent=2)}")
    print("-" * 50)
    
    # Test case 2: Weak context (repeated calls)
    print("Testing weak context scenario...")
    data2 = {
        "phone_number": "7777777777", 
        "call_frequency": 3,
        "user_language": "en"
    }
    
    response2 = requests.post(f"{BASE_URL}/explain", json=data2)
    print(f"Status: {response2.status_code}")
    print(f"Response: {json.dumps(response2.json(), indent=2)}")
    print("-" * 50)
    
    # Test case 3: No context (unknown number)
    print("Testing no context scenario...")
    data3 = {
        "phone_number": "1111111111",
        "user_language": "en"
    }
    
    response3 = requests.post(f"{BASE_URL}/explain", json=data3)
    print(f"Status: {response3.status_code}")
    print(f"Response: {json.dumps(response3.json(), indent=2)}")
    print("-" * 50)

def test_health_check():
    """Test the health check endpoint"""
    print("Testing health check...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Health status: {response.json()}")
    print("-" * 50)

if __name__ == "__main__":
    print("Running API tests...")
    try:
        test_health_check()
        test_explain_endpoint()
        print("Tests completed!")
    except Exception as e:
        print(f"Error running tests: {e}")
        print("Make sure the backend server is running on http://127.0.0.1:8000")
