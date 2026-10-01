from backend.app.sources.geo_utils import SubdivisionManager
bbox = SubdivisionManager.geocode_location("Fairbanks, Alaska, United States")
print(f"Bbox: {bbox}")
