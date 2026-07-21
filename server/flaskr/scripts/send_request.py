import requests

BASE_URL = "http://127.0.0.1:5000"

# POST request
post_response = requests.post(
    f"{BASE_URL}/stocks",
    json={"symbol": "SPCX"}
)
print("POST status:", post_response.status_code)
print("POST body:", post_response.text)

# GET request
response = requests.get(f"{BASE_URL}/stocks")
print("GET status:", response.status_code)
print("GET body:", response.text)
