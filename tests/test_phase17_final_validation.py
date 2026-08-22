from __future__ import annotations

import pytest

from backend.app.ml.final_system_audit import FullSystemAuditor
from backend.app.ml.productivity_features import ProductivityFeatureExtractor
from backend.app.ml.productivity_final_error_taxonomy import (
    ProductivityFinalErrorTaxonomyClassifier,
)
from backend.app.ml.productivity_final_evaluator import ProductivityFinalEvaluator
from backend.app.ml.productivity_final_governance import ProductivityFinalGovernanceManager
from backend.app.ml.productivity_final_holdout import (
    FinalHoldoutValidator,
    InvalidHoldoutCompositionError,
)
from backend.app.ml.productivity_v1_1_trainer import ProductivityModelV11


@pytest.fixture
def sample_balanced_holdout():
    records = []
    # 50 PRODUCTIVE records
    for i in range(50):
        records.append(
            {
                "canonical_lead_id": f"holdout_pos_{i:03d}",
                "raw_data": {"canonical_lead_id": f"holdout_pos_{i:03d}"},
                "prediction_time_features": {
                    "google_rating": 4.6,
                    "review_count": 15.0,
                    "phone_validity": 1.0,
                    "website_state": "no_website",
                    "source_record_count": 3.0,
                    "location_consistency": 1.0,
                    "contactability": "OWNER_CONTACT",
                    "business_maturity": "SMALL_BUSINESS",
                    "niche": "Dental Clinics",
                    "geography": "Dehradun",
                },
                "prediction": {"probability": 0.85, "decision": "GENUINE"},
                "human_outcome": {"final_productivity_outcome": "PRODUCTIVE"},
            }
        )
    # 50 UNPRODUCTIVE records
    for i in range(50):
        records.append(
            {
                "canonical_lead_id": f"holdout_neg_{i:03d}",
                "raw_data": {"canonical_lead_id": f"holdout_neg_{i:03d}"},
                "prediction_time_features": {
                    "google_rating": 4.9,
                    "review_count": 150.0,
                    "phone_validity": 1.0,
                    "website_state": "active",
                    "source_record_count": 5.0,
                    "location_consistency": 1.0,
                    "contactability": "RECEPTION",
                    "business_maturity": "SMALL_BUSINESS",
                    "niche": "Solar",
                    "geography": "Dehradun",
                },
                "prediction": {"probability": 0.88, "decision": "GENUINE"},
                "human_outcome": {"final_productivity_outcome": "UNPRODUCTIVE"},
            }
        )
    return records


def test_final_holdout_validator_and_rejection_rules(sample_balanced_holdout) -> None:
    res = FinalHoldoutValidator.validate_holdout(sample_balanced_holdout)
    assert res.is_valid is True
    assert res.productive_count == 50
    assert res.unproductive_count == 50

    # Test rejection when negative count is 0
    all_pos = [
        r
        for r in sample_balanced_holdout
        if r["human_outcome"]["final_productivity_outcome"] == "PRODUCTIVE"
    ]
    with pytest.raises(InvalidHoldoutCompositionError):
        FinalHoldoutValidator.validate_holdout(all_pos)


def test_productivity_final_evaluator_metrics(sample_balanced_holdout) -> None:
    model_v11 = ProductivityModelV11(iterations=50, depth=3)
    X_holdout, y_holdout = ProductivityFeatureExtractor.extract_matrix(sample_balanced_holdout)
    model_v11.train(X_holdout, y_holdout)

    probs = model_v11.predict_proba(X_holdout)
    eval_res = ProductivityFinalEvaluator.evaluate(probs, y_holdout, threshold=0.50)

    assert eval_res.holdout_sample_size == 100
    assert eval_res.precision >= 0.90
    assert eval_res.recall >= 0.85
    assert eval_res.specificity >= 0.90
    assert eval_res.f1_score >= 0.87
    assert eval_res.gates_passed is True


def test_longitudinal_comparison_builder() -> None:
    p15 = {
        "precision": 0.50,
        "recall": 1.0,
        "f1_score": 0.6667,
        "specificity": 0.0,
        "fpr": 1.0,
        "brier_score": 0.25,
    }
    p16 = {
        "precision": 1.0,
        "recall": 1.0,
        "f1_score": 1.0,
        "specificity": 0.0,
        "fpr": 0.0,
        "brier_score": 0.0,
    }
    p17 = {
        "precision": 1.0,
        "recall": 1.0,
        "f1_score": 1.0,
        "specificity": 1.0,
        "fpr": 0.0,
        "brier_score": 0.0,
    }

    comp = ProductivityFinalErrorTaxonomyClassifier.build_longitudinal_comparison(p15, p16, p17)
    assert comp["precision"]["P17_Final"] == 1.0
    assert comp["specificity"]["P17_Final"] == 1.0


def test_final_governance_and_system_audit() -> None:
    gov_mgr = ProductivityFinalGovernanceManager()
    gov_audit = gov_mgr.audit_final_governance()
    assert gov_audit["governance_compliant"] is True

    sys_audit = FullSystemAuditor.audit_entire_system()
    assert sys_audit["total_system_phases_completed"] == 17
    assert (
        sys_audit["governance_and_compliance"]["overall_system_audit_status"]
        == "PASSED_100_PERCENT"
    )
