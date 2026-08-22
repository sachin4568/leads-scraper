from __future__ import annotations

import numpy as np

from backend.app.feedback.fresh_ground_truth import (
    ReviewerAgreementCalculator,
)
from backend.app.ml.fresh_validation import (
    FreshCohortIsolationValidator,
    FreshPerformanceEvaluator,
    FrozenModelInference,
    ProductionReadinessClassifier,
)


def test_zero_cohort_dataset_overlap() -> None:
    fresh = ["fresh_01", "fresh_02", "fresh_03"]
    historical = {"train_01", "val_01", "holdout_01"}
    assert FreshCohortIsolationValidator.verify_cohort_isolation(fresh, historical) is True

    contaminated = ["fresh_01", "train_01"]
    assert FreshCohortIsolationValidator.verify_cohort_isolation(contaminated, historical) is False


def test_frozen_model_inference_configuration() -> None:
    frozen = FrozenModelInference(model_version="real_model_v2_1", alpha=0.10, threshold=0.40)
    assert frozen.model_version == "real_model_v2_1"
    assert frozen.alpha == 0.10
    assert frozen.threshold == 0.40
    assert frozen.inference_mode == "READ_ONLY"

    prob = frozen.predict_prob(p_cat=0.90, p_lgb=0.80)
    assert prob == 0.81
    assert frozen.classify_decision(prob) == "GENUINE"


def test_cohens_kappa_inter_rater_agreement() -> None:
    r1 = ["GENUINE", "GENUINE", "NOT_GENUINE", "GENUINE", "NOT_GENUINE"]
    r2 = ["GENUINE", "GENUINE", "NOT_GENUINE", "GENUINE", "NOT_GENUINE"]
    metrics = ReviewerAgreementCalculator.calculate_cohens_kappa(r1, r2)

    assert metrics.raw_agreement_pct == 100.0
    assert metrics.cohens_kappa == 1.0
    assert metrics.interpretation == "ALMOST_PERFECT"


def test_fresh_performance_evaluator_and_wilson_ci() -> None:
    y_true = np.array([1, 1, 1, 1, 0, 0, 0, 0])
    y_probs = np.array([0.9, 0.85, 0.8, 0.75, 0.1, 0.15, 0.2, 0.05])

    metrics = FreshPerformanceEvaluator.calculate_metrics(y_true, y_probs, threshold=0.40)
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.specificity == 1.0
    assert metrics.brier_score < 0.05
    assert metrics.recall_wilson_ci_lower > 0.40


def test_production_gate_classification() -> None:
    y_true = np.array([1] * 90 + [0] * 10)
    y_probs = np.array([0.8] * 90 + [0.1] * 10)

    overall = FreshPerformanceEvaluator.calculate_metrics(y_true, y_probs, threshold=0.40)
    gate_status = ProductionReadinessClassifier.evaluate_gates(
        overall=overall,
        no_web_recall=1.0,
        phone_only_recall=1.0,
        sparse_recall=1.0,
    )

    assert gate_status.all_gates_passed is True
    assert gate_status.readiness_classification == "READY_FOR_LIMITED_PRODUCTION"
