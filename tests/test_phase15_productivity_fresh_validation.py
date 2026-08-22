from __future__ import annotations

import numpy as np
import pytest

from backend.app.ml.productivity_fresh_error_taxonomy import (
    FreshProductivityErrorTaxonomyClassifier,
)
from backend.app.ml.productivity_fresh_ground_truth import FreshProductivityGroundTruthManager
from backend.app.ml.productivity_fresh_validation import (
    FreshProductivityEvaluator,
    FreshProductivityIsolationValidator,
    FreshProductivityReadinessClassifier,
    FrozenProductivityConfigurationError,
    FrozenProductivityInference,
    Phase14Vs15Comparator,
    ProbabilityCalibrationAnalyzer,
)
from backend.app.production.productivity_ground_truth import FinalOutcome


def test_fresh_cohort_isolation_validator() -> None:
    fresh_ids = [f"fresh_{i}" for i in range(1000)]
    historical_ids = [f"hist_{i}" for i in range(5000)]

    res = FreshProductivityIsolationValidator.validate_isolation(fresh_ids, historical_ids)
    assert res.isolation_passed is True
    assert res.overlapping_ids_count == 0

    bad_fresh = fresh_ids + ["hist_10"]
    bad_res = FreshProductivityIsolationValidator.validate_isolation(bad_fresh, historical_ids)
    assert bad_res.isolation_passed is False
    assert bad_res.overlapping_ids_count == 1


def test_frozen_productivity_inference_guard() -> None:
    guard = FrozenProductivityInference(
        model_version="productivity_model_v1", status="CHALLENGER", threshold=0.45
    )
    assert guard.threshold == 0.45

    with pytest.raises(FrozenProductivityConfigurationError):
        FrozenProductivityInference(
            model_version="wrong_version", status="CHALLENGER", threshold=0.45
        )

    with pytest.raises(FrozenProductivityConfigurationError):
        FrozenProductivityInference(
            model_version="productivity_model_v1", status="CHALLENGER", threshold=0.50
        )


def test_fresh_ground_truth_and_double_review_kappa() -> None:
    gt_mgr = FreshProductivityGroundTruthManager()

    for i in range(150):
        out = FinalOutcome.PRODUCTIVE if i < 75 else FinalOutcome.UNPRODUCTIVE
        r2_out = (
            out
            if i % 10 != 0
            else (
                FinalOutcome.UNPRODUCTIVE
                if out == FinalOutcome.PRODUCTIVE
                else FinalOutcome.PRODUCTIVE
            )
        )
        gt_mgr.log_fresh_outcome(
            canonical_lead_id=f"fresh_lead_{i}",
            reviewer_1_id="rev_1",
            reviewer_1_outcome=out,
            reviewer_2_id="rev_2",
            reviewer_2_outcome=r2_out,
        )

    kappa_res = gt_mgr.compute_double_review_kappa()
    assert kappa_res.target_passed is True
    assert kappa_res.cohens_kappa >= 0.75


def test_fresh_performance_evaluator_and_wilson_ci() -> None:
    probs = np.array([0.49] * 300)
    y_true = np.array([1] * 150 + [0] * 150)

    eval_res = FreshProductivityEvaluator.evaluate_fresh_performance(probs, y_true, threshold=0.45)
    assert eval_res.tp == 150
    assert eval_res.fp == 150
    assert eval_res.tn == 0
    assert eval_res.specificity == 0.0
    assert len(eval_res.precision_wilson_ci) == 2


def test_probability_calibration_analyzer() -> None:
    probs = np.array([0.70] * 100)
    calib = ProbabilityCalibrationAnalyzer.analyze_calibration(probs, threshold=0.45)
    assert calib.calibration_classification == "OVERCONFIDENT_PRODUCTIVITY_MODEL"
    assert calib.fraction_above_threshold == 1.0


def test_phase14_vs_phase15_comparator() -> None:
    holdout_res = {"precision": 0.5439, "specificity": 0.0, "brier_score": 0.2483}
    probs = np.array([0.49] * 300)
    y_true = np.array([1] * 150 + [0] * 150)
    fresh_eval = FreshProductivityEvaluator.evaluate_fresh_performance(
        probs, y_true, threshold=0.45
    )

    comp = Phase14Vs15Comparator.compare(holdout_res, fresh_eval)
    assert comp.specificity_reproduction_status == "SPECIFICITY_FAILURE_REPRODUCED"


def test_fresh_error_taxonomy_classifier() -> None:
    records = [
        {
            "canonical_lead_id": f"l_{i}",
            "final_outcome": "UNPRODUCTIVE" if i % 2 == 0 else "PRODUCTIVE",
        }
        for i in range(20)
    ]
    probs = np.array([0.49] * 20)

    taxonomy = FreshProductivityErrorTaxonomyClassifier.audit_fresh_errors(
        records, probs, threshold=0.45
    )
    assert taxonomy["false_positives_count"] == 10
    assert len(taxonomy["false_positives_sample"]) > 0


def test_fresh_readiness_classifier_and_governance() -> None:
    holdout_res = {"precision": 0.5439, "specificity": 0.0, "brier_score": 0.2483}
    probs = np.array([0.49] * 300)
    y_true = np.array([1] * 150 + [0] * 150)
    fresh_eval = FreshProductivityEvaluator.evaluate_fresh_performance(
        probs, y_true, threshold=0.45
    )

    comp = Phase14Vs15Comparator.compare(holdout_res, fresh_eval)
    calib = ProbabilityCalibrationAnalyzer.analyze_calibration(probs, threshold=0.45)

    cls, rationale = FreshProductivityReadinessClassifier.classify(
        comp, calib, double_review_kappa_passed=True
    )
    assert cls == "PRODUCTIVITY_SPECIFICITY_FAILURE"
    assert "0% specificity failure" in rationale
