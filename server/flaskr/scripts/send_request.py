import requests

BASE_URL = "http://127.0.0.1:5000"

# POST request
post_response = requests.post(
    f"{BASE_URL}/stocks",
    json={
        "ticker": "SPCX",
        "amount": 5,
        "cost_basis": 100,
        "purchase_date": "2026-07-24",
    }
)
print("POST status:", post_response.status_code)
print("POST body:", post_response.text)

# GET request
response = requests.get(f"{BASE_URL}/stocks")
print("GET status:", response.status_code)
print("GET body:", response.text)
