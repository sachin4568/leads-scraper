from backend.app.sources.osm_overpass import OSMOverpassConnector
import httpx
connector = OSMOverpassConnector()
bbox = [64.779636, 64.877948, -147.821053, -147.524124]
query = connector._build_overpass_query("Medspa", bbox)
print("Testing with User-Agent python-httpx/0.27.0")
with httpx.Client(timeout=35.0) as client:
    resp = client.post("https://overpass.kumi.systems/api/interpreter", data={"data": query}, headers={"User-Agent": "python-httpx/0.27.0"})
    print(f"Status: {resp.status_code}")
