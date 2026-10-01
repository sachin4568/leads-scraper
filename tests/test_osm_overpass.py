from __future__ import annotations

import pytest
import respx
from httpx import Response, RequestError

from backend.app.sources.osm_overpass import OSMOverpassConnector, DEFAULT_CATEGORY_MAPPING
from backend.app.sources.base import NormalizedLeadRecord
from backend.app.ingestion.ingestion import RawLead
from backend.app.ingestion.lifecycle import LifecycleResolver, LifecycleState
from backend.app.database import SessionLocal


@pytest.fixture(autouse=True)
def mock_dns(monkeypatch) -> None:
    def mock_getaddrinfo(host, port, *args, **kwargs):
        if "overpass-api.de" in host or "openstreetmap.org" in host:
            return [(None, None, None, None, ("127.0.0.1", 443))]
        raise OSError(f"Unmocked host {host}")

    monkeypatch.setattr("socket.getaddrinfo", mock_getaddrinfo)


def test_category_mapping() -> None:
    connector = OSMOverpassConnector()
    # Test valid categories
    assert DEFAULT_CATEGORY_MAPPING["restaurant"] == ("amenity", "restaurant")
    assert DEFAULT_CATEGORY_MAPPING["dentist"] == ("amenity", "dentist")
    assert DEFAULT_CATEGORY_MAPPING["plumber"] == ("craft", "plumber")

    # Test query builder category resolution
    bbox = [51.0, 51.5, -0.1, 0.1]
    query = connector._build_overpass_query("restaurant", bbox)
    assert 'node["amenity"="restaurant"](51.0,-0.1,51.5,0.1);' in query


def test_location_handling() -> None:
    connector = OSMOverpassConnector()
    # Static resolution
    bbox = connector._geocode_location("London")
    assert bbox == [51.28676, 51.69187, -0.510375, 0.3340155]

    # Bounding Box subdivision
    cells = connector._subdivide_bbox(bbox, subdivisions=9)
    assert len(cells) == 9
    # Subdivided bounds check
    assert cells[0][0] == bbox[0] # lat_min
    assert cells[8][1] == bbox[1] # lat_max


@respx.mock
def test_geocode_nominatim_fallback() -> None:
    connector = OSMOverpassConnector()
    mock_nominatim = [
        {
            "boundingbox": ["40.7128", "40.7728", "-74.0060", "-73.9360"],
            "osm_id": "175905",
            "osm_type": "relation",
            "display_name": "New York City, New York, USA"
        }
    ]
    respx.get("https://nominatim.openstreetmap.org/search").mock(
        return_value=Response(200, json=mock_nominatim)
    )
    bbox = connector._geocode_location("Unknown Place")
    assert bbox == [40.7128, 40.7728, -74.0060, -73.9360]


def test_query_generation() -> None:
    connector = OSMOverpassConnector()
    bbox = [51.28676, 51.69187, -0.510375, 0.3340155]
    query = connector._build_overpass_query("dentist", bbox)
    assert "[out:json]" in query
    assert "node[\"amenity\"=\"dentist\"]" in query
    assert "way[\"amenity\"=\"dentist\"]" in query
    assert "relation[\"amenity\"=\"dentist\"]" in query
    assert "out center;" in query


def test_response_normalization() -> None:
    connector = OSMOverpassConnector()
    # Raw node element from OSM
    node_element = {
        "type": "node",
        "id": 123456,
        "lat": 51.5074,
        "lon": -0.1278,
        "tags": {
            "name": "Smiles Dental Practice",
            "amenity": "dentist",
            "addr:street": "High Street",
            "addr:housenumber": "22",
            "addr:city": "London",
            "addr:postcode": "EC1A 1BB",
            "phone": "+44 20 1234 5678",
            "website": "http://smileslondon.co.uk",
            "email": "info@smileslondon.co.uk",
            "instagram": "smiles_london"
        }
    }
    record = connector._parse_element(node_element)
    assert record is not None
    assert record.source == "osm_overpass"
    assert record.source_id == "node/123456"
    assert record.business_name == "Smiles Dental Practice"
    assert record.phone == "+44 20 1234 5678"
    assert record.website == "http://smileslondon.co.uk"
    assert record.address == "22 High Street"
    assert record.city == "London"
    assert record.category == "dentist"
    assert record.social_handles == {"instagram": "smiles_london"}


