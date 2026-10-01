import requests
query = """[out:json][timeout:25];
(
  nwr["shop"="beauty"](64.77,-147.82,64.87,-147.52);
  nwr["leisure"="spa"](64.77,-147.82,64.87,-147.52);
);
out center;"""
print("Querying Overpass DE...")
resp = requests.post("https://overpass-api.de/api/interpreter", data={"data": query})
print(f"Status: {resp.status_code}")
print(resp.text[:200])
