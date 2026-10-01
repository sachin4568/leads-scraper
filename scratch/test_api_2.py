import requests

url = "http://localhost:8000/api/v1/scrape-jobs"
payload = {
    "niche": "Medspa",
    "city": "Fairbanks",
    "region": "Alaska",
    "country": "United States",
    "target_lead_count": 5,
    "service": "website_dev"
}
response = requests.post(url, json=payload)
print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")
