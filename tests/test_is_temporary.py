from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.ingestion.ingestion import RawLead
from backend.app.ingestion.lifecycle import LifecycleResolver, LifecycleState
from backend.app.models_phase2 import Base, CanonicalLead, LeadObservation


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_is_temporary_initial_and_promotion(db_session) -> None:
    resolver = LifecycleResolver()

    # 1. First observation (from google_places) -> should create a temporary CanonicalLead
    raw1 = RawLead(
        source_name="google_places",
        business_name="Apex Solar Systems",
        industry="Solar",
        source_record_id="g_place_solar_1",
        website="https://www.apexsolarsystems.com",
        phone="+1 512 555 9988",
        city="Austin",
    )
    c1, obs1, s1 = resolver.process_observation(db_session, raw1)
    assert s1 == LifecycleState.NEW
    assert c1.is_temporary is True

    # 2. Second observation from same provider (google_places) -> should not promote
    raw2 = RawLead(
        source_name="google_places",
        business_name="Apex Solar Systems",
        industry="Solar",
        source_record_id="g_place_solar_2",
        website="https://www.apexsolarsystems.com",
        phone="+1 512 555 9988",
        city="Austin",
    )
    c2, obs2, s2 = resolver.process_observation(db_session, raw2)
    assert s2 == LifecycleState.EXISTING
    assert c2.id == c1.id
    assert c2.is_temporary is True

    # 3. Third observation from a different provider (yelp) -> should promote to permanent
    raw3 = RawLead(
        source_name="yelp",
        business_name="Apex Solar",
        industry="Solar",
        source_record_id="yelp_solar_1",
        website="https://www.apexsolarsystems.com",
        phone="+1 512 555 9988",
        city="Austin",
    )
    c3, obs3, s3 = resolver.process_observation(db_session, raw3)
    assert s3 == LifecycleState.EXISTING
    assert c3.id == c1.id
    assert c3.is_temporary is False
