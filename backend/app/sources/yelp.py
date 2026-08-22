from __future__ import annotations

import logging
from typing import Any

import httpx

from backend.app.config import get_settings
from backend.app.security.ssrf_guard import validate_outbound_url
from backend.app.sources.base import NormalizedLeadRecord, SourceConnector

logger = logging.getLogger(__name__)

YELP_SEARCH_URL = "https://api.yelp.com/v3/businesses/search"


class YelpConnector(SourceConnector):
    def __init__(
        self,
        api_key: str | None = None,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 60.0,
    ) -> None:
        super().__init__(
            failure_threshold=failure_threshold, recovery_timeout_seconds=recovery_timeout_seconds
        )
        self.api_key = api_key or getattr(get_settings(), "yelp_api_key", None)

    @property
    def source_name(self) -> str:
        return "yelp"

    def parse_yelp_record(self, raw_biz: dict[str, Any]) -> NormalizedLeadRecord:
        biz_id = str(raw_biz.get("id") or "")
        business_name = str(raw_biz.get("name") or "Unknown Business")
        location = raw_biz.get("location") or {}
        display_address = location.get("display_address")
        address = (
            ", ".join(display_address)
            if isinstance(display_address, list)
            else location.get("address1")
        )
        phone = raw_biz.get("display_phone") or raw_biz.get("phone")
        website = raw_biz.get("url")
        categories = raw_biz.get("categories") or []
        category = (
            categories[0].get("title") if categories and isinstance(categories[0], dict) else None
        )

        return NormalizedLeadRecord(
            source=self.source_name,
            source_id=biz_id,
            business_name=business_name,
            website=website,
            phone=phone,
            address=address,
            category=category,
            raw_data=raw_biz,
        )

    def search_leads(
        self,
        query: str,
        location: str | None = None,
        limit: int = 100,
        page: int = 1,
        pagination_state: dict[str, Any] | None = None,
    ) -> list[NormalizedLeadRecord]:
        if self.is_circuit_open():
            logger.warning("Yelp connector circuit breaker is open. Aborting request.")
            return []

        if not self.acquire_rate_limit():
            logger.warning("Yelp rate limit exceeded. Aborting request.")
            return []

        if not self.api_key:
            logger.info("Yelp API key missing. Provider status: CREDENTIAL_MISSING.")
            return []

        headers = {"Authorization": f"Bearer {self.api_key}"}
        page_size = min(limit, 50)
        offset = max(0, (page - 1) * page_size)

        params: dict[str, Any] = {"term": query, "limit": page_size, "offset": offset}
        if location:
            is_coords = False
            if "," in location:
                try:
                    parts = location.split(",")
                    lat_val = float(parts[0])
                    lon_val = float(parts[1])
                    is_coords = True
                except ValueError:
                    pass

            if is_coords:
                params["latitude"] = lat_val
                params["longitude"] = lon_val
                if pagination_state and "radius_meters" in pagination_state:
                    params["radius"] = pagination_state["radius_meters"]
            else:
                params["location"] = location

        validated_url = validate_outbound_url(YELP_SEARCH_URL)

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(validated_url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
                businesses = data.get("businesses") or []
                self.record_success()
                
                records = [self.parse_yelp_record(biz) for biz in businesses]
                if pagination_state is not None:
                    pagination_state["results_returned"] = pagination_state.get("results_returned", 0) + len(records)
                    if len(records) < page_size:
                        pagination_state["has_more"] = False
                return records
        except Exception as error:
            self.record_failure()
            logger.error(f"Yelp search failed: {error}")
            return []

    def health_check(self) -> bool:
        if self.is_circuit_open():
            return False
        try:
            validated_url = validate_outbound_url(YELP_SEARCH_URL)
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(
                    validated_url, headers=headers, params={"term": "health", "location": "test"}
                )
                return resp.status_code in (200, 400, 401, 403)
        except Exception:
            return False
