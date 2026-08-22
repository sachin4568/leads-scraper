from __future__ import annotations

import pytest

from backend.app.production.production_drift import LongitudinalDriftMonitor
from backend.app.production.production_governance import (
    GovernanceApprovalError,
    ProductionGovernanceManager,
)
from backend.app.production.production_scaler import ProductionScaler
from backend.app.production.productivity_dataset import (
    ProductivityCandidateRecord,
    ProductivityDatasetExporter,
    TemporalLeakageError,
)
from backend.app.production.productivity_ground_truth import (
    FinalOutcome,
    OutreachState,
    ProductivityGroundTruthManager,
)


def test_progressive_batch_scaler_gates() -> None:
    scaler = ProductionScaler()

    # 1. Batch 100
    assert scaler.can_trigger_next_batch(100) is True
    res1 = scaler.evaluate_batch_gate("batch_100", 100)
    assert res1.can_proceed_to_next_batch is True

    # 2. Batch 250
    assert scaler.can_trigger_next_batch(250) is True
    res2 = scaler.evaluate_batch_gate("batch_250", 250)
    assert res2.can_proceed_to_next_batch is True

    # 3. Batch 500
    assert scaler.can_trigger_next_batch(500) is True
    res3 = scaler.evaluate_batch_gate("batch_500", 500)
    assert res3.can_proceed_to_next_batch is True


def test_unambiguous_productivity_accounting_invariant() -> None:
    gt_mgr = ProductivityGroundTruthManager()

    # Log 250 Control Cohort Leads
    for i in range(250):
        gt_mgr.log_outreach_record(
            canonical_lead_id=f"ctrl_{i}",
            is_control_cohort=True,
            outreach_state=OutreachState.NOT_ATTEMPTED,
            final_outcome=FinalOutcome.NOT_RESOLVED,
            reviewer_1_id="rev_ctrl",
            reviewer_1_outcome=FinalOutcome.NOT_RESOLVED,
        )

    # Log 250 Outreach Cohort Leads
    for i in range(250):
        gt_mgr.log_outreach_record(
            canonical_lead_id=f"out_{i}",
            is_control_cohort=False,
            outreach_state=OutreachState.CONTACTED if i >= 50 else OutreachState.OWNER_REACHED,
            final_outcome=FinalOutcome.PRODUCTIVE if i < 50 else FinalOutcome.UNPRODUCTIVE,
            reviewer_1_id="rev_1",
            reviewer_1_outcome=FinalOutcome.PRODUCTIVE if i < 50 else FinalOutcome.UNPRODUCTIVE,
        )

    summary = gt_mgr.get_cohort_accounting_summary(total_cohort_leads=500)
    assert summary["unambiguous_accounting_invariant_verified"] is True
    assert summary["control_cohort_untouched_count"] == 250
    assert summary["outreach_cohort_attempted_count"] == 250


def test_cohens_kappa_double_review_target() -> None:
    gt_mgr = ProductivityGroundTruthManager()

    for i in range(50):
        out = FinalOutcome.PRODUCTIVE if i < 40 else FinalOutcome.UNPRODUCTIVE
        gt_mgr.log_outreach_record(
            canonical_lead_id=f"double_{i}",
            is_control_cohort=False,
            outreach_state=OutreachState.OWNER_REACHED,
            final_outcome=out,
            reviewer_1_id="rev_1",
            reviewer_1_outcome=out,
            reviewer_2_id="rev_2",
            reviewer_2_outcome=out,
        )

    kappa_res = gt_mgr.compute_double_review_kappa()
    assert kappa_res.cohens_kappa == 1.0
    assert kappa_res.target_passed is True


def test_temporal_leakage_audit_and_exporter() -> None:
    valid_features = {"phone_validity": 1.0, "google_rating": 4.5, "review_count": 25}
    assert ProductivityDatasetExporter.audit_leakage(valid_features) is True

    leaked_features = {"phone_validity": 1.0, "productive": True}
    with pytest.raises(TemporalLeakageError):
        ProductivityDatasetExporter.audit_leakage(leaked_features)

    rec = ProductivityCandidateRecord(
        canonical_lead_id="lead_test_01",
        prediction_time_features=valid_features,
        model_prediction={"probability": 0.85, "decision": "GENUINE"},
        future_outreach_outcome={"outreach_state": "OWNER_REACHED", "final_outcome": "PRODUCTIVE"},
        human_outcome_label="PRODUCTIVE",
    )
    exported = ProductivityDatasetExporter.export_productivity_dataset(
        [rec], dataset_version="test_v1"
    )
    assert exported["leakage_audit_passed"] is True


def test_longitudinal_drift_monitoring() -> None:
    monitor = LongitudinalDriftMonitor(baseline_mean_prob=0.85)
    report = monitor.calculate_batch_drift("batch_test", [0.84, 0.86, 0.85])

    assert report.drift_classification == "NO_DRIFT"
    assert report.drift_root_cause == "NO_DRIFT"


def test_model_governance_human_approval_enforcement() -> None:
    gov = ProductionGovernanceManager()
    gov.register_challenger("productivity_model_v1")

    with pytest.raises(GovernanceApprovalError):
        gov.promote_challenger_to_champion("productivity_model_v1", human_approved=False)

    compliance = gov.audit_governance_compliance()
    assert compliance["automatic_promotion"] == "OFF"
    assert compliance["automatic_retraining"] == "OFF"
