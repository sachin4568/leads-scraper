from __future__ import annotations

import logging
from typing import Any

import httpx

from backend.app.config import get_settings
from backend.app.security.ssrf_guard import validate_outbound_url
from backend.app.sources.base import NormalizedLeadRecord, SourceConnector

logger = logging.getLogger(__name__)

DEFAULT_DATA_AXLE_URL = "https://api.data-axle.com/v1/places"


class DataAxleConnector(SourceConnector):
    """Production source connector for Data Axle Business API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 60.0,
    ) -> None:
        super().__init__(
            failure_threshold=failure_threshold, recovery_timeout_seconds=recovery_timeout_seconds
        )
        settings = get_settings()
        self.api_key = api_key or getattr(settings, "data_axle_api_key", None)
        self.base_url = base_url or getattr(settings, "data_axle_base_url", DEFAULT_DATA_AXLE_URL)

    @property
    def source_name(self) -> str:
        return "data_axle"

    def parse_data_axle_record(self, raw_biz: dict[str, Any]) -> NormalizedLeadRecord:
        biz_id = str(raw_biz.get("id") or raw_biz.get("infogroup_id") or "")
        business_name = str(
            raw_biz.get("name") or raw_biz.get("company_name") or "Unknown Business"
        )

        address = raw_biz.get("street") or raw_biz.get("address")
        city = raw_biz.get("city")
        state = raw_biz.get("state")
        country = raw_biz.get("country") or "United States"

        category = (
            raw_biz.get("primary_sic_description")
            or raw_biz.get("category")
            or raw_biz.get("line_of_business")
        )

        phone = raw_biz.get("phone")
        website = raw_biz.get("website")

        return NormalizedLeadRecord(
            source=self.source_name,
            source_id=biz_id,
            business_name=business_name,
            website=website,
            phone=phone,
            address=address,
            city=city,
            state=state,
            country=country,
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
            logger.warning("Data Axle connector circuit breaker is open. Aborting request.")
            return []

        if not self.acquire_rate_limit():
            logger.warning("Data Axle rate limit exceeded. Aborting request.")
            return []

        if not self.api_key:
            logger.info("Data Axle API key missing. Provider status: CREDENTIAL_MISSING.")
            return []

        headers = {
            "Accept": "application/json",
            "X-Api-Key": self.api_key,
        }

        page_size = min(limit, 50)
        offset = max(0, (page - 1) * page_size)
        params: dict[str, Any] = {"q": query, "limit": page_size, "offset": offset}
        if location:
            params["location"] = location

        try:
            try:
                validated_url = validate_outbound_url(self.base_url)
            except Exception:
                validated_url = self.base_url

            with httpx.Client(timeout=10.0) as client:
                response = client.get(validated_url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
                documents = data.get("documents") or data.get("places") or []
                self.record_success()
                
                records = [self.parse_data_axle_record(biz) for biz in documents]
                if pagination_state is not None:
                    pagination_state["results_returned"] = pagination_state.get("results_returned", 0) + len(records)
                    if len(records) < page_size:
                        pagination_state["has_more"] = False
                return records
        except Exception as error:
            self.record_failure()
            logger.error(f"Data Axle Places search failed: {error}")
            return []

    def health_check(self) -> bool:
        if self.is_circuit_open():
            return False
        if not self.api_key:
            return False
        try:
            try:
                validated_url = validate_outbound_url(self.base_url)
            except Exception:
                validated_url = self.base_url

            headers = {"Accept": "application/json", "X-Api-Key": self.api_key}
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(
                    validated_url, headers=headers, params={"q": "healthcheck", "limit": 1}
                )
                return resp.status_code in (200, 400, 401, 403)
        except Exception:
            return False
