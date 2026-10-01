import httpx

url = "https://nominatim.openstreetmap.org/search"
headers = {"User-Agent": "LeadIntelligencePlatform/1.0 (info@leadsplatform.com)"}
query_str = "Fairbanks, Alaska, United States, None"
params = {"q": query_str, "format": "json", "limit": 1}

resp = httpx.get(url, params=params, headers=headers)
print(f"Status: {resp.status_code}")
print(resp.json())

query_str2 = "Fairbanks, Alaska, United States"
params2 = {"q": query_str2, "format": "json", "limit": 1}
resp2 = httpx.get(url, params=params2, headers=headers)
print(f"Status 2: {resp2.status_code}")
print(f"Result 2: {len(resp2.json())}")
