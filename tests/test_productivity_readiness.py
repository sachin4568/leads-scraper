from __future__ import annotations

import pytest

from backend.app.ml.productivity_readiness import (
    ControlVsOutreachAnalyzer,
    FeatureQualityAnalyzer,
    LabelDistributionAuditor,
    OutreachSelectionBiasAuditor,
    ProductivityDatasetIntegrityAuditor,
    ProductivityLabelQualityAuditor,
    ProductivityReadinessClassifier,
    ProductivityTemporalLeakageAuditor,
    ServiceOpportunityAnalyzer,
    TemporalLeakageError,
)


@pytest.fixture
def mock_productivity_records():
    recs = []
    # 50 PRODUCTIVE records
    for i in range(50):
        recs.append(
            {
                "canonical_lead_id": f"lead_prod_{i:03d}",
                "human_outcome_label": "PRODUCTIVE",
                "future_outreach_outcome": {
                    "outreach_state": "OWNER_REACHED",
                    "final_outcome": "PRODUCTIVE",
                },
                "prediction_time_features": {
                    "phone_validity": 1.0,
                    "google_rating": 4.8,
                    "review_count": 40.0,
                    "niche": "Dental Clinics",
                },
                "is_control_cohort": False,
            }
        )
    # 70 UNPRODUCTIVE records
    for i in range(70):
        recs.append(
            {
                "canonical_lead_id": f"lead_unprod_{i:03d}",
                "human_outcome_label": "UNPRODUCTIVE",
                "future_outreach_outcome": {
                    "outreach_state": "CONTACTED",
                    "final_outcome": "UNPRODUCTIVE",
                },
                "prediction_time_features": {
                    "phone_validity": 1.0,
                    "google_rating": 4.2,
                    "review_count": 15.0,
                    "niche": "Solar",
                },
                "is_control_cohort": False,
            }
        )
    # 130 NOT_RESOLVED records
    for i in range(130):
        recs.append(
            {
                "canonical_lead_id": f"lead_unres_{i:03d}",
                "human_outcome_label": "NOT_RESOLVED",
                "future_outreach_outcome": {
                    "outreach_state": "CONTACTED",
                    "final_outcome": "NOT_RESOLVED",
                },
                "prediction_time_features": {
                    "phone_validity": 1.0,
                    "google_rating": 4.5,
                    "review_count": 20.0,
                    "niche": "Dental Clinics",
                },
                "is_control_cohort": False,
            }
        )
    # 250 NOT_ATTEMPTED Control records
    for i in range(250):
        recs.append(
            {
                "canonical_lead_id": f"lead_ctrl_{i:03d}",
                "human_outcome_label": "NOT_RESOLVED",
                "future_outreach_outcome": {
                    "outreach_state": "NOT_ATTEMPTED",
                    "final_outcome": "NOT_RESOLVED",
                },
                "prediction_time_features": {
                    "phone_validity": 1.0,
                    "google_rating": 4.5,
                    "review_count": 20.0,
                    "niche": "Dental Clinics",
                },
                "is_control_cohort": True,
            }
        )
    return recs


def test_dataset_integrity_auditor(mock_productivity_records) -> None:
    res = ProductivityDatasetIntegrityAuditor.audit_integrity(mock_productivity_records)
    assert res.total_records_discovered == 500
    assert res.unique_canonical_ids == 500
    assert res.duplicate_id_count == 0
    assert res.missing_labels_count == 0
    assert res.integrity_passed is True


def test_label_distribution_and_wilson_ci(mock_productivity_records) -> None:
    dist = LabelDistributionAuditor.calculate_distribution(mock_productivity_records)
    assert dist.total_records == 500
    assert dist.eligible_labeled_records == 120
    assert dist.productive_count == 50
    assert dist.unproductive_count == 70
    assert dist.not_attempted_count == 250
    assert dist.productive_rate == 0.4167
    assert dist.class_imbalance_ratio == 1.4
    assert 0.30 <= dist.wilson_95_ci_low <= 0.36
    assert 0.48 <= dist.wilson_95_ci_high <= 0.54


def test_outreach_selection_bias_auditor() -> None:
    res = OutreachSelectionBiasAuditor.audit_selection_bias([0.85] * 250, [0.85] * 250)
    assert res.outreach_cohort_size == 250
    assert res.control_cohort_size == 250
    assert res.selection_bias_classification == "SELECTION_BIAS_LOW"


def test_label_quality_kappa_threshold() -> None:
    q_pass = ProductivityLabelQualityAuditor.audit_label_quality(0.8286, 91.67)
    assert q_pass.kappa_passed is True

    q_fail = ProductivityLabelQualityAuditor.audit_label_quality(0.60, 80.0)
    assert q_fail.kappa_passed is False


def test_temporal_leakage_detection(mock_productivity_records) -> None:
    assert (
        ProductivityTemporalLeakageAuditor.audit_temporal_leakage(mock_productivity_records) is True
    )

    leaked = list(mock_productivity_records)
    leaked[0]["prediction_time_features"]["productive"] = True
    with pytest.raises(TemporalLeakageError):
        ProductivityTemporalLeakageAuditor.audit_temporal_leakage(leaked)


def test_feature_quality_and_service_opportunities(mock_productivity_records) -> None:
    feats = FeatureQualityAnalyzer.analyze_features(mock_productivity_records)
    assert feats["google_rating"]["productive_mean"] == 4.8
    assert feats["google_rating"]["unproductive_mean"] == 4.2

    services = ServiceOpportunityAnalyzer.analyze_service_opportunities()
    assert services["WEBSITE"]["productive_rate"] == 0.4167

    cohorts = ControlVsOutreachAnalyzer.analyze_cohorts(250, 250)
    assert cohorts["balance_status"] == "BALANCED"


def test_productivity_readiness_classifier(mock_productivity_records) -> None:
    integ = ProductivityDatasetIntegrityAuditor.audit_integrity(mock_productivity_records)
    dist = LabelDistributionAuditor.calculate_distribution(mock_productivity_records)
    qual = ProductivityLabelQualityAuditor.audit_label_quality(0.8286, 91.67)

    res = ProductivityReadinessClassifier.classify(integ, dist, qual, leakage_passed=True)
    assert res.classification == "PRODUCTIVITY_MODEL_EXPERIMENT_READY"
    assert res.more_data_required is True
