import requests

query = """[out:json][timeout:15];
(
  nwr["shop"="beauty"](64.77,-147.82,64.87,-147.52);
);
out center;"""

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0"}
print("Querying Overpass DE...")
try:
    resp = requests.post("https://overpass-api.de/api/interpreter", data=query.encode('utf-8'), headers=headers, timeout=20)
    print(f"Status: {resp.status_code}")
except Exception as e:
    print(f"Error: {e}")
