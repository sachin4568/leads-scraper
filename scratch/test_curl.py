import requests

query = """[out:json][timeout:15];
(
  nwr["shop"="beauty"](64.77,-147.82,64.87,-147.52);
);
out center;"""

headers = {"User-Agent": "curl/7.68.0"}
print("Querying Overpass Kumi...")
try:
    resp = requests.post("https://overpass.kumi.systems/api/interpreter", data={"data": query}, headers=headers, timeout=20)
    print(f"Status: {resp.status_code}")
except Exception as e:
    print(f"Error: {e}")
