from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.feedback.productivity_pilot import ProductivityPilotEngine
from backend.app.ingestion.ingestion import DirectoryAdapter, GooglePlacesAdapter
from backend.app.ingestion.lifecycle import LifecycleResolver
from backend.app.ml.staging_engine import StagingModelEngine
from backend.app.models_phase2 import Base as BasePhase2
from backend.app.models_phase3 import Base as BasePhase3


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    BasePhase2.metadata.create_all(bind=engine)
    BasePhase3.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_staging_model_engine_prediction() -> None:
    engine = StagingModelEngine(alpha=0.10, threshold=0.50)
    output = engine.predict_lead("lead_test_01", [1.0, 1.0, 1.0, 3.0, 0.0])

    assert output.canonical_lead_id == "lead_test_01"
    assert output.model_name == "real_model_v2_ensemble"
    assert output.predicted_decision in ("GENUINE", "REJECTED")
    assert 0.0 <= output.predicted_probability <= 1.0


def test_deduplication_and_update_lifecycle_in_staging(db_session) -> None:
    resolver = LifecycleResolver()
    gp_adapter = GooglePlacesAdapter()

    payload = {
        "place_id": "ChIJ_staging_dedup_01",
        "name": "Staging Biz",
        "types": ["Dental Clinics"],
        "city": "Dehradun",
        "website": "https://www.stagingbiz.com",
        "formatted_phone_number": "+91 98970 55555",
    }
    raw = gp_adapter.normalize_payload(payload)

    # 1. New Ingestion
    c1, _, s1 = resolver.process_observation(db_session, raw)
    assert s1.value == "NEW"

    # 2. Repeat Ingestion -> DUPLICATE / EXISTING
    c2, _, s2 = resolver.process_observation(db_session, raw)
    assert c2.id == c1.id
    assert s2.value in ("EXISTING", "DUPLICATE")

    # 3. Ingest from secondary source with modified phone -> UPDATED
    dir_adapter = DirectoryAdapter()
    payload_mod = {
        "place_id": "ChIJ_staging_dedup_01_v2",
        "name": "Staging Biz",
        "types": ["Dental Clinics"],
        "city": "Dehradun",
        "website": "https://www.stagingbiz.com",
        "formatted_phone_number": "+91 99999 88888",
    }
    raw_mod = dir_adapter.normalize_payload(payload_mod)
    c3, _, s3 = resolver.process_observation(db_session, raw_mod)
    assert c3.id == c1.id
    assert s3.value == "UPDATED"


def test_productivity_pilot_logging_and_separation() -> None:
    pilot = ProductivityPilotEngine()
    pilot.log_outreach_event("lead_prod_01", True, True, True, "PRODUCTIVE", "CLOSED")
    pilot.log_outreach_event("lead_prod_02", True, True, False, "UNPRODUCTIVE", "REJECTED")

    summary = pilot.get_summary_metrics(total_leads_count=10)
    assert summary["outreach_attempted_count"] == 2
    assert summary["productive_count"] == 1
    assert summary["unproductive_count"] == 1
    assert summary["not_attempted_count"] == 8
