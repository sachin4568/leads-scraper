import requests
url = "https://nominatim.openstreetmap.org/search"
headers = {"User-Agent": "LeadIntelligencePlatform/1.0 (info@leadsplatform.com)"}
params = {"q": "Medspa in New York", "format": "json", "limit": 5, "addressdetails": 1}
print(requests.get(url, headers=headers, params=params).json())
