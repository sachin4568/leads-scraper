from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.ingestion.ingestion import RawLead
from backend.app.ingestion.lifecycle import LifecycleResolver, LifecycleState
from backend.app.models_phase2 import Base as Phase2Base
from backend.app.models_phase2 import CanonicalLead, LeadObservation


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Phase2Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_cross_provider_identity_resolution_single_canonical_lead(db_session):
    """Verifies 3 different providers scraping the same business resolve into 1 CanonicalLead."""
    resolver = LifecycleResolver()

    # 1. Google Places Observation
    g_lead = RawLead(
        source_name="google_places",
        business_name="Apex Solar Systems",
        industry="Solar",
        source_record_id="g_place_solar_100",
        website="https://www.apexsolarsystems.com",
        phone="+1 512 555 9988",
        address="500 Innovation Way",
        city="Austin",
        state="TX",
        country="United States",
    )
    c1, obs1, s1 = resolver.process_observation(db_session, g_lead)
    assert s1 == LifecycleState.NEW
    assert c1.business_name == "Apex Solar Systems"
    canonical_id = c1.id

    # 2. Foursquare Observation (Same domain & phone)
    fsq_lead = RawLead(
        source_name="foursquare",
        business_name="Apex Solar Systems Inc",
        industry="Solar",
        source_record_id="fsq_solar_100",
        website="https://www.apexsolarsystems.com",
        phone="+1 512 555 9988",
        address="500 Innovation Way Suite A",
        city="Austin",
        state="TX",
        country="United States",
    )
    c2, obs2, s2 = resolver.process_observation(db_session, fsq_lead)
    assert s2 == LifecycleState.EXISTING
    assert c2.id == canonical_id

    # 3. Data Axle Observation (Same domain & phone)
    da_lead = RawLead(
        source_name="data_axle",
        business_name="Apex Solar",
        industry="Solar",
        source_record_id="da_solar_100",
        website="https://www.apexsolarsystems.com",
        phone="+1 512 555 9988",
        city="Austin",
        state="TX",
        country="United States",
    )
    c3, obs3, s3 = resolver.process_observation(db_session, da_lead)
    assert s3 == LifecycleState.EXISTING
    assert c3.id == canonical_id

    # Total Canonical Leads in DB must remain exactly 1
    total_canonicals = db_session.query(CanonicalLead).count()
    assert total_canonicals == 1

    # Total observations attached to this canonical lead must be 3
    observations = (
        db_session.query(LeadObservation)
        .filter(LeadObservation.canonical_lead_id == canonical_id)
        .all()
    )
    assert len(observations) == 3
    sources = {obs.source_name for obs in observations}
    assert sources == {"google_places", "foursquare", "data_axle"}
