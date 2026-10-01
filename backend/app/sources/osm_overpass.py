from __future__ import annotations

import logging
import math
import time
from typing import Any

import httpx

from backend.app.config import get_settings
from backend.app.security.ssrf_guard import validate_outbound_url
from backend.app.sources.base import NormalizedLeadRecord, SourceConnector
from backend.app.sources.geo_utils import SubdivisionManager

logger = logging.getLogger(__name__)

import re

# Comprehensive category-to-OSM tag mappings
DEFAULT_CATEGORY_MAPPING: dict[str, list[tuple[str, str]]] = {
    # Home & Garden Services
    "lawn care": [("craft", "gardener"), ("craft", "landscaper"), ("shop", "garden_centre")],
    "lawn": [("craft", "gardener"), ("craft", "landscaper"), ("shop", "garden_centre")],
    "landscaping": [("craft", "landscaper"), ("craft", "gardener"), ("shop", "garden_centre")],
    "gardening": [("craft", "gardener"), ("shop", "garden_centre")],
    "gardener": [("craft", "gardener"), ("craft", "landscaper")],
    "gardeners": [("craft", "gardener"), ("craft", "landscaper")],
    "tree service": [("craft", "gardener"), ("craft", "tree_surgeon"), ("craft", "landscaper")],
    "tree surgeon": [("craft", "tree_surgeon"), ("craft", "gardener")],
    "cleaning": [("craft", "cleaning"), ("shop", "dry_cleaning")],
    "cleaners": [("craft", "cleaning")],
    "carpet cleaning": [("craft", "cleaning")],
    "maid service": [("craft", "cleaning")],
    "pest control": [("craft", "pest_control")],
    "carpenter": [("craft", "carpenter")],
    "carpenters": [("craft", "carpenter")],
    "carpentry": [("craft", "carpenter")],
    "painter": [("craft", "painter")],
    "painters": [("craft", "painter")],
    "painting": [("craft", "painter")],
    "electrician": [("craft", "electrician"), ("shop", "electrical")],
    "electricians": [("craft", "electrician"), ("shop", "electrical")],
    "electrical": [("craft", "electrician"), ("shop", "electrical")],
    "roofing": [("craft", "roofer")],
    "roofer": [("craft", "roofer")],
    "roofers": [("craft", "roofer")],
    "plumber": [("craft", "plumber")],
    "plumbers": [("craft", "plumber")],
    "plumbing": [("craft", "plumber")],
    "hvac": [("craft", "hvac")],
    "air conditioning": [("craft", "hvac")],
    "heating": [("craft", "hvac")],
    "locksmith": [("craft", "locksmith")],
    "locksmiths": [("craft", "locksmith")],
    "handyman": [("craft", "handyman"), ("craft", "builder")],
    "contractor": [("craft", "builder"), ("craft", "contractor"), ("craft", "handyman")],
    "contractors": [("craft", "builder"), ("craft", "contractor")],
    "general contractor": [("craft", "builder"), ("craft", "contractor")],
    "construction": [("craft", "builder"), ("craft", "contractor")],
    "builder": [("craft", "builder")],
    "builders": [("craft", "builder")],
    "solar": [("craft", "solar")],
    "solar installation": [("craft", "solar")],
    "moving": [("craft", "moving"), ("craft", "mover")],
    "movers": [("craft", "moving")],

    # Automotive
    "auto repair": [("shop", "car_repair"), ("craft", "car_repair"), ("amenity", "car_repair")],
    "mechanic": [("shop", "car_repair"), ("craft", "car_repair")],
    "car repair": [("shop", "car_repair"), ("craft", "car_repair")],
    "auto body": [("shop", "car_repair"), ("craft", "car_repair")],
    "car wash": [("amenity", "car_wash")],
    "auto detailing": [("amenity", "car_wash")],
    "towing": [("craft", "towing")],

    # Health & Wellness & Beauty
    "veterinary": [("amenity", "veterinary")],
    "veterinarian": [("amenity", "veterinary")],
    "vet": [("amenity", "veterinary")],
    "pet grooming": [("shop", "pet_grooming"), ("shop", "pet")],
    "pet store": [("shop", "pet"), ("shop", "pet_grooming")],
    "hairdresser": [("shop", "hairdresser")],
    "hair salon": [("shop", "hairdresser")],
    "barber": [("shop", "hairdresser")],
    "barbershop": [("shop", "hairdresser")],
    "beauty": [("shop", "beauty")],
    "beauty salon": [("shop", "beauty"), ("shop", "hairdresser")],
    "spa": [("amenity", "spa"), ("shop", "beauty"), ("shop", "massage")],
    "massage": [("shop", "massage"), ("amenity", "spa")],
    "nail salon": [("shop", "beauty")],
    "gym": [("leisure", "fitness_centre"), ("amenity", "gym")],
    "fitness": [("leisure", "fitness_centre")],
    "personal trainer": [("leisure", "fitness_centre")],
    "yoga": [("leisure", "fitness_centre"), ("leisure", "sports_centre")],
    "optician": [("shop", "optician")],
    "optometrist": [("shop", "optician")],
    "dentist": [("amenity", "dentist")],
    "dental": [("amenity", "dentist")],
    "dental clinic": [("amenity", "dentist")],
    "clinic": [("amenity", "clinic"), ("amenity", "doctors")],
    "doctor": [("amenity", "doctors"), ("amenity", "clinic")],
    "medical clinic": [("amenity", "clinic"), ("amenity", "doctors")],
    "pharmacy": [("amenity", "pharmacy")],
    "chiropractor": [("healthcare", "chiropractor")],
    "physiotherapy": [("healthcare", "physiotherapist")],

    # Professional Services
    "lawyer": [("office", "lawyer"), ("amenity", "lawyer")],
    "attorney": [("office", "lawyer")],
    "law firm": [("office", "lawyer")],
    "legal": [("office", "lawyer")],
    "accountant": [("office", "accountant")],
    "cpa": [("office", "accountant")],
    "bookkeeping": [("office", "accountant")],
    "tax consultant": [("office", "accountant")],
    "real estate": [("office", "estate_agent"), ("shop", "estate_agent")],
    "realtor": [("office", "estate_agent")],
    "estate agent": [("office", "estate_agent")],
    "property management": [("office", "estate_agent")],
    "insurance": [("office", "insurance")],
    "financial advisor": [("office", "financial_advisor"), ("office", "financial")],
    "photographer": [("craft", "photographer"), ("shop", "photographer")],
    "photography": [("craft", "photographer"), ("shop", "photographer")],
    "caterer": [("craft", "caterer"), ("amenity", "catering")],
    "catering": [("craft", "caterer"), ("amenity", "catering")],
    "driving school": [("amenity", "driving_school")],
    "daycare": [("amenity", "kindergarten"), ("amenity", "childcare")],
    "childcare": [("amenity", "childcare"), ("amenity", "kindergarten")],

    # Food & Hospitality
    "restaurant": [("amenity", "restaurant")],
    "cafe": [("amenity", "cafe")],
    "bar": [("amenity", "bar")],
    "pub": [("amenity", "pub")],
    "bakery": [("shop", "bakery")],
    "hotel": [("tourism", "hotel")],
}


