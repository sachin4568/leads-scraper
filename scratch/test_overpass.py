import requests
import json
query = """[out:json][timeout:15];
(
  nwr["shop"="beauty"](64.77,-147.82,64.87,-147.52);
);
out center;"""
print("Querying Overpass DE...")
try:
    resp = requests.post("https://overpass-api.de/api/interpreter", data={"data": query}, timeout=20)
    print(f"Status: {resp.status_code}")
    print(resp.text[:200])
except Exception as e:
    print(f"Error: {e}")
