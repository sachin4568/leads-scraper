from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.app.sources.rate_limiter import SourceRateLimiter


class NormalizedLeadRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source: str = Field(..., description="Source name e.g. google_maps, yelp, meta")
    source_id: str = Field(..., description="Unique source identifier")
    business_name: str
    website: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    category: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    social_handles: dict[str, str] = Field(default_factory=dict)
    raw_data: dict[str, Any] = Field(default_factory=dict)

    def get_idempotency_key(self) -> str:
        if self.source_id and str(self.source_id).strip():
            return f"{self.source}:{str(self.source_id).strip()}"
        return f"{self.source}:{self.business_name}"

    @property
    def source_name(self) -> str:
        return self.source

    @property
    def source_record_id(self) -> str:
        return self.source_id

    @property
    def industry(self) -> str:
        return self.category or "General"


class SourceConnector(ABC):
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 60.0,
        rate_limiter: SourceRateLimiter | None = None,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.rate_limiter = rate_limiter or SourceRateLimiter()

    def acquire_rate_limit(self) -> bool:
        return self.rate_limiter.acquire(self.source_name)

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Name of the data source e.g. 'google_maps'"""

    @abstractmethod
    def search_leads(
        self,
        query: str,
        location: str | None = None,
        limit: int = 100,
        page: int = 1,
        pagination_state: dict[str, Any] | None = None,
    ) -> list[NormalizedLeadRecord]:
        """Fetch and return normalized lead records from the source."""

    @abstractmethod
    def health_check(self) -> bool:
        """Check if the source API is available."""

    def is_circuit_open(self) -> bool:
        if self.failure_count >= self.failure_threshold:
            if self.last_failure_time and (
                time.time() - self.last_failure_time > self.recovery_timeout_seconds
            ):
                # Half-open state reset
                self.failure_count = 0
                self.last_failure_time = None
                return False
            return True
        return False

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()

    def record_success(self) -> None:
        self.failure_count = 0
        self.last_failure_time = None
