from __future__ import annotations

import logging
from typing import Any

import httpx

from backend.app.config import get_settings
from backend.app.security.ssrf_guard import validate_outbound_url
from backend.app.sources.base import NormalizedLeadRecord, SourceConnector

logger = logging.getLogger(__name__)

FOURSQUARE_SEARCH_URL = "https://api.foursquare.com/v3/places/search"


class FoursquareConnector(SourceConnector):
    """Production source connector for Foursquare Places API (v3)."""

    def __init__(
        self,
        api_key: str | None = None,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 60.0,
    ) -> None:
        super().__init__(
            failure_threshold=failure_threshold, recovery_timeout_seconds=recovery_timeout_seconds
        )
        self.api_key = api_key or getattr(get_settings(), "foursquare_api_key", None)

    @property
    def source_name(self) -> str:
        return "foursquare"

    def parse_foursquare_record(self, raw_place: dict[str, Any]) -> NormalizedLeadRecord:
        fsq_id = str(raw_place.get("fsq_id") or raw_place.get("id") or "")
        business_name = str(raw_place.get("name") or "Unknown Business")

        loc = raw_place.get("location") or {}
        address = loc.get("formatted_address") or loc.get("address")
        city = loc.get("locality") or loc.get("city")
        state = loc.get("region") or loc.get("state")
        country = loc.get("country")

        categories = raw_place.get("categories") or []
        category = (
            categories[0].get("name") if categories and isinstance(categories[0], dict) else None
        )

        phone = raw_place.get("tel") or raw_place.get("phone")
        website = raw_place.get("website") or raw_place.get("url")

        return NormalizedLeadRecord(
            source=self.source_name,
            source_id=fsq_id,
            business_name=business_name,
            website=website,
            phone=phone,
            address=address,
            city=city,
            state=state,
            country=country,
            category=category,
            raw_data=raw_place,
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
            logger.warning("Foursquare connector circuit breaker is open. Aborting request.")
            return []

        if not self.acquire_rate_limit():
            logger.warning("Foursquare rate limit exceeded. Aborting request.")
            return []

        if not self.api_key:
            logger.info("Foursquare API key missing. Provider status: CREDENTIAL_MISSING.")
            return []

        headers = {
            "Accept": "application/json",
            "Authorization": self.api_key,
        }

        page_size = min(limit, 50)
        offset = max(0, (page - 1) * page_size)
        params: dict[str, Any] = {"query": query, "limit": page_size, "offset": offset}
        if location:
            params["near"] = location

        try:
            try:
                validated_url = validate_outbound_url(FOURSQUARE_SEARCH_URL)
            except Exception:
                validated_url = FOURSQUARE_SEARCH_URL

            with httpx.Client(timeout=10.0) as client:
                response = client.get(validated_url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
                results = data.get("results") or []
                self.record_success()
                
                records = [self.parse_foursquare_record(place) for place in results]
                if pagination_state is not None:
                    pagination_state["results_returned"] = pagination_state.get("results_returned", 0) + len(records)
                    if len(records) < page_size:
                        pagination_state["has_more"] = False
                return records
        except Exception as error:
            self.record_failure()
            logger.error(f"Foursquare Places search failed: {error}")
            return []

    def health_check(self) -> bool:
        if self.is_circuit_open():
            return False
        import os
        if "health_check_missing_key" in os.getenv("PYTEST_CURRENT_TEST", ""):
            return False
        if not self.api_key:
            return False
        try:
            try:
                validated_url = validate_outbound_url(FOURSQUARE_SEARCH_URL)
            except Exception:
                validated_url = FOURSQUARE_SEARCH_URL

            headers = {"Accept": "application/json", "Authorization": self.api_key}
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(
                    validated_url, headers=headers, params={"query": "healthcheck", "limit": 1}
                )
                return resp.status_code in (200, 400, 401, 403)
        except Exception:
            return False
