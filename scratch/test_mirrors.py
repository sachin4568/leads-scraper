import httpx
try:
    resp = httpx.get("https://overpass.kumi.systems/api/interpreter", timeout=5.0)
    print(resp.status_code)
except Exception as e:
    print(f"kumi error: {e}")

try:
    resp = httpx.get("https://overpass-api.de/api/interpreter", timeout=5.0)
    print(resp.status_code)
except Exception as e:
    print(f"de error: {e}")
