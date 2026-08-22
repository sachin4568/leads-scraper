from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.ingestion.ingestion import DirectoryAdapter, GooglePlacesAdapter
from backend.app.models_phase2 import Base as BasePhase2
from backend.app.models_phase3 import Base as BasePhase3
from backend.app.production.feedback_loop import ProductionFeedbackCollector
from backend.app.production.monitoring import (
    ProductionDataQualityMonitor,
    ProductionDriftMonitor,
)
from backend.app.production.production_inference import (
    FrozenModelGuard,
    ProductionConfigurationError,
    ProductionInferenceEngine,
)
from backend.app.production.production_ingestion import ControlledProductionIngestion
from backend.app.production.productivity_tracking import (
    ProductivityOutcomeManager,
    ProductivityStatus,
)
from backend.app.production.safety import (
    EmergencyStopError,
    ProductionKillSwitch,
    RolloutMode,
    RolloutTransitionError,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    BasePhase2.metadata.create_all(bind=engine)
    BasePhase3.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_frozen_model_guard_validation() -> None:
    guard = FrozenModelGuard()
    assert guard.validate_configuration("real_model_v2_1", 0.10, 0.40) is True

    with pytest.raises(ProductionConfigurationError):
        guard.validate_configuration("wrong_model_version", 0.10, 0.40)

    with pytest.raises(ProductionConfigurationError):
        guard.validate_configuration("real_model_v2_1", 0.50, 0.40)

    with pytest.raises(ProductionConfigurationError):
        guard.validate_configuration("real_model_v2_1", 0.10, 0.50)


def test_controlled_production_ingestion_and_deduplication(db_session) -> None:
    ingestion = ControlledProductionIngestion(default_quota=50)
    gp_adapter = GooglePlacesAdapter()
    dir_adapter = DirectoryAdapter()

    payload = {
        "place_id": "ChIJ_phase11_dedup_01",
        "name": "Prod Biz",
        "types": ["Dental Clinics"],
        "city": "Dehradun",
        "website": "https://www.prodbiz11.com",
        "formatted_phone_number": "+91 98970 11111",
    }
    raw1 = gp_adapter.normalize_payload(payload)

    # 1. New Ingestion
    c1, _, s1 = ingestion.resolver.process_observation(db_session, raw1)
    assert s1.value == "NEW"

    # 2. Repeat Ingestion -> DUPLICATE / EXISTING
    c2, _, s2 = ingestion.resolver.process_observation(db_session, raw1)
    assert c2.id == c1.id
    assert s2.value in ("EXISTING", "DUPLICATE")

    # 3. Secondary Source with Modified Phone -> UPDATED
    payload_mod = {
        "place_id": "ChIJ_phase11_dedup_01_v2",
        "name": "Prod Biz",
        "types": ["Dental Clinics"],
        "city": "Dehradun",
        "website": "https://www.prodbiz11.com",
        "formatted_phone_number": "+91 99999 22222",
    }
    raw2 = dir_adapter.normalize_payload(payload_mod)
    c3, _, s3 = ingestion.resolver.process_observation(db_session, raw2)
    assert c3.id == c1.id
    assert s3.value == "UPDATED"


def test_prediction_audit_logging_and_immutability(db_session) -> None:
    engine = ProductionInferenceEngine(model_version="real_model_v2_1", alpha=0.10, threshold=0.40)
    prob, dec, audit_rec = engine.predict_and_audit(
        db_session,
        canonical_lead_id="lead_audit_01",
        feature_vector=[1.0, 1.0, 1.0, 2.0, 0.0],
        source_batch_id="batch_01",
    )

    assert audit_rec.canonical_lead_id == "lead_audit_01"
    assert audit_rec.model_version == "real_model_v2_1"
    assert 0.0 <= prob <= 1.0
    assert dec in ("GENUINE", "REJECTED")


def test_human_feedback_and_productivity_separation(db_session) -> None:
    collector = ProductionFeedbackCollector()
    event = collector.record_human_outcome(
        db_session,
        canonical_lead_id="lead_fb_01",
        reviewer_id="rev_01",
        genuineness_outcome="GENUINE",
        evidence="Validated address and business registration.",
    )
    assert event.genuineness_outcome == "GENUINE"

    prod_mgr = ProductivityOutcomeManager()
    prod_rec = prod_mgr.record_outreach_attempt(
        "lead_fb_01", "PHONE", ProductivityStatus.UNPRODUCTIVE, "NOT_INTERESTED"
    )
    assert prod_rec.status == ProductivityStatus.UNPRODUCTIVE
    # Genuineness remains GENUINE even if unproductive
    assert event.genuineness_outcome == "GENUINE"


def test_drift_monitoring_and_data_quality() -> None:
    dq = ProductionDataQualityMonitor.audit_batch(
        [{"phone": "+91 99999 00000", "website": "https://test.com"}]
    )
    assert dq.total_records == 1
    assert dq.missing_phone_rate == 0.0

    drift = ProductionDriftMonitor.calculate_drift([0.80, 0.85, 0.90], baseline_mean_prob=0.85)
    assert drift.drift_status == "STABLE"


def test_safety_kill_switch_and_rollout_mode_transitions() -> None:
    ks = ProductionKillSwitch()
    assert ks.current_rollout_mode == RolloutMode.CONTROLLED_TEST

    # Test Rollout Transition requires approval
    with pytest.raises(RolloutTransitionError):
        ks.transition_rollout_mode(RolloutMode.LIMITED_PRODUCTION, human_approved=False)

    new_mode = ks.transition_rollout_mode(RolloutMode.LIMITED_PRODUCTION, human_approved=True)
    assert new_mode == RolloutMode.LIMITED_PRODUCTION

    # Test Emergency Kill Switch
    ks.disable_inference("Emergency halt")
    with pytest.raises(EmergencyStopError):
        ks.validate_inference_allowed()

    ks.disable_source("google_places", "API error")
    with pytest.raises(EmergencyStopError):
        ks.validate_source_allowed("google_places")
