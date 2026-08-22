from __future__ import annotations

import time

from backend.app.security.token_encryption import decrypt_token, encrypt_token
from backend.app.sources.base import NormalizedLeadRecord, SourceConnector


class DummyConnector(SourceConnector):
    @property
    def source_name(self) -> str:
        return "dummy_source"

    def search_leads(
        self, query: str, location: str | None = None, limit: int = 100
    ) -> list[NormalizedLeadRecord]:
        return [
            NormalizedLeadRecord(
                source=self.source_name,
                source_id="dummy-1",
                business_name="Dummy Business",
                website="https://dummy.example.com",
            )
        ]

    def health_check(self) -> bool:
        return True


def test_token_encryption_roundtrip() -> None:
    token = "secret-oauth-token-12345"
    encrypted = encrypt_token(token)
    assert encrypted != token
    assert decrypt_token(encrypted) == token


def test_normalized_lead_record_schema() -> None:
    record = NormalizedLeadRecord(
        source="google_maps",
        source_id="gmaps-123",
        business_name="Dental Clinic",
        phone="+15551234",
    )
    assert record.source == "google_maps"
    assert record.source_id == "gmaps-123"
    assert record.business_name == "Dental Clinic"
    assert record.website is None


def test_source_connector_circuit_breaker() -> None:
    connector = DummyConnector(failure_threshold=3, recovery_timeout_seconds=0.5)
    assert connector.is_circuit_open() is False

    connector.record_failure()
    connector.record_failure()
    assert connector.is_circuit_open() is False

    connector.record_failure()  # Reaches threshold (3)
    assert connector.is_circuit_open() is True

    # Recovery timeout test
    time.sleep(0.6)
    assert connector.is_circuit_open() is False  # Resets to false after recovery timeout
