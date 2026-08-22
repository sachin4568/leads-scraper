from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.enrichment.entity_resolution import EntityResolver
from backend.app.models import Lead, SourceRecord, Workspace


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        yield session


def test_domain_and_name_normalization() -> None:
    assert EntityResolver.normalize_domain("https://www.dentalcare.com/about") == "dentalcare.com"
    assert EntityResolver.normalize_domain("http://clinic.org/") == "clinic.org"

    assert EntityResolver.normalize_name("Smile Care Dental LLC") == "smile care dental"
    assert EntityResolver.normalize_name("Metro Plumbers Inc.") == "metro plumbers"


def test_match_score_calculation() -> None:
    lead1 = Lead(
        business_name="Smile Dental", website="https://smiledental.com", phone="+14155552671"
    )
    lead2 = Lead(
        business_name="Smile Dental Care",
        website="http://www.smiledental.com",
        phone="+14155559999",
    )

    # Domain match score
    score = EntityResolver.calculate_match_score(lead1, lead2)
    assert score == 1.0


def test_find_duplicate_leads_and_merge(db_session) -> None:
    ws_id = uuid.uuid4()
    ws = Workspace(id=ws_id, name="Resolution Workspace")
    db_session.add(ws)
    db_session.commit()

    lead_a = Lead(
        workspace_id=ws_id,
        business_name="City Dental Clinic",
        website="https://citydental.com",
        phone="+14155551111",
    )
    lead_b = Lead(
        workspace_id=ws_id,
        business_name="City Dental Clinic Inc",
        website="http://www.citydental.com",
        email="info@citydental.com",
    )
    db_session.add_all([lead_a, lead_b])
    db_session.commit()

    # Add source record linked to lead_b
    src_rec = SourceRecord(
        workspace_id=ws_id, lead_id=lead_b.id, source="yelp", source_id="yelp-123"
    )
    db_session.add(src_rec)
    db_session.commit()

    resolver = EntityResolver()

    # Find duplicates
    dupes = resolver.find_duplicate_leads(db_session, ws_id, lead_a)
    assert len(dupes) == 1
    assert dupes[0][0].id == lead_b.id
    assert dupes[0][1] == 1.0

    # Merge duplicate into primary lead
    merged = resolver.merge_leads(db_session, lead_a, lead_b)
    assert merged.id == lead_a.id
    assert merged.email == "info@citydental.com"  # Fills missing email from lead_b

    # Verify source record reassigned to primary lead
    db_session.refresh(src_rec)
    assert src_rec.lead_id == lead_a.id

    # Verify duplicate lead is soft-deleted
    db_session.refresh(lead_b)
    assert lead_b.deleted_at is not None
