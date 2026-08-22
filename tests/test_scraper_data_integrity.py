from __future__ import annotations

import pytest
import respx
import httpx
from httpx import Response
from sqlalchemy.orm import Session

from backend.app.sources.google_maps import PLACES_TEXT_SEARCH_URL, GoogleMapsConnector
from backend.app.ingestion.lifecycle import LifecycleResolver, LifecycleState
from backend.app.ingestion.ingestion import RawLead
from backend.app.models_phase2 import CanonicalLead, LeadObservation
from backend.app.models import Lead, ScrapeJob
from backend.app.worker import execute_scrape_job
from backend.app.database import Base, SessionLocal, engine

@pytest.fixture(autouse=True)
def mock_dns(monkeypatch) -> None:
    def mock_getaddrinfo(host, port, *args, **kwargs):
        if host == "maps.googleapis.com":
            return [(None, None, None, None, ("142.250.190.46", 443))]
        raise OSError(f"Unmocked host {host}")
    monkeypatch.setattr("socket.getaddrinfo", mock_getaddrinfo)

# 1. Invalid Google API key creates zero leads
@respx.mock
def test_invalid_api_key_fails() -> None:
    respx.get(PLACES_TEXT_SEARCH_URL).mock(
        return_value=Response(200, json={"status": "REQUEST_DENIED", "error_message": "The provided API key is invalid."})
    )
    connector = GoogleMapsConnector(api_key="invalid-key")
    with pytest.raises(ValueError) as exc:
        connector.search_leads(query="Plumbers", location="London")
    assert str(exc.value) == "PROVIDER_AUTH_FAILED"

# 2. Missing Google API key creates zero leads
def test_missing_api_key_fails() -> None:
    connector = GoogleMapsConnector(api_key=None)
    connector.api_key = None  # Ensure it is explicitly None and doesn't fall back to settings
    with pytest.raises(ValueError) as exc:
        connector.search_leads(query="Plumbers", location="London")
    assert str(exc.value) == "CREDENTIAL_MISSING"

# 3. Provider timeout creates zero fabricated leads
@respx.mock
def test_provider_timeout_fails() -> None:
    respx.get(PLACES_TEXT_SEARCH_URL).mock(side_effect=httpx.ConnectTimeout("Connection timed out"))
    connector = GoogleMapsConnector(api_key="valid-key")
    with pytest.raises(ValueError) as exc:
        connector.search_leads(query="Plumbers", location="London")
    assert str(exc.value) == "PROVIDER_UNAVAILABLE"

# 4. Empty provider response creates zero fabricated leads
@respx.mock
def test_empty_provider_response_returns_empty() -> None:
    respx.get(PLACES_TEXT_SEARCH_URL).mock(
        return_value=Response(200, json={"status": "OK", "results": []})
    )
    connector = GoogleMapsConnector(api_key="valid-key")
    leads = connector.search_leads(query="Plumbers", location="London")
    assert leads == []

# 6. Mock provider IDs cannot enter production canonical leads
def test_mock_provider_ids_rejected(db_session: Session) -> None:
    resolver = LifecycleResolver()
    raw_lead = RawLead(
        source_name="google_maps",
        source_record_id="mock-place-123",
        business_name="Test Business",
        industry="General",
    )
    with pytest.raises(ValueError) as exc:
        resolver.process_observation(db_session, raw_lead)
    assert str(exc.value) == "PROVIDER_RECORD_INVALID"

# 7. Two real provider records remain isolated
def test_records_remain_isolated(db_session: Session) -> None:
    resolver = LifecycleResolver()
    raw1 = RawLead(
        source_name="google_maps",
        source_record_id="place-abc",
        business_name="Plumbing Pro A",
        industry="General",
        phone="+44 20 8888 1111",
    )
    raw2 = RawLead(
        source_name="google_maps",
        source_record_id="place-def",
        business_name="Plumbing Pro B",
        industry="General",
        phone="+44 20 8888 2222",
    )
    c1, o1, s1 = resolver.process_observation(db_session, raw1)
    c2, o2, s2 = resolver.process_observation(db_session, raw2)
    
    assert c1.id != c2.id
    assert c1.business_name == "Plumbing Pro A"
    assert c2.business_name == "Plumbing Pro B"

# 8. Provider record IDs remain attached to their leads
def test_provider_ids_attached(db_session: Session) -> None:
    resolver = LifecycleResolver()
    raw = RawLead(
        source_name="google_maps",
        source_record_id="place-real-999",
        business_name="Real Plumbing Ltd",
        industry="General",
    )
    c, o, s = resolver.process_observation(db_session, raw)
    assert o.source_record_id == "place-real-999"
    assert o.idempotency_key == "google_maps:place-real-999"

# 9. NULL provider fields remain NULL
def test_null_fields_remain_null(db_session: Session) -> None:
    resolver = LifecycleResolver()
    raw = RawLead(
        source_name="google_maps",
        source_record_id="place-real-nulls",
        business_name="No Info Plumbing",
        industry="General",
        phone=None,
        email=None,
        website=None,
    )
    c, o, s = resolver.process_observation(db_session, raw)
    assert c.canonical_phone is None
    assert c.canonical_email is None
    assert c.canonical_domain is None
    assert o.observed_phone is None
    assert o.observed_email is None
    assert o.observed_website is None

@pytest.fixture
def db_session() -> Session:
    # Set up clean in-memory session for lifecycle tests
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()
