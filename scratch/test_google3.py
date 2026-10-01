import httpx
from backend.app.config import get_settings

settings = get_settings()
api_key = settings.google_maps_api_key

headers = {
    "Content-Type": "application/json",
    "X-Goog-Api-Key": api_key,
    "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress"
}
body = {
    "textQuery": "Medspa in Fairbanks Alaska",
    "pageSize": 5
}

resp = httpx.post("https://places.googleapis.com/v1/places:searchText", headers=headers, json=body)
print(f"Status: {resp.status_code}")
print(resp.text)
