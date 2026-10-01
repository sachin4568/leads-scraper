
import httpx
query = """[out:json][timeout:25];
(
  node["name"~"plumber", i](51.4,-0.2,51.6,0.2);
  way["name"~"plumber", i](51.4,-0.2,51.6,0.2);
);
out center;"""
headers = {"User-Agent": "Antigravity/1.0", "Accept": "*/*", "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
r = httpx.post("https://overpass-api.de/api/interpreter", data={"data": query}, headers=headers)
print(r.status_code)
print(len(r.text))