@respx.mock
def test_empty_and_malformed_response() -> None:
    connector = OSMOverpassConnector()
    bbox = [51.28676, 51.69187, -0.510375, 0.3340155]
    query = connector._build_overpass_query("cafe", bbox)

    # Malformed response test
    respx.post("https://overpass-api.de/api/interpreter").mock(
        return_value=Response(200, content="Invalid Non-JSON Content")
    )
    with pytest.raises(ValueError) as exc:
        connector._execute_query(query)
    assert "PROVIDER_UNAVAILABLE" in str(exc.value)

    # Empty result elements test
    respx.post("https://overpass-api.de/api/interpreter").mock(
        return_value=Response(200, json={"elements": []})
    )
    leads = connector.search_leads("cafe", location="London")
    assert leads == []


@respx.mock
def test_timeout_retry_circuit_breaker() -> None:
    connector = OSMOverpassConnector(failure_threshold=2)
    # Mock connection timeout
    respx.post("https://overpass-api.de/api/interpreter").mock(
        side_effect=RequestError("Connection timed out")
    )

    # Trigger failures to open circuit
    with pytest.raises(Exception):
        connector.search_leads("cafe", location="London")
    assert connector.failure_count == 1

    with pytest.raises(Exception):
        connector.search_leads("cafe", location="London")
    assert connector.failure_count == 2
    assert connector.is_circuit_open() is True

    # Blocked requests during open circuit
    assert connector.search_leads("cafe", location="London") == []


@respx.mock
def test_http_429_backoff() -> None:
    connector = OSMOverpassConnector()
    respx.post("https://overpass-api.de/api/interpreter").mock(
        return_value=Response(429, json={"error": "Too Many Requests"})
    )
    
    import time
    start = time.time()
    # Should attempt multiple retries with backoff and eventually fail
    with pytest.raises(ValueError) as exc:
        connector._execute_query("query")
    assert "PROVIDER_UNAVAILABLE" in str(exc.value)
    # Check that it waited for retries
    assert time.time() - start >= 2.0


@respx.mock
def test_http_5xx_retry() -> None:
    connector = OSMOverpassConnector()
    # Fail first request, succeed second
    route = respx.post("https://overpass-api.de/api/interpreter")
    route.side_effect = [
        Response(502, text="Bad Gateway"),
        Response(200, json={"elements": [{"type": "node", "id": 1, "tags": {"name": "Retry Cafe", "amenity": "cafe"}}]})
    ]

    leads = connector.search_leads("cafe", location="London")
    assert len(leads) == 1
    assert leads[0].business_name == "Retry Cafe"


def test_osm_overpass_integration() -> None:
    # A small real Overpass query or mock integration validation to check database pipeline insertion
    db = SessionLocal()
    from backend.app.models_phase2 import CanonicalLead, LeadObservation, LeadIdentity
    from backend.app.models import Lead, SourceRecord
    
    # 0. Pre-test cleanup to avoid duplicates from failed cleanup of previous runs
    obs_recs = db.query(LeadObservation).filter(LeadObservation.observed_business_name == "Overpass Green Dental").all()
    for o in obs_recs:
        db.delete(o)
        
    identities = db.query(LeadIdentity).filter(LeadIdentity.raw_signal == "Overpass Green Dental").all()
    for idx in identities:
        db.delete(idx)
        
    canonicals = db.query(CanonicalLead).filter(CanonicalLead.business_name == "Overpass Green Dental").all()
    for c in canonicals:
        db.delete(c)
        
    leads = db.query(Lead).filter(Lead.business_name == "Overpass Green Dental").all()
    for l in leads:
        db.delete(l)
    db.commit()

    resolver = LifecycleResolver()
    
    try:
        raw_lead = RawLead(
            source_name="osm_overpass",
            source_record_id="node/99887766",
            business_name="Overpass Green Dental",
            industry="dentist",
            address="15 Green Road",
            city="London",
            country="United Kingdom",
            phone="+44 77 9999 8888",
            website="http://greendental.co.uk",
            raw_payload={"type": "node", "id": 99887766, "tags": {"name": "Overpass Green Dental", "phone": "+44 77 9999 8888"}}
        )

        canonical, obs, l_state = resolver.process_observation(db, raw_lead)
        assert canonical is not None
        assert obs is not None
        assert l_state == LifecycleState.NEW
        
        # Verify it exists in database
        db.refresh(canonical)
        assert canonical.business_name == "Overpass Green Dental"
        assert canonical.canonical_phone == "+44 77 9999 8888"

        # Verify duplicate detection
        canonical2, obs2, l_state2 = resolver.process_observation(db, raw_lead)
        assert canonical2.id == canonical.id
        assert l_state2 == LifecycleState.DUPLICATE

    finally:
        # Cleanup created records to ensure database is perfectly clean
        obs_recs = db.query(LeadObservation).filter(LeadObservation.observed_business_name == "Overpass Green Dental").all()
        for o in obs_recs:
            db.delete(o)
            
        identities = db.query(LeadIdentity).filter(LeadIdentity.raw_signal == "Overpass Green Dental").all()
        for idx in identities:
            db.delete(idx)
            
        canonicals = db.query(CanonicalLead).filter(CanonicalLead.business_name == "Overpass Green Dental").all()
        for c in canonicals:
            db.delete(c)
            
        leads = db.query(Lead).filter(Lead.business_name == "Overpass Green Dental").all()
        for l in leads:
            db.delete(l)
            
        db.commit()
        db.close()


