from __future__ import annotations

import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.feedback.active_learning import ActiveLearningEngine
from backend.app.feedback.dataset_exporter import FeedbackDatasetExporter, TemporalLeakageError
from backend.app.feedback.feedback_validation import (
    ContactabilityOutcome,
    FeedbackQualityValidator,
    FeedbackState,
    GenuinenessOutcome,
    HumanOutcomeEventInput,
    ProductivityOutcome,
    QualificationOutcome,
    ServiceOpportunityFlag,
    WebsiteReviewState,
)
from backend.app.models_phase3 import Base, HumanOutcomeEvent, PredictionHistoryRecord


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_prediction_history_immutability(db_session) -> None:
    t_feat = datetime.datetime.utcnow() - datetime.timedelta(seconds=10)
    t_pred = datetime.datetime.utcnow() - datetime.timedelta(seconds=5)

    pred = PredictionHistoryRecord(
        canonical_lead_id="lead_immut_001",
        model_name="CatBoost_LightGBM_Ensemble",
        model_version="v1.1_phase1_stratified",
        feature_version="v1.0_allowlist",
        predicted_probability=0.89,
        predicted_decision="GENUINE",
        operating_threshold=0.50,
        feature_snapshot_timestamp=t_feat,
        prediction_timestamp=t_pred,
    )
    db_session.add(pred)
    db_session.commit()

    # Human review decision
    evt = HumanOutcomeEvent(
        canonical_lead_id="lead_immut_001",
        prediction_id=pred.id,
        genuineness_outcome="GENUINE",
        contactability_outcome="OWNER_CONTACT",
        productivity_outcome="UNPRODUCTIVE",
        qualification_outcome="NOT_QUALIFIED",
        service_opportunity_flags='["NO_CLEAR_OPPORTUNITY"]',
        website_review_state="ACTIVE_GOOD",
        reason_code="already_has_provider",
        feedback_state="VALIDATED",
    )
    db_session.add(evt)
    db_session.commit()

    # Assert PredictionHistoryRecord remains 100% untouched
    stored_pred = (
        db_session.query(PredictionHistoryRecord)
        .filter(PredictionHistoryRecord.id == pred.id)
        .first()
    )
    assert stored_pred.predicted_probability == 0.89
    assert stored_pred.predicted_decision == "GENUINE"
    assert stored_pred.model_version == "v1.1_phase1_stratified"


def test_productivity_separated_from_genuineness(db_session) -> None:
    inp = HumanOutcomeEventInput(
        canonical_lead_id="lead_prod_001",
        genuineness_outcome=GenuinenessOutcome.GENUINE,
        contactability_outcome=ContactabilityOutcome.OWNER_CONTACT,
        productivity_outcome=ProductivityOutcome.UNPRODUCTIVE,
        qualification_outcome=QualificationOutcome.NOT_QUALIFIED,
        service_opportunity_flags=[ServiceOpportunityFlag.NO_CLEAR_OPPORTUNITY],
        website_review_state=WebsiteReviewState.ACTIVE_GOOD,
        reason_code="already_has_provider",
    )
    is_valid, msg, fstate = FeedbackQualityValidator.validate_feedback_input(inp)
    assert is_valid is True
    assert fstate == FeedbackState.VALIDATED


def test_multi_label_service_opportunity_support(db_session) -> None:
    inp = HumanOutcomeEventInput(
        canonical_lead_id="lead_multilabel_001",
        genuineness_outcome=GenuinenessOutcome.GENUINE,
        contactability_outcome=ContactabilityOutcome.OWNER_CONTACT,
        productivity_outcome=ProductivityOutcome.PRODUCTIVE,
        qualification_outcome=QualificationOutcome.QUALIFIED,
        service_opportunity_flags=[
            ServiceOpportunityFlag.WEBSITE,
            ServiceOpportunityFlag.SEO,
            ServiceOpportunityFlag.SMMA,
        ],
        website_review_state=WebsiteReviewState.ACTIVE_NEEDS_IMPROVEMENT,
    )
    assert len(inp.service_opportunity_flags) == 3
    assert ServiceOpportunityFlag.WEBSITE in inp.service_opportunity_flags
    assert ServiceOpportunityFlag.SEO in inp.service_opportunity_flags


