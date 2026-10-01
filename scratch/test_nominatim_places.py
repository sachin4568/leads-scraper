import requests

url = "https://nominatim.openstreetmap.org/search"
headers = {"User-Agent": "LeadIntelligencePlatform/1.0 (info@leadsplatform.com)"}
params = {"q": "beauty in Fairbanks", "format": "json", "limit": 10, "addressdetails": 1}

print("Querying Nominatim...")
resp = requests.get(url, headers=headers, params=params)
print(f"Status: {resp.status_code}")
for item in resp.json():
    print(item.get("display_name"))
