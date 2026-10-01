from backend.app.sources.osm_overpass import OSMOverpassConnector
import httpx
connector = OSMOverpassConnector()
bbox = [64.779636, 64.877948, -147.821053, -147.524124]
query = connector._build_overpass_query("Medspa", bbox)
print("Testing without User-Agent")
with httpx.Client(timeout=35.0) as client:
    resp = client.post("https://overpass.kumi.systems/api/interpreter", data={"data": query})
    print(f"Status: {resp.status_code}")
