from __future__ import annotations

import pytest

from backend.app.ml.productivity_readiness import TemporalLeakageError
from backend.app.production.productivity_expansion import (
    InterRaterProductivityReviewManager,
    ProductivityExpansionManager,
    ProductivityExpansionReadinessClassifier,
    ProductivityOutcomeEngine,
    SelectionBiasMonitor,
)
from backend.app.production.productivity_expansion_exporter import ProductivityExpansionExporter
from backend.app.production.productivity_expansion_leakage import (
    ProductivityExpansionLeakageAuditor,
)
from backend.app.production.productivity_ground_truth import FinalOutcome, OutreachState


def test_candidate_sampling_diversity() -> None:
    mgr = ProductivityExpansionManager()
    lead_pool = [
        {
            "canonical_lead_id": f"lead_{i}",
            "probability": 0.85 if i % 2 == 0 else 0.45,
            "niche": "Solar",
        }
        for i in range(20)
    ]
    sampled = mgr.sample_candidates("batch_test", lead_pool, sample_size=10)
    assert len(sampled) == 10
    assert sampled[0].candidate_probability_band == "HIGH"
    assert sampled[1].candidate_probability_band == "MEDIUM"


def test_productivity_outcome_recording_and_dimension_separation() -> None:
    engine = ProductivityOutcomeEngine()
    rec = engine.record_productivity_outcome(
        canonical_lead_id="lead_p13b_01",
        prediction_id="pred_01",
        outreach_batch_id="batch_A",
        reviewer_id="rev_1",
        outreach_state=OutreachState.OWNER_REACHED,
        final_productivity_outcome=FinalOutcome.PRODUCTIVE,
        feature_snapshot_timestamp="2026-08-13T10:00:00+00:00",
        prediction_timestamp="2026-08-13T10:00:05+00:00",
    )
    assert rec.final_productivity_outcome == FinalOutcome.PRODUCTIVE
    # OutreachState != FinalOutcome
    assert rec.outreach_state == OutreachState.OWNER_REACHED


def test_double_review_kappa_evaluation() -> None:
    r1 = ["PRODUCTIVE"] * 20 + ["UNPRODUCTIVE"] * 20
    r2 = ["PRODUCTIVE"] * 18 + ["UNPRODUCTIVE"] * 2 + ["UNPRODUCTIVE"] * 20

    res = InterRaterProductivityReviewManager.evaluate_double_review(r1, r2)
    assert res.target_passed is True
    assert res.cohens_kappa >= 0.75
    assert res.classification == "SUBSTANTIAL"


def test_selection_bias_monitor() -> None:
    out_probs = [0.85] * 100
    ctrl_probs = [0.85] * 100

    bias = SelectionBiasMonitor.evaluate_selection_bias(out_probs, ctrl_probs)
    assert bias["classification"] == "SELECTION_BIAS_LOW"
    assert bias["standardized_mean_diff"] == 0.0


def test_expansion_temporal_leakage_auditor() -> None:
    valid_recs = [
        {"canonical_lead_id": "lead_1", "prediction_time_features": {"phone_validity": 1.0}}
    ]
    assert (
        ProductivityExpansionLeakageAuditor.audit_expansion_candidates(valid_recs)["audit_passed"]
        is True
    )

    leaked_recs = [
        {"canonical_lead_id": "lead_2", "prediction_time_features": {"owner_reached": True}}
    ]
    with pytest.raises(TemporalLeakageError):
        ProductivityExpansionLeakageAuditor.audit_expansion_candidates(leaked_recs)


def test_productivity_expansion_exporter_v2() -> None:
    candidates = [
        {"canonical_lead_id": "c1", "human_outcome": {"final_productivity_outcome": "PRODUCTIVE"}},
        {
            "canonical_lead_id": "c2",
            "human_outcome": {"final_productivity_outcome": "UNPRODUCTIVE"},
        },
        {
            "canonical_lead_id": "c3",
            "human_outcome": {"final_productivity_outcome": "NOT_RESOLVED"},
        },
    ]
    exp = ProductivityExpansionExporter.export_v2_dataset(candidates, dataset_version="test_v2")

    assert exp["total_records"] == 2
    assert exp["excluded_unresolved_and_control_count"] == 1


def test_productivity_expansion_readiness_classifier() -> None:
    cls, req, desc = ProductivityExpansionReadinessClassifier.classify_readiness(
        total_resolved_outcomes=500,
        productive_count=250,
        unproductive_count=250,
        kappa=0.835,
        leakage_violations=0,
        bias_classification="SELECTION_BIAS_LOW",
    )
    assert cls == "PRODUCTIVITY_MODEL_TRAINING_CANDIDATE"
    assert req is False
