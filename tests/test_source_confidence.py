import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.models import Base as BasePhase1
from backend.app.models_phase2 import Base as BasePhase2, LeadObservation
from backend.app.intelligence.source_confidence import SourceConfidenceSystem

engine = create_engine("sqlite:///:memory:")
SessionLocal = sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    BasePhase1.metadata.create_all(engine)
    BasePhase2.metadata.create_all(engine)
    yield
    BasePhase2.metadata.drop_all(engine)
    BasePhase1.metadata.drop_all(engine)


def test_dynamic_source_confidence_calculations():
    db = SessionLocal()

    # Create dummy observations
    obs_1 = LeadObservation(
        canonical_lead_id="lead_1",
        source_name="google_places",
        source_record_id="sp_1",
        observed_phone="+1234567890",
        observed_website="https://google.com"
    )
    obs_2 = LeadObservation(
        canonical_lead_id="lead_1",
        source_name="osm_overpass",
        source_record_id="osm_1",
        observed_phone="+1234567890",
        observed_website="https://google.com"
    )

    observations = [obs_1, obs_2]

    # Scenario 1: Phone is confirmed by 2 distinct sources (Google & OSM), validation passed
    phone_conf = SourceConfidenceSystem.calculate_field_confidence(
        db,
        field_name="phone",
        field_value="+1234567890",
        observations=observations,
        validation_passed=True,
        validation_score=90
    )
    # Average acceptance rate (default 1.0) * 80 = 80
    # Cross-source bonus (2 sources) = +10
    # Validation passed bonus = +15
    # Validation score contribution (90/100 * 10) = +9
    # Total = 80 + 10 + 15 + 9 = 114, capped at 100
    assert phone_conf == 100

    # Scenario 2: Website observed by only 1 source, validation failed
    website_conf = SourceConfidenceSystem.calculate_field_confidence(
        db,
        field_name="website",
        field_value="https://google.com",
        observations=[obs_1],  # only 1 source
        validation_passed=False,
        validation_score=0
    )
    # Average rate * 80 = 80
    # Cross-source bonus (1 source) = 0
    # Validation failed penalty = -10
    # Total = 70
    assert website_conf == 70

    db.close()
