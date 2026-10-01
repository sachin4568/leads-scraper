import requests

url = "https://nominatim.openstreetmap.org/search"
headers = {"User-Agent": "LeadIntelligencePlatform/1.0 (info@leadsplatform.com)"}
params = {"q": "heating contractor in Fairbanks", "format": "json", "limit": 10, "addressdetails": 1}

resp = requests.get(url, headers=headers, params=params)
print(resp.json())
