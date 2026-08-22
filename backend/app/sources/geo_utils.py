from __future__ import annotations

import logging
import math
from typing import Any

import httpx

from backend.app.security.ssrf_guard import validate_outbound_url

logger = logging.getLogger(__name__)

# Static boundaries cache for common cities
STATIC_CITY_BBOXES: dict[str, list[float]] = {
    "london": [51.28676, 51.69187, -0.510375, 0.3340155],
    "new york": [40.477399, 40.917577, -74.25909, -73.700272],
    "new york, ny": [40.477399, 40.917577, -74.25909, -73.700272],
    "new york city": [40.477399, 40.917577, -74.25909, -73.700272],
    "manchester": [53.3335, 53.593, -2.333, -2.133],
    "birmingham": [52.381, 52.608, -2.033, -1.727],
    "leeds": [53.743, 53.928, -1.683, -1.411],
    "delhi": [28.40, 28.88, 76.84, 77.35],
    "new delhi": [28.40, 28.88, 76.84, 77.35],
}


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates the distance in meters between two coordinates."""
    R = 6371000.0  # Earth's radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


class SubdivisionManager:
    """Handles location geocoding, grid cell subdivision, and cell coordinate/radius calculation."""

    @staticmethod
    def geocode_location(location: str) -> list[float] | None:
        """Resolves location query string to a bounding box: [lat_min, lat_max, lon_min, lon_max]."""
        loc_clean = location.lower().strip()

        # 1. Check static city database cache
        for city, bbox in STATIC_CITY_BBOXES.items():
            if city in loc_clean or loc_clean in city:
                logger.info(f"[Geocoder] Resolved {location} from static city cache.")
                return bbox

        # 2. Try Nominatim Geocoder API
        try:
            url = "https://nominatim.openstreetmap.org/search"
            headers = {"User-Agent": "LeadIntelligencePlatform/1.0 (info@leadsplatform.com)"}
            params = {"q": location, "format": "json", "limit": 1}

            logger.info(f"[Geocoder] Querying Nominatim for location: {location}")
            with httpx.Client(timeout=6.0) as client:
                resp = client.get(url, params=params, headers=headers)
                if resp.status_code == 200:
                    results = resp.json()
                    if results:
                        bbox_str = results[0].get("boundingbox")
                        if bbox_str and len(bbox_str) == 4:
                            resolved_bbox = [
                                float(bbox_str[0]),
                                float(bbox_str[1]),
                                float(bbox_str[2]),
                                float(bbox_str[3]),
                            ]
                            logger.info(f"[Geocoder] Resolved bounding box from Nominatim: {resolved_bbox}")
                            return resolved_bbox
        except Exception as e:
            logger.warning(f"[Geocoder] Nominatim lookup failed: {e}")

        # Fallback to London bounds
        logger.warning(f"[Geocoder] Failed to geocode location '{location}'. Falling back to London bounds.")
        return STATIC_CITY_BBOXES["london"]

    @classmethod
    def subdivide_location(cls, location: str, subdivisions: int = 9) -> list[dict[str, Any]]:
        """Geocodes and subdivides a region into centroid cells with bounding box, coordinates, and radius."""
        bbox = cls.geocode_location(location)
        if not bbox:
            return []

        lat_min, lat_max, lon_min, lon_max = bbox
        grid_size = int(subdivisions**0.5)
        if grid_size < 1:
            grid_size = 1

        lat_step = (lat_max - lat_min) / grid_size
        lon_step = (lon_max - lon_min) / grid_size

        cells = []
        for i in range(grid_size):
            for j in range(grid_size):
                c_lat_min = lat_min + i * lat_step
                c_lat_max = c_lat_min + lat_step
                c_lon_min = lon_min + j * lon_step
                c_lon_max = c_lon_min + lon_step

                # Compute centroid of cell
                c_lat = (c_lat_min + c_lat_max) / 2
                c_lon = (c_lon_min + c_lon_max) / 2

                # Compute radius as distance from centroid to corner of cell
                radius = haversine_distance(c_lat, c_lon, c_lat_max, c_lon_max)

                cells.append(
                    {
                        "bbox": [c_lat_min, c_lat_max, c_lon_min, c_lon_max],
                        "center_lat": c_lat,
                        "center_lon": c_lon,
                        "radius_meters": math.ceil(radius),
                    }
                )
        return cells
