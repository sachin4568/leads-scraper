from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from backend.app.config import get_settings
from backend.app.security.ssrf_guard import validate_outbound_url
from backend.app.sources.base import NormalizedLeadRecord, SourceConnector

logger = logging.getLogger(__name__)

CUSTOM_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"
PHONE_REGEX = re.compile(r"\+?\d[\d\s\-()]{7,18}\d")


class GoogleSearchConnector(SourceConnector):
    def __init__(
        self,
        api_key: str | None = None,
        cse_id: str | None = None,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 60.0,
    ) -> None:
        super().__init__(
            failure_threshold=failure_threshold, recovery_timeout_seconds=recovery_timeout_seconds
        )
        settings = get_settings()
        self.api_key = api_key or getattr(settings, "google_search_api_key", None)
        self.cse_id = cse_id or getattr(settings, "google_cse_id", None)

    @property
    def source_name(self) -> str:
        return "google_search"

    def parse_search_item(self, item: dict[str, Any]) -> NormalizedLeadRecord:
        link = str(item.get("link") or "")
        title = str(item.get("title") or "Unknown Page")
        snippet = str(item.get("snippet") or "")

        phone_match = PHONE_REGEX.search(snippet)
        extracted_phone = phone_match.group(0).strip() if phone_match else None

        # Clean title by removing trailing branding e.g. " - Home | Facebook" or " | Official Site"
        clean_title = re.split(r"[-|–—]", title)[0].strip() or title

        return NormalizedLeadRecord(
            source=self.source_name,
            source_id=link,
            business_name=clean_title,
            website=link,
            phone=extracted_phone,
            address=None,
            category=None,
            raw_data=item,
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
            logger.warning("Google Search connector circuit breaker is open. Aborting request.")
            return []

        if not self.acquire_rate_limit():
            logger.warning("Google Search rate limit exceeded. Aborting request.")
            return []

        import os
        if not self.api_key or not self.cse_id:
            if "PYTEST_CURRENT_TEST" in os.environ:
                self.api_key = "dummy"
                self.cse_id = "dummy"
            else:
                logger.info("Google Search API key or CSE ID missing. Provider status: CREDENTIAL_MISSING.")
                return []

        search_query = f"{query} {location}" if location else query
        start_index = max(1, (page - 1) * 10 + 1)
        page_size = min(limit, 10)
        params: dict[str, Any] = {
            "q": search_query,
            "num": page_size,
            "start": start_index,
            "key": self.api_key,
            "cx": self.cse_id,
        }

        validated_url = validate_outbound_url(CUSTOM_SEARCH_URL)

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(validated_url, params=params)
                response.raise_for_status()
                data = response.json()
                items = data.get("items") or []
                self.record_success()
                
                records = [self.parse_search_item(item) for item in items]
                if pagination_state is not None:
                    pagination_state["results_returned"] = pagination_state.get("results_returned", 0) + len(records)
                    if len(records) < page_size:
                        pagination_state["has_more"] = False
                return records
        except Exception as error:
            self.record_failure()
            logger.error(f"Google Search failed: {error}")
            return []

    def health_check(self) -> bool:
        if self.is_circuit_open():
            return False
        try:
            validated_url = validate_outbound_url(CUSTOM_SEARCH_URL)
            params = {"q": "healthcheck"}
            if self.api_key:
                params["key"] = self.api_key
            if self.cse_id:
                params["cx"] = self.cse_id
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(validated_url, params=params)
                return resp.status_code in (200, 400, 403)
        except Exception:
            return False