def test_temporal_ordering_leakage_prevention(db_session) -> None:
    # Invalid timestamp sequence: feature snapshot AFTER prediction
    t_feat = datetime.datetime.utcnow()
    t_pred = datetime.datetime.utcnow() - datetime.timedelta(seconds=10)
    t_out = datetime.datetime.utcnow() + datetime.timedelta(seconds=10)

    pred = PredictionHistoryRecord(
        canonical_lead_id="lead_temp_001",
        model_name="Ensemble",
        model_version="v1.1",
        feature_version="v1.0",
        predicted_probability=0.80,
        predicted_decision="GENUINE",
        feature_snapshot_timestamp=t_feat,
        prediction_timestamp=t_pred,
    )
    db_session.add(pred)
    db_session.commit()

    evt = HumanOutcomeEvent(
        canonical_lead_id="lead_temp_001",
        prediction_id=pred.id,
        genuineness_outcome="GENUINE",
        contactability_outcome="OWNER_CONTACT",
        productivity_outcome="PRODUCTIVE",
        qualification_outcome="QUALIFIED",
        service_opportunity_flags='["WEBSITE"]',
        feedback_state="VALIDATED",
        human_outcome_timestamp=t_out,
    )
    db_session.add(evt)
    db_session.commit()

    exporter = FeedbackDatasetExporter()
    with pytest.raises(TemporalLeakageError) as exc_info:
        exporter.export_genuineness_dataset(db_session, dataset_version="test_temp_v1.0")
    assert "Temporal leakage detected" in str(exc_info.value)


def test_active_learning_multi_factor_ranking_and_duplicate_suppression(db_session) -> None:
    engine = ActiveLearningEngine()

    cand1 = engine.evaluate_and_enqueue_candidate(
        db_session,
        "lead_al_001",
        "Dental Clinics",
        "Dehradun",
        prob_catboost=0.51,
        prob_lightgbm=0.49,
        identity_ambiguity=True,
    )
    cand2 = engine.evaluate_and_enqueue_candidate(
        db_session,
        "lead_al_002",
        "Dental Clinics",
        "Dehradun",
        prob_catboost=0.95,
        prob_lightgbm=0.90,
        identity_ambiguity=False,
    )

    assert cand1.composite_priority_score > cand2.composite_priority_score

    # Duplicate candidate re-enqueue returns existing candidate
    cand1_repeat = engine.evaluate_and_enqueue_candidate(
        db_session,
        "lead_al_001",
        "Dental Clinics",
        "Dehradun",
        prob_catboost=0.51,
        prob_lightgbm=0.49,
        identity_ambiguity=True,
    )
    assert cand1_repeat is not None
    assert cand1_repeat.selection_count == 2


def test_post_prediction_leakage_denial_check() -> None:
    from backend.app.feedback.dataset_exporter import POST_PREDICTION_LEAKAGE_FIELDS

    forbidden_fields = {
        "human_outcome",
        "productivity_outcome",
        "qualification_outcome",
        "sales_result",
        "later_audit_result",
    }
    for f in forbidden_fields:
        assert f in POST_PREDICTION_LEAKAGE_FIELDS


def test_active_learning_diversity_quotas(db_session) -> None:
    engine = ActiveLearningEngine()
    for i in range(10):
        engine.evaluate_and_enqueue_candidate(
            db_session,
            f"lead_niche_{i}",
            "Dental Clinics",
            "Dehradun",
            prob_catboost=0.51,
            prob_lightgbm=0.49,
        )
    for i in range(5):
        engine.evaluate_and_enqueue_candidate(
            db_session,
            f"lead_plumbing_{i}",
            "Plumbing Contractors",
            "Mohali",
            prob_catboost=0.53,
            prob_lightgbm=0.47,
        )

    queue = engine.get_prioritized_queue(db_session, limit=10, max_per_niche=3)
    niche_counts = {}
    for item in queue:
        niche_counts[item.niche] = niche_counts.get(item.niche, 0) + 1

    assert niche_counts.get("Dental Clinics", 0) <= 3
    assert niche_counts.get("Plumbing Contractors", 0) <= 3
