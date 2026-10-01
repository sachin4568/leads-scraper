from backend.app.sources.osm_overpass import OSMOverpassConnector
from backend.app.sources.geo_utils import SubdivisionManager
import httpx

connector = OSMOverpassConnector()
bbox = [64.779636, 64.877948, -147.821053, -147.524124]

query = connector._build_overpass_query("Medspa", bbox)
print("Testing query with Fairbanks bbox...")
with httpx.Client(timeout=35.0) as client:
    try:
        resp = client.post("https://overpass-api.de/api/interpreter", data=query)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            print(f"Elements: {len(resp.json().get('elements', []))}")
        else:
            print(resp.text)
    except Exception as e:
        print(f"Error: {e}")