def test_query_expansion_restaurant_and_category_support() -> None:
    from backend.app.intelligence.query_expansion import QueryExpansionEngine
    connector = OSMOverpassConnector()
    engine = QueryExpansionEngine()

    expansions = engine.expand_query("restaurant", max_queries=5)
    query_terms = [e["query"] for e in expansions]

    # Expected expansions
    assert "restaurant" in query_terms
    assert "restaurants" in query_terms
    assert "cafe" in query_terms
    assert "eatery" in query_terms
    assert "bistro" in query_terms

    # Check category support on connector
    assert connector.supports_category("restaurant") is True
    assert connector.supports_category("restaurants") is True
    assert connector.supports_category("cafe") is True
    assert connector.supports_category("eatery") is False
    assert connector.supports_category("bistro") is False

    # Check query builder raises on unsupported
    bbox = [19.15, 19.16, 72.84, 72.85]
    with pytest.raises(ValueError) as exc1:
        connector._build_overpass_query("eatery", bbox)
    assert "UNSUPPORTED_CATEGORY" in str(exc1.value)

    with pytest.raises(ValueError) as exc2:
        connector._build_overpass_query("bistro", bbox)
    assert "UNSUPPORTED_CATEGORY" in str(exc2.value)


@respx.mock
def test_supported_vs_skipped_query_execution() -> None:
    connector = OSMOverpassConnector()
    bbox = [51.28676, 51.69187, -0.510375, 0.3340155]

    # Mock Overpass endpoint for cafe query
    respx.post("https://overpass-api.de/api/interpreter").mock(
        return_value=Response(200, json={
            "elements": [
                {"type": "node", "id": 101, "tags": {"name": "Supported Cafe", "amenity": "cafe"}}
            ]
        })
    )

    # 1. Supported query executes successfully
    leads = connector.search_leads("cafe", location="London")
    assert len(leads) == 1
    assert leads[0].business_name == "Supported Cafe"

    # 2. Zero-result query succeeds with empty list
    respx.post("https://overpass-api.de/api/interpreter").mock(
        return_value=Response(200, json={"elements": []})
    )
    zero_leads = connector.search_leads("bakery", location="London")
    assert zero_leads == []


