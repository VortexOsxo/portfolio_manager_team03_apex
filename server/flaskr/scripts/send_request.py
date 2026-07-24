import requests

BASE_URL = "http://127.0.0.1:5000"

# Buy stocks, without cost_basis and transaction_date
post_response = requests.post(
    f"{BASE_URL}/stocks/buy",
    json={"ticker": "SPCX", "amount": 100}
)
print("POST status:", post_response.status_code)
print("POST body:", post_response.text)

# Buy stocks, with cost_basis and transaction_date
post_response2 = requests.post(
    f"{BASE_URL}/stocks/buy",
    json={"ticker": "NVDA", "amount": 50, "cost_basis": 200, "transaction_date": "2023-01-01"}
)
print("POST status:", post_response2.status_code)
print("POST body:", post_response2.text)

# Sell stocks, with cost_basis and transaction_date
post_response3 = requests.post(
    f"{BASE_URL}/stocks/sell",
    json={"ticker": "NVDA", "amount": 25, "cost_basis": 210, "transaction_date": "2023-01-05"}
)
print("POST status:", post_response3.status_code)
print("POST body:", post_response3.text)

# See holdings
response = requests.get(f"{BASE_URL}/stocks")
print("GET status:", response.status_code)
print("GET body:", response.text)

# See transactions
response2 = requests.get(f"{BASE_URL}/transactions")
print("GET status:", response2.status_code)
print("GET body:", response2.text)