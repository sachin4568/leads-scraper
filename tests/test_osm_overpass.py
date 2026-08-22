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
    leads1 = connector.search_leads("cafe", location="London")
    assert leads1 == []
    assert connector.failure_count == 1

    leads2 = connector.search_leads("cafe", location="London")
    assert leads2 == []
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
