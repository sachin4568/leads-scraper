from backend.app.config import get_settings
from backend.app.sources.google_maps import GoogleMapsConnector

settings = get_settings()
print(f"Key configured: {bool(settings.google_maps_api_key)}")

connector = GoogleMapsConnector(api_key=settings.google_maps_api_key.get_secret_value() if settings.google_maps_api_key else None)
print(f"Connector key present: {bool(connector.api_key)}")

try:
    print("Trying NEW API...")
    res = connector._search_places_new("Medspa in Fairbanks Alaska", limit=5, pagination_state={})
    print(f"NEW API returned {len(res)} results.")
except Exception as e:
    print(f"NEW API Exception: {e}")

try:
    print("Trying legacy search_leads...")
    res = connector.search_leads("Medspa", "Fairbanks Alaska", limit=5, pagination_state={})
    print(f"search_leads returned {len(res)} results.")
except Exception as e:
    print(f"search_leads Exception: {e}")

