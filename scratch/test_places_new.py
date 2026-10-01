from backend.app.config import get_settings
import requests

API_KEY = get_settings().google_maps_api_key
print(f"Key: {API_KEY[:5]}...")

url = "https://places.googleapis.com/v1/places:searchText"
headers = {
    "X-Goog-Api-Key": API_KEY,
    "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.websiteUri,places.location,places.primaryType",
    "Content-Type": "application/json"
}
payload = {
    "textQuery": "Medspa in Fairbanks, Alaska",
    "maxResultCount": 10
}
resp = requests.post(url, headers=headers, json=payload)
print(resp.status_code)
print(resp.text[:500])
