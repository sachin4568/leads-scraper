import uuid
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from backend.app.models import Base as BasePhase1
from backend.app.models_phase2 import Base as BasePhase2, CanonicalLead, LeadObservation
from backend.app.ingestion.ingestion import RawLead
from backend.app.ingestion.lifecycle import LifecycleResolver

engine = create_engine("sqlite:///:memory:")
SessionLocal = sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    BasePhase1.metadata.create_all(engine)
    BasePhase2.metadata.create_all(engine)
    yield
    BasePhase2.metadata.drop_all(engine)
    BasePhase1.metadata.drop_all(engine)


def test_conflict_tracking_in_entity_resolution():
    db = SessionLocal()
    resolver = LifecycleResolver()

    # Step 1: Ingest observation from Source A
    lead_a = RawLead(
        source_name="source_a",
        source_record_id="rec_1",
        business_name="Dental Care Clinic",
        industry="Dentist",
        address="123 Main St",
        city="San Jose",
        country="US",
        website="https://dentalcare.com",
        phone="+14081112222",
        raw_payload={},
    )
    
    canonical_a, obs_a, state_a = resolver.process_observation(db, lead_a)
    db.add(canonical_a)
    db.commit()

    # Step 2: Ingest differing observation from Source B resolving to same canonical profile
    # Matches on phone, conflicts on website
    lead_b = RawLead(
        source_name="source_b",
        source_record_id="rec_2",
        business_name="Dental Care Clinic",
        industry="Dentist",
        address="123 Main St",
        city="San Jose",
        country="US",
        website="https://dental-care-clinic.com",  # Conflict!
        phone="+14081112222",                      # Same phone to match
        raw_payload={},
    )
    
    canonical_b, obs_b, state_b = resolver.process_observation(db, lead_b)
    db.commit()

    # Fetch fresh record and assert conflicts are populated
    refreshed_canonical = db.scalar(
        select(CanonicalLead).where(CanonicalLead.id == canonical_a.id)
    )

    assert refreshed_canonical.conflicts is not None
    assert "website" in refreshed_canonical.conflicts

    # Assert details
    website_conf = refreshed_canonical.conflicts["website"]
    assert website_conf["conflict"] is True
    assert website_conf["canonical_value"] == "https://dentalcare.com"
    assert website_conf["evidence"]["source_a"] == "https://dentalcare.com"
    assert website_conf["evidence"]["source_b"] == "https://dental-care-clinic.com"

    db.close()