def test_deduplication_across_multiple_queries() -> None:
    """Verifies that multiple category queries finding the same OSM element are deduplicated."""
    db = SessionLocal()
    resolver = LifecycleResolver()
    from backend.app.models_phase2 import CanonicalLead, LeadObservation, LeadIdentity

    name = "Dedup Test Resto"
    osm_id = "node/88889999"

    # Cleanup pre-test
    db.query(LeadObservation).filter(LeadObservation.source_record_id == osm_id).delete()
    db.query(LeadIdentity).filter(LeadIdentity.raw_signal == name).delete()
    db.query(CanonicalLead).filter(CanonicalLead.business_name == name).delete()
    db.commit()

    try:
        # Lead found by first query ('restaurant')
        raw1 = RawLead(
            source_name="osm_overpass",
            source_record_id=osm_id,
            business_name=name,
            industry="restaurant",
            address="123 Main Rd",
            city="Mumbai",
            country="India",
            phone="+91 22 12345678",
            website="https://deduptest.com",
            raw_payload={"type": "node", "id": 88889999, "tags": {"name": name, "amenity": "restaurant"}},
        )
        c1, obs1, state1 = resolver.process_observation(db, raw1)
        assert state1 == LifecycleState.NEW
        assert c1 is not None

        # Same lead found by second query ('restaurants' or 'cafe')
        raw2 = RawLead(
            source_name="osm_overpass",
            source_record_id=osm_id,
            business_name=name,
            industry="restaurant",
            address="123 Main Rd",
            city="Mumbai",
            country="India",
            phone="+91 22 12345678",
            website="https://deduptest.com",
            raw_payload={"type": "node", "id": 88889999, "tags": {"name": name, "amenity": "restaurant"}},
        )
        c2, obs2, state2 = resolver.process_observation(db, raw2)
        assert state2 == LifecycleState.DUPLICATE
        assert c2.id == c1.id

    finally:
        db.query(LeadObservation).filter(LeadObservation.source_record_id == osm_id).delete()
        db.query(LeadIdentity).filter(LeadIdentity.raw_signal == name).delete()
        db.query(CanonicalLead).filter(CanonicalLead.business_name == name).delete()
        db.commit()
        db.close()


def test_canonical_category_resolution() -> None:
    connector = OSMOverpassConnector()
    assert connector.get_canonical_category("restaurant") == "amenity=restaurant"
    assert connector.get_canonical_category("restaurants") == "amenity=restaurant"
    assert connector.get_canonical_category("cafe") == "amenity=cafe"
    assert connector.get_canonical_category("dentist") == "amenity=dentist"
    assert connector.get_canonical_category("dental clinic") == "amenity=dentist"
    assert connector.get_canonical_category("eatery") is None
    assert connector.get_canonical_category("bistro") is None


@respx.mock
def test_http_406_not_retried() -> None:
    connector = OSMOverpassConnector()
    route = respx.post("https://overpass-api.de/api/interpreter").mock(
        return_value=Response(406, text="Not Acceptable")
    )
    with pytest.raises(ValueError) as exc:
        connector._execute_query("test query")
    assert "406" in str(exc.value)
    # Must only attempt once (0 retries)
    assert route.call_count == 1


@respx.mock
def test_http_429_retry_after_header_handling() -> None:
    connector = OSMOverpassConnector()
    route = respx.post("https://overpass-api.de/api/interpreter")
    route.side_effect = [
        Response(429, headers={"Retry-After": "1"}, json={"error": "rate limit"}),
        Response(200, json={"elements": [{"type": "node", "id": 1, "tags": {"name": "After Rate Limit", "amenity": "cafe"}}]})
    ]
    leads = connector.search_leads("cafe", location="London")
    assert len(leads) == 1
    assert leads[0].business_name == "After Rate Limit"
    assert route.call_count == 2


@respx.mock
def test_http_504_bounded_retry() -> None:
    connector = OSMOverpassConnector()
    route = respx.post("https://overpass-api.de/api/interpreter").mock(
        return_value=Response(504, text="Gateway Timeout")
    )
    with pytest.raises(ValueError) as exc:
        connector._execute_query("test query")
    assert "504" in str(exc.value)
    # Bounded to max_retries + 1 = 3 attempts total
    assert route.call_count == 3


def test_early_stopping_on_target_lead_count() -> None:
    """Verifies that discovery stops once unique target leads count is reached."""
    from unittest.mock import MagicMock
    from backend.app.worker import execute_single_query_plan

    mock_db = MagicMock()
    mock_job = MagicMock()
    mock_job.leads_scraped = 5
    mock_job.target_lead_count = 5
    mock_job.status = "RUNNING"

    plan = {
        "source": "osm_overpass",
        "query": "restaurant",
        "reason": "exact niche",
        "location": "Mumbai",
        "niche": "restaurant",
    }
    # Should early-stop and return without calling connector
    execute_single_query_plan(mock_db, mock_job, plan)
    assert mock_job.leads_scraped == 5


