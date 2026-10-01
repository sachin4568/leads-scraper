from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.ingestion.ingestion import RawLead
from backend.app.ingestion.identity import CanonicalIdentityEngine, IdentityConfidence
from backend.app.ingestion.lifecycle import LifecycleResolver, LifecycleState
from backend.app.models import SourceRecord, Workspace
from backend.app.models_phase2 import Base as Phase2Base
from backend.app.models_phase2 import CanonicalLead, LeadObservation


@pytest.fixture
def db_session_and_engine():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Phase2Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    ws = Workspace(name="Test Workspace")
    session.add(ws)
    session.commit()
    session.refresh(ws)
    yield session, engine, ws
    session.close()


def test_bounded_sql_query_count_and_no_nplusone(db_session_and_engine):
    """Proves that resolve_identity executes a bounded, constant number of SQL queries regardless of candidate count."""
    session, engine, ws = db_session_and_engine
    resolver = LifecycleResolver()

    # Seed 30 existing CanonicalLeads with SourceRecords and observations
    for i in range(30):
        raw = RawLead(
            source_name="osm_overpass",
            business_name=f"Existing Business {i}",
            industry="restaurant",
            source_record_id=f"node/seed_{i}",
            website=f"https://business{i}.com",
            phone=f"+91 98000000{i:02d}",
            address=f"Location {i}, Mumbai",
            city="Mumbai",
            country="India",
            raw_payload={"lat": 19.15 + (i * 0.001), "lon": 72.85 + (i * 0.001)},
        )
        c, obs, _ = resolver.process_observation(session, raw)
        src_rec = SourceRecord(
            workspace_id=ws.id,
            source=raw.source_name,
            source_id=raw.source_record_id,
            raw_data=raw.raw_payload,
        )
        session.add(src_rec)
        session.commit()

    total_canonicals = session.query(CanonicalLead).count()
    assert total_canonicals == 30

    engine_instance = CanonicalIdentityEngine()

    # Test incoming lead with coordinates
    incoming = RawLead(
        source_name="osm_overpass",
        business_name="Unseen New Cafe",
        industry="restaurant",
        source_record_id="node/new_101",
        website="https://newcafe.com",
        phone="+91 9999999999",
        address="Goregaon, Mumbai",
        city="Mumbai",
        country="India",
        raw_payload={"lat": 19.16, "lon": 72.85},
    )

    query_count = 0

    def query_listener(conn, cursor, statement, parameters, context, executemany):
        nonlocal query_count
        query_count += 1

    event.listen(engine, "before_cursor_execute", query_listener)

    # First resolution: Should only emit 2 queries (1 for CanonicalLead+joined observations, 1 for batch SourceRecords)
    # NOT 1 + 30 + 30 = 61 queries!
    matched, explanation = engine_instance.resolve_identity(session, incoming)

    assert matched is None
    assert explanation.match_level == IdentityConfidence.NO_MATCH
    assert query_count <= 2, f"Expected <= 2 queries, got {query_count}"

    # Second resolution with another lead: Should use memory cache, emitting only 1 query for CanonicalLead
    query_count = 0
    incoming2 = RawLead(
        source_name="osm_overpass",
        business_name="Another New Cafe",
        industry="restaurant",
        source_record_id="node/new_102",
        website="https://anothercafe.com",
        phone="+91 8888888888",
        city="Mumbai",
        country="India",
        raw_payload={"lat": 19.17, "lon": 72.86},
    )
    matched2, explanation2 = engine_instance.resolve_identity(session, incoming2)
    assert matched2 is None
    assert query_count == 1, f"Expected exactly 1 query on cached candidates, got {query_count}"

    event.remove(engine, "before_cursor_execute", query_listener)


def test_identity_matching_accuracy_and_signals(db_session_and_engine):
    """Verifies that high-confidence matching, duplicate detection, and signal explanations remain exact."""
    session, _, ws = db_session_and_engine
    resolver = LifecycleResolver()

    raw1 = RawLead(
        source_name="osm_overpass",
        business_name="Goregaon Delights Cafe",
        industry="restaurant",
        source_record_id="node/gd_1",
        website="https://goregondelights.com",
        phone="+91 9820112233",
        city="Mumbai",
        country="India",
        raw_payload={"lat": 19.165, "lon": 72.845},
    )
    c1, obs1, s1 = resolver.process_observation(session, raw1)
    assert s1 == LifecycleState.NEW
    src1 = SourceRecord(workspace_id=ws.id, source=raw1.source_name, source_id=raw1.source_record_id, raw_data=raw1.raw_payload)
    session.add(src1)
    session.commit()

    # Match by phone + similar name + proximity
    engine = CanonicalIdentityEngine()
    raw2 = RawLead(
        source_name="google_places",
        business_name="Goregaon Delights",
        industry="restaurant",
        source_record_id="ChIJ_gd_2",
        website="https://goregondelights.com",
        phone="+91 9820112233",
        city="Mumbai",
        country="India",
        raw_payload={"lat": 19.1651, "lon": 72.8451},
    )
    matched, exp = engine.resolve_identity(session, raw2)
    assert matched is not None
    assert matched.id == c1.id
    assert exp.match_level in (IdentityConfidence.HIGH_CONFIDENCE_MATCH, IdentityConfidence.EXACT_MATCH)
    assert "exact_phone" in exp.matched_signals
    assert "exact_domain" in exp.matched_signals


def test_missing_coordinates_handled_safely(db_session_and_engine):
    """Verifies that leads without coordinates fallback to city/state match safely without crashing."""
    session, _, _ = db_session_and_engine
    resolver = LifecycleResolver()

    raw_no_geo = RawLead(
        source_name="osm_overpass",
        business_name="No Geo Restaurant",
        industry="restaurant",
        source_record_id="node/no_geo_1",
        website="https://nogeo.com",
        phone="+91 9111122222",
        city="Mumbai",
        country="India",
        raw_payload=None,
    )
    c, obs, s = resolver.process_observation(session, raw_no_geo)
    assert s == LifecycleState.NEW

    engine = CanonicalIdentityEngine()
    raw_query = RawLead(
        source_name="yelp",
        business_name="Different Place",
        industry="restaurant",
        source_record_id="yelp/diff_1",
        website="https://differentplace.com",
        phone="+91 9333344444",
        city="Mumbai",
        country="India",
        raw_payload=None,
    )
    matched, exp = engine.resolve_identity(session, raw_query)
    assert matched is None
    assert exp.match_level == IdentityConfidence.NO_MATCH
