from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from backend.app.config import get_settings
from backend.app.security.ssrf_guard import validate_outbound_url
from backend.app.sources.base import NormalizedLeadRecord, SourceConnector
from backend.app.sources.geo_utils import SubdivisionManager

logger = logging.getLogger(__name__)

# Configurable category-to-OSM mapping
DEFAULT_CATEGORY_MAPPING: dict[str, tuple[str, str]] = {
    "restaurant": ("amenity", "restaurant"),
    "cafe": ("amenity", "cafe"),
    "bar": ("amenity", "bar"),
    "bakery": ("shop", "bakery"),
    "hotel": ("tourism", "hotel"),
    "dental clinic": ("amenity", "dentist"),
    "dentist": ("amenity", "dentist"),
    "dental": ("amenity", "dentist"),
    "plumber": ("craft", "plumber"),
    "plumbing": ("craft", "plumber"),
    "hvac": ("craft", "hvac"),
    "roofing": ("craft", "roofer"),
    "electrician": ("craft", "electrician"),
}


class OSMOverpassConnector(SourceConnector):
    """Lead discovery connector using OpenStreetMap (OSM) via the Overpass API."""

    def __init__(
        self,
        endpoint_url: str | None = None,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 60.0,
    ) -> None:
        super().__init__(
            failure_threshold=failure_threshold,
            recovery_timeout_seconds=recovery_timeout_seconds,
        )
        self.endpoint_url = endpoint_url or getattr(get_settings(), "overpass_api_url", "https://overpass-api.de/api/interpreter")
        
        # OSM-specific discovery metrics
        self.metrics: dict[str, Any] = {
            "total_osm_results": 0,
            "unique_businesses_discovered": 0,
            "duplicates": 0,
            "identity_matches": 0,
            "new_canonical_leads": 0,
            "records_containing_website": 0,
            "records_containing_phone": 0,
            "records_containing_address": 0,
            "records_containing_email": 0,
            "query_failures": 0,
            "total_response_time": 0.0,
            "successful_queries": 0,
        }

    @property
    def source_name(self) -> str:
        return "osm_overpass"

    def _geocode_location(self, location: str) -> list[float] | None:
        return SubdivisionManager.geocode_location(location)

    def _subdivide_bbox(self, bbox: list[float], subdivisions: int = 9) -> list[list[float]]:
        grid_size = int(subdivisions**0.5)
        lat_min, lat_max, lon_min, lon_max = bbox
        lat_step = (lat_max - lat_min) / grid_size
        lon_step = (lon_max - lon_min) / grid_size
        cells = []
        for i in range(grid_size):
            for j in range(grid_size):
                cells.append([
                    lat_min + i * lat_step,
                    lat_min + (i + 1) * lat_step,
                    lon_min + j * lon_step,
                    lon_min + (j + 1) * lon_step
                ])
        return cells

    def _build_overpass_query(self, category: str, bbox: list[float]) -> str:
        """Builds a secure and sanitized Overpass QL query using resolved category tags and bounds."""
        cat_key = category.lower().strip()
        mapping = DEFAULT_CATEGORY_MAPPING.get(cat_key)
        
        if not mapping:
            # Check if keyword contains parts we map
            for key, val in DEFAULT_CATEGORY_MAPPING.items():
                if key in cat_key or cat_key in key:
                    mapping = val
                    break
        
        if not mapping:
            logger.error(f"[OSM Overpass] Unsupported niche category requested: {category}")
            raise ValueError("UNSUPPORTED_CATEGORY")

        tag_key, tag_val = mapping
        lat_min, lat_max, lon_min, lon_max = bbox

        # Sanitize coordinate formats to floats to avoid injection hazards
        lat_min = float(lat_min)
        lat_max = float(lat_max)
        lon_min = float(lon_min)
        lon_max = float(lon_max)

        query = (
            f"[out:json][timeout:25];\n"
            f"(\n"
            f'  node["{tag_key}"="{tag_val}"]({lat_min},{lon_min},{lat_max},{lon_max});\n'
            f'  way["{tag_key}"="{tag_val}"]({lat_min},{lon_min},{lat_max},{lon_max});\n'
            f'  relation["{tag_key}"="{tag_val}"]({lat_min},{lon_min},{lat_max},{lon_max});\n'
            f");\n"
            f"out center;"
        )
        return query

    def _execute_query(self, query: str) -> dict[str, Any]:
        """Performs request to Overpass API with timeouts, retry logic, and exponential backoff."""
        max_retries = 3
        backoff_factor = 2.0

        try:
            validated_url = validate_outbound_url(self.endpoint_url)
        except Exception:
            validated_url = self.endpoint_url

        for attempt in range(max_retries):
            # Check rate limiter
            if not self.acquire_rate_limit():
                logger.warning("[OSM Overpass] Rate limit hit. Delaying request call.")
                time.sleep(1.0)

            try:
                start_time = time.time()
                with httpx.Client(timeout=15.0) as client:
                    logger.info(f"[OSM Overpass] Sending request. Attempt {attempt + 1}/{max_retries}.")
                    response = client.post(validated_url, data={"data": query})
                    
                    if response.status_code == 429:
                        logger.warning("[OSM Overpass] Received HTTP 429. Backing off.")
                        time.sleep(backoff_factor * (attempt + 1))
                        continue
                    elif response.status_code >= 500:
                        logger.warning(f"[OSM Overpass] Received HTTP {response.status_code}. Backing off.")
                        time.sleep(backoff_factor * (attempt + 1))
                        continue

                    response.raise_for_status()
                    
                    elapsed = time.time() - start_time
                    self.metrics["total_response_time"] += elapsed
                    self.metrics["successful_queries"] += 1

                    try:
                        data = response.json()
                        return data
                    except Exception as json_err:
                        logger.error(f"[OSM Overpass] Failed to parse JSON body: {json_err}")
                        raise ValueError("PROVIDER_UNAVAILABLE")

            except httpx.HTTPStatusError as http_err:
                logger.error(f"[OSM Overpass] HTTP error occurred: {http_err}")
                if http_err.response.status_code == 400:
                    raise ValueError("INVALID_QUERY")
                time.sleep(backoff_factor * (attempt + 1))
            except httpx.RequestError as req_err:
                logger.error(f"[OSM Overpass] Connection request error: {req_err}")
                time.sleep(backoff_factor * (attempt + 1))

        self.metrics["query_failures"] += 1
        raise ValueError("PROVIDER_UNAVAILABLE")

    def _parse_element(self, element: dict[str, Any]) -> NormalizedLeadRecord | None:
        """Parses a raw OSM element (node/way/relation) into a NormalizedLeadRecord."""
        tags = element.get("tags") or {}
        business_name = tags.get("name") or tags.get("brand") or tags.get("operator")
        if not business_name:
            return None

        # Build address
        street = tags.get("addr:street")
        housenumber = tags.get("addr:housenumber")
        address_parts = [p for p in [housenumber, street] if p]
        address = " ".join(address_parts) if address_parts else None

        city = tags.get("addr:city")
        state = tags.get("addr:state")
        country = tags.get("addr:country") or "United Kingdom"
        postal_code = tags.get("addr:postcode")

        # Basic fields
        phone = tags.get("phone") or tags.get("contact:phone") or tags.get("contact:mobile")
        website = tags.get("website") or tags.get("contact:website") or tags.get("url")
        email = tags.get("email") or tags.get("contact:email")

        # Coordinates
        lat = element.get("lat")
        lon = element.get("lon")
        if not lat or not lon:
            # For ways and relations, center is returned
            center = element.get("center") or {}
            lat = center.get("lat")
            lon = center.get("lon")

        # Map category from primary tags
        category = tags.get("amenity") or tags.get("shop") or tags.get("tourism") or tags.get("craft") or "General"

        # Social handles
        socials = {}
        for plat in ["facebook", "instagram", "twitter", "linkedin"]:
            val = tags.get(plat) or tags.get(f"contact:{plat}")
            if val:
                socials[plat] = val

        # Populate custom raw data context
        raw_data = {
            "id": element.get("id"),
            "type": element.get("type"),
            "lat": lat,
            "lon": lon,
            "tags": tags,
        }

        # Update metrics counters
        self.metrics["unique_businesses_discovered"] += 1
        if website:
            self.metrics["records_containing_website"] += 1
        if phone:
            self.metrics["records_containing_phone"] += 1
        if address:
            self.metrics["records_containing_address"] += 1
        if email:
            self.metrics["records_containing_email"] += 1

        element_type = element.get("type") or "node"
        element_id = element.get("id") or "0"

        return NormalizedLeadRecord(
            source=self.source_name,
            source_id=f"{element_type}/{element_id}",
            business_name=business_name.strip(),
            website=website,
            phone=phone,
            email=email,
            address=address,
            city=city,
            state=state,
            country=country,
            category=category,
            social_handles=socials,
            raw_data=raw_data,
        )

    def search_leads(
        self,
        query: str,
        location: str | None = None,
        limit: int = 100,
        page: int = 1,
        pagination_state: dict[str, Any] | None = None,
    ) -> list[NormalizedLeadRecord]:
        """Queries Overpass API and returns a list of normalized lead records."""
        if self.is_circuit_open():
            logger.warning("[OSM Overpass] Connector circuit breaker is open. Aborting search.")
            return []

        if not self.acquire_rate_limit():
            logger.warning("[OSM Overpass] Rate limit exceeded. Aborting search.")
            return []

        if not location:
            logger.warning("[OSM Overpass] Location not specified. Search aborted.")
            return []

        # 1. Resolve and subdivide location
        cells = SubdivisionManager.subdivide_location(location, subdivisions=9)
        if not cells:
            return []

        if page > len(cells):
            if pagination_state is not None:
                pagination_state["has_more"] = False
            return []
            
        cell_idx = (page - 1) % len(cells)
        target_bbox = cells[cell_idx]["bbox"]

        # 3. Build Overpass QL Query
        try:
            osm_query = self._build_overpass_query(query, target_bbox)
        except ValueError as e:
            if str(e) == "UNSUPPORTED_CATEGORY":
                return []
            raise e

        # 4. Request Overpass API
        try:
            raw_response = self._execute_query(osm_query)
            elements = raw_response.get("elements") or []
            
            self.metrics["total_osm_results"] += len(elements)
            self.record_success()

            # 5. Parse and Normalize
            records: list[NormalizedLeadRecord] = []
            for element in elements:
                rec = self._parse_element(element)
                if rec:
                    records.append(rec)
                    if len(records) >= limit:
                        break

            if pagination_state is not None:
                pagination_state["results_returned"] = pagination_state.get("results_returned", 0) + len(records)
                if page >= len(cells):
                    pagination_state["has_more"] = False

            # Log updated cumulative metrics
            avg_time = (
                self.metrics["total_response_time"] / self.metrics["successful_queries"]
                if self.metrics["successful_queries"] > 0
                else 0.0
            )
            logger.info(
                f"[OSM Metrics] Total Results: {self.metrics['total_osm_results']} | "
                f"Unique Discovered: {self.metrics['unique_businesses_discovered']} | "
                f"Query Failures: {self.metrics['query_failures']} | "
                f"Avg Response Time: {avg_time:.2f}s"
            )

            return records

        except Exception as error:
            self.record_failure()
            logger.error(f"[OSM Overpass] Search execution failed on page {page}: {error}")
            return []

    def health_check(self) -> bool:
        """Returns True if the Overpass API is online and accepting queries."""
        if self.is_circuit_open():
            return False
            
        try:
            validated_url = validate_outbound_url(self.endpoint_url)
        except Exception:
            validated_url = self.endpoint_url

        try:
            # Overpass API returns status or short response on standard request
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(validated_url)
                return resp.status_code in (200, 400, 429)
        except Exception:
            return False
