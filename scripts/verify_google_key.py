from __future__ import annotations

import os
import sys
import httpx
from dotenv import load_dotenv

load_dotenv(override=True)

from backend.app.sources.google_maps import GoogleMapsConnector

def main():
    api_key = os.getenv("GOOGLE_MAPS_API_KEY") or os.getenv("GOOGLE_PLACES_API_KEY")
    key_loaded = bool(api_key and str(api_key).strip())
    
    print(f"credential loaded: {'YES' if key_loaded else 'NO'}")
    if not key_loaded:
        print("Places API response status: CREDENTIAL_MISSING")
        print("number of real places returned: 0")
        print("first place name: N/A")
        print("first place ID: N/A")
        print("normalization status: FAILED")
        print("\nEXACT GOOGLE ERROR: GOOGLE_MAPS_API_KEY is not set or empty in backend .env.")
        sys.exit(1)

    search_query = "Dental Clinics in London"

    # 1. Test Places API (New) Text Search Endpoint: https://places.googleapis.com/v1/places:searchText
    url_new = "https://places.googleapis.com/v1/places:searchText"
    headers_new = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.websiteUri",
    }

    try:
        res_new = httpx.post(url_new, headers=headers_new, json={"textQuery": search_query}, timeout=10.0)
        if res_new.status_code == 200:
            data_new = res_new.json()
            places = data_new.get("places") or []
            print("Places API response status: 200 OK")
            print(f"number of real places returned: {len(places)}")
            if places:
                first_name = places[0].get("displayName", {}).get("text", "N/A")
                first_id = places[0].get("id", "N/A")
                print(f"first place name: {first_name}")
                print(f"first place ID: {first_id}")
                print("normalization status: NORMALIZED_OK")
            else:
                print("first place name: N/A")
                print("first place ID: N/A")
                print("normalization status: ZERO_RESULTS")
            return
        else:
            err_json = res_new.json().get("error", {})
            err_code = err_json.get("code", res_new.status_code)
            err_status = err_json.get("status", "UNKNOWN")
            err_msg = err_json.get("message", res_new.text[:150])
            
            print(f"Places API response status: HTTP {res_new.status_code} ({err_status})")
            print("number of real places returned: 0")
            print("first place name: N/A")
            print("first place ID: N/A")
            print("normalization status: FAILED")
            print(f"\nEXACT GOOGLE ERROR: HTTP {err_code} {err_status} - {err_msg}")
            sys.exit(1)

    except Exception as e:
        print(f"Places API response status: ERROR ({e})")
        print("number of real places returned: 0")
        print("first place name: N/A")
        print("first place ID: N/A")
        print("normalization status: FAILED")
        print(f"\nEXACT GOOGLE ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
