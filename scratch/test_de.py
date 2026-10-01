import requests

query = """[out:json][timeout:15];
(
  nwr["shop"="beauty"](64.77,-147.82,64.87,-147.52);
);
out center;"""

headers = {"User-Agent": "curl/7.68.0", "Content-Type": "application/x-www-form-urlencoded"}
print("Querying Overpass DE raw...")
try:
    resp = requests.post("https://overpass-api.de/api/interpreter", data=query, headers=headers, timeout=20)
    print(f"Status: {resp.status_code}")
    print(resp.text[:200])
except Exception as e:
    print(f"Error: {e}")
