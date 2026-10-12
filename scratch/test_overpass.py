import httpx

q = """[out:json][timeout:25];
(
  node["craft"="hvac"](40.7,-74.0,40.8,-73.9);
);
out center;"""

for ep in [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]:
    for ua in ["python-httpx/0.27.0", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"]:
        try:
            r = httpx.post(ep, data={"data": q}, headers={"User-Agent": ua, "Content-Type": "application/x-www-form-urlencoded"}, timeout=15)
            print(f"Endpoint: {ep} | UA: {ua[:20]}... | Status: {r.status_code}")
            if r.status_code == 200:
                print("   Elements found:", len(r.json().get("elements", [])))
        except Exception as e:
            print(f"Endpoint: {ep} | UA: {ua[:20]}... | Error: {e}")