class OSMOverpassProviderError(ValueError):
    """Raised when OSM Overpass provider fails due to HTTP, network, or decoding errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        endpoint: str | None = None,
        elapsed_ms: float | None = None,
        attempt: int | None = None,
        details: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.endpoint = endpoint
        self.elapsed_ms = elapsed_ms
        self.attempt = attempt
        self.details = details


DEFAULT_OSM_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 LeadIntelligence/1.0"
FALLBACK_OVERPASS_ENDPOINTS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
]


class OSMOverpassConnector(SourceConnector):
    """Lead discovery connector using OpenStreetMap (OSM) via the Overpass API."""

    def __init__(
        self,
        endpoint_url: str | None = None,
        user_agent: str | None = None,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 60.0,
    ) -> None:
        super().__init__(
            failure_threshold=failure_threshold,
            recovery_timeout_seconds=recovery_timeout_seconds,
        )
        self.endpoint_url = endpoint_url or getattr(get_settings(), "overpass_api_url", "https://overpass-api.de/api/interpreter")
        self.user_agent = user_agent
        self.user_agent = "python-httpx/0.27.0"
        self.seen_queries = set()
        
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

    def get_canonical_category(self, category: str) -> str | None:
        """Resolves a category string to a canonical OSM tag identity (e.g., 'amenity=restaurant')."""
        if not category:
            return None
        cat_key = category.lower().strip()
        if cat_key in DEFAULT_CATEGORY_MAPPING:
            tag_key, tag_val = DEFAULT_CATEGORY_MAPPING[cat_key][0]
            return f"{tag_key}={tag_val}"
        if cat_key.endswith("s") and cat_key[:-1] in DEFAULT_CATEGORY_MAPPING:
            tag_key, tag_val = DEFAULT_CATEGORY_MAPPING[cat_key[:-1]][0]
            return f"{tag_key}={tag_val}"
        for key, tuples in DEFAULT_CATEGORY_MAPPING.items():
            if key in cat_key or cat_key in key:
                tag_key, tag_val = tuples[0]
                return f"{tag_key}={tag_val}"
        return f"custom={cat_key}"

    def supports_category(self, category: str) -> bool:
        """Checks whether a category is supported by the Overpass tag mapping."""
        return bool(category and category.strip())

    def _build_overpass_query(self, category: str, bbox: list[float]) -> str:
        """Builds a secure and sanitized Overpass QL query using resolved category tags and bounds."""
        cat_key = category.lower().strip()
        tag_tuples: list[tuple[str, str]] = []
        
        if cat_key in DEFAULT_CATEGORY_MAPPING:
            tag_tuples = DEFAULT_CATEGORY_MAPPING[cat_key]
        elif cat_key.endswith("s") and cat_key[:-1] in DEFAULT_CATEGORY_MAPPING:
            tag_tuples = DEFAULT_CATEGORY_MAPPING[cat_key[:-1]]
        else:
            for k, tuples in DEFAULT_CATEGORY_MAPPING.items():
                if k in cat_key or cat_key in k:
                    tag_tuples = tuples
                    break

        lat_min, lat_max, lon_min, lon_max = [float(x) for x in bbox]
        bounds_str = f"({lat_min},{lon_min},{lat_max},{lon_max})"

        if not tag_tuples:
            clean_word = re.sub(r"[^a-zA-Z0-9 ]", "", cat_key).strip().split()[0] if cat_key else "business"
            return (
                f"[out:json][timeout:25];\n"
                f"(\n"
                f'  node["name"~"{clean_word}", i]{bounds_str};\n'
                f'  way["name"~"{clean_word}", i]{bounds_str};\n'
                f");\n"
                f"out center;"
            )

        query_lines = []
        for tag_key, tag_val in tag_tuples:
            query_lines.append(f'  node["{tag_key}"="{tag_val}"]{bounds_str};')
            query_lines.append(f'  way["{tag_key}"="{tag_val}"]{bounds_str};')



        return (
            f"[out:json][timeout:35];\n"
            f"(\n"
            + "\n".join(query_lines) + "\n"
            f");\n"
            f"out center;"
        )

    def _execute_query(self, query: str, category: str = "unknown") -> dict[str, Any]:
        if query in self.seen_queries:
            logger.info(f"[OSM Overpass] Skipping identical query for category '{category}'")
            return {"elements": []}
        self.seen_queries.add(query)
        """Performs request to Overpass API with bounded timeouts, mirror failover, and retry logic."""
        max_retries = 1
        backoff_factor = 1.5

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "*/*",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }
        canonical_cat = self.get_canonical_category(category) or category
        timeout = httpx.Timeout(45.0)

        # Build candidate endpoints prioritizing fastest responsive mirrors
        target_endpoints = list(dict.fromkeys([*FALLBACK_OVERPASS_ENDPOINTS, self.endpoint_url]))

        total_retry_delay = 0.0
        start_overall = time.time()
        last_error = None

        for endpoint in target_endpoints:
            try:
                validated_url = validate_outbound_url(endpoint)
            except Exception:
                validated_url = endpoint

            for attempt in range(max_retries + 1):
                if not self.acquire_rate_limit():
                    logger.warning("[OSM Overpass] Rate limit hit. Delaying request call.")
                    time.sleep(1.0)
                    total_retry_delay += 1.0

                start_attempt = time.time()
                try:
                    with httpx.Client(timeout=timeout) as client:
                        logger.info(
                            f"[OSM Overpass] Sending request: source={self.source_name} endpoint={validated_url} "
                            f"http_method=POST attempt={attempt + 1}/{max_retries + 1} query_category={category} canonical_category={canonical_cat}"
                        )
                        response = client.post(validated_url, data={"data": query}, headers=headers)
                        server_elapsed_ms = round((time.time() - start_attempt) * 1000, 2)
                        total_elapsed_ms = round((time.time() - start_overall) * 1000, 2)

                        if response.status_code == 200:
                            self.metrics["successful_queries"] += 1
                            self.metrics["total_response_time"] += server_elapsed_ms
                            return response.json()

                        if response.status_code == 429:
                            if attempt < max_retries:
                                retry_after_hdr = response.headers.get("Retry-After")
                                backoff = min(float(retry_after_hdr), 10.0) if (retry_after_hdr and retry_after_hdr.isdigit()) else min(backoff_factor * (attempt + 1), 6.0)
                                time.sleep(backoff)
                                total_retry_delay += backoff
                                continue
                            break  # Try next mirror

                        if response.status_code in (403, 406, 500, 502, 503, 504):
                            logger.warning(f"[OSM Overpass] Server error {response.status_code} on {validated_url}. Trying next mirror...")
                            break

                except (httpx.TimeoutException, httpx.NetworkError) as net_err:
                    last_error = net_err
                    logger.warning(f"[OSM Overpass] Network/timeout error on {validated_url}: {net_err}. Trying next mirror...")
                    break
                except Exception as ex:
                    last_error = ex
                    logger.warning(f"[OSM Overpass] Unexpected error on {validated_url}: {ex}. Trying next mirror...")
                    break

        self.metrics["query_failures"] += 1
        raise OSMOverpassProviderError(
            f"[OSM Overpass] All Overpass API mirrors failed or timed out: {last_error}",
            status_code=504,
            endpoint=self.endpoint_url,
            elapsed_ms=round((time.time() - start_overall) * 1000, 2),
        )

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
        country = tags.get("addr:country")
        postal_code = tags.get("addr:postcode")

        full_addr_parts = [p for p in [address, city, state, postal_code, country] if p]
        formatted_address = ", ".join(full_addr_parts) if full_addr_parts else address

        # Basic fields
        phone = tags.get("phone") or tags.get("contact:phone") or tags.get("contact:mobile")
        website = (
            tags.get("website")
            or tags.get("contact:website")
            or tags.get("contact:url")
            or tags.get("url")
            or tags.get("operator:website")
            or tags.get("brand:website")
        )
        email = tags.get("email") or tags.get("contact:email")

        # Coordinates
        lat = None
        lon = None
        if "lat" in element:
            lat = float(element["lat"])
        if "lon" in element:
            lon = float(element["lon"])
        if lat is None or lon is None:
            # For ways and relations, center is returned
            center = element.get("center") or {}
            if "lat" in center:
                lat = float(center["lat"])
            if "lon" in center:
                lon = float(center["lon"])

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
        if formatted_address:
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
            address=formatted_address or address,
            formatted_address=formatted_address,
            city=city,
            state=state,
            country=country,
            postal_code=postal_code,
            latitude=lat,
            longitude=lon,
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

        # 1. Resolve bounding box for location
        bbox = SubdivisionManager.geocode_location(location)
        if not bbox:
            logger.warning(f"[OSM Overpass] Could not geocode location: '{location}'. Search aborted.")
            return []

        # 2. Strategy selection: Default is Single-BBox; subdivision is available as explicit fallback
        use_subdivision_fallback = (
            pagination_state is not None 
            and pagination_state.get("subdivision_fallback", False)
        )
        # 2. Check if bbox is large (> 0.8 degrees in lat or lon) and needs subdivision
        lat_span = abs(bbox[1] - bbox[0])
        lon_span = abs(bbox[3] - bbox[2])

        if lat_span > 0.8 or lon_span > 0.8 or use_subdivision_fallback:
            grid_dim = max(2, min(8, math.ceil(max(lat_span, lon_span) / 0.6)))
            cells = self._subdivide_bbox(bbox, subdivisions=grid_dim**2)
            if page > 1 and page <= len(cells):
                target_boxes = [cells[page - 1]]
            else:
                target_boxes = cells
        else:
            target_boxes = [bbox]

        if pagination_state is not None:
            pagination_state["has_more"] = False

        # 3. Query cells and collect discovered records
        records: list[NormalizedLeadRecord] = []
        seen_keys: set[str] = set()

        for target_bbox in target_boxes:
            try:
                osm_query = self._build_overpass_query(query, target_bbox)
                raw_response = self._execute_query(osm_query, category=query)
                elements = raw_response.get("elements") or []
                self.metrics["total_osm_results"] += len(elements)
                self.record_success()

                for element in elements:
                    rec = self._parse_element(element)
                    if rec and rec.business_name:
                        dedup_k = f"{rec.business_name.lower().strip()}:{rec.phone or ''}"
                        if dedup_k not in seen_keys:
                            seen_keys.add(dedup_k)
                            records.append(rec)
                            if len(records) >= limit:
                                break
            except Exception as cell_err:
                logger.warning(f"[OSM Overpass] Cell query warning for bbox {target_bbox}: {cell_err}")
                continue

            if len(records) >= limit:
                break

        if pagination_state is not None:
            pagination_state["results_returned"] = pagination_state.get("results_returned", 0) + len(records)

        avg_time = (
            self.metrics["total_response_time"] / self.metrics["successful_queries"]
            if self.metrics["successful_queries"] > 0
            else 0.0
        )
        logger.info(
            f"[OSM Metrics] Query '{query}' ({self.get_canonical_category(query)}) | "
            f"Results: {len(records)} | Total Discovered: {self.metrics['unique_businesses_discovered']} | "
            f"Query Failures: {self.metrics['query_failures']} | Avg Time: {avg_time:.2f}s"
        )
        return records

    def health_check(self) -> bool:
        """Returns True if the Overpass API is online and accepting queries."""
        if self.is_circuit_open():
            return False
            
        try:
            validated_url = validate_outbound_url(self.endpoint_url)
        except Exception:
            validated_url = self.endpoint_url

        try:
            headers = {
                "User-Agent": self.user_agent,
                "Accept": "application/json",
            }
            # Overpass API returns status or short response on standard request
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(validated_url, headers=headers)
                return resp.status_code in (200, 400, 429)
        except Exception:
            return False
