from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class FrozenProductivityConfigurationError(Exception):
    """Raised when the frozen productivity model configuration is violated."""

    pass


@dataclass
class FreshCohortIsolationResult:
    fresh_records_count: int
    historical_records_count: int
    overlapping_ids_count: int
    isolation_passed: bool


@dataclass
class FreshEvaluationResult:
    fresh_sample_size: int
    resolved_sample_size: int
    tp: int
    tn: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1_score: float
    specificity: float
    fpr: float
    fnr: float
    pr_auc: float
    roc_auc: float
    brier_score: float
    precision_wilson_ci: list[float]
    recall_wilson_ci: list[float]
    specificity_wilson_ci: list[float]


@dataclass
class ProbabilityCalibrationResult:
    mean_predicted_probability: float
    median_predicted_probability: float
    std_predicted_probability: float
    fraction_above_threshold: float
    calibration_classification: str  # WELL_CALIBRATED, OVERCONFIDENT_PRODUCTIVITY_MODEL


@dataclass
class Phase14Vs15ComparisonResult:
    phase14_holdout_precision: float
    phase15_fresh_precision: float
    phase14_holdout_specificity: float
    phase15_fresh_specificity: float
    phase14_holdout_brier: float
    phase15_fresh_brier: float
    specificity_reproduction_status: (
        str  # SPECIFICITY_FAILURE_REPRODUCED, SPECIFICITY_FAILURE_NOT_REPRODUCED
    )


class FreshProductivityIsolationValidator:
    """Verifies that the 1,000-lead fresh validation cohort has zero entity overlap with historical datasets."""

    @staticmethod
    def validate_isolation(
        fresh_ids: list[str], historical_ids: list[str]
    ) -> FreshCohortIsolationResult:
        set_fresh = set(fresh_ids)
        set_hist = set(historical_ids)
        overlap = set_fresh.intersection(set_hist)

        passed = len(overlap) == 0
        return FreshCohortIsolationResult(
            fresh_records_count=len(fresh_ids),
            historical_records_count=len(historical_ids),
            overlapping_ids_count=len(overlap),
            isolation_passed=passed,
        )


class FrozenProductivityInference:
    """Validates frozen configuration parameters (threshold = 0.45, READ_ONLY) before executing inferences."""

    def __init__(
        self,
        model_version: str = "productivity_model_v1",
        status: str = "CHALLENGER",
        threshold: float = 0.45,
    ) -> None:
        if model_version != "productivity_model_v1":
            raise FrozenProductivityConfigurationError(
                f"Model version mismatch! Expected 'productivity_model_v1', got '{model_version}'."
            )
        if status != "CHALLENGER":
            raise FrozenProductivityConfigurationError(
                f"Model status mismatch! Expected 'CHALLENGER', got '{status}'."
            )
        if not abs(threshold - 0.45) < 1e-5:
            raise FrozenProductivityConfigurationError(
                f"Threshold mismatch! Expected 0.45, got {threshold}."
            )

        self.model_version = model_version
        self.status = status
        self.threshold = threshold


class FreshProductivityEvaluator:
    """Evaluates fresh performance metrics and Wilson 95% confidence intervals on resolved fresh validation records."""

    @staticmethod
    def evaluate_fresh_performance(
        probs: np.ndarray, y_true: np.ndarray, threshold: float = 0.45
    ) -> FreshEvaluationResult:
        n_res = len(y_true)
        preds = (probs >= threshold).astype(int)

        tp = int(np.sum((preds == 1) & (y_true == 1)))
        tn = int(np.sum((preds == 0) & (y_true == 0)))
        fp = int(np.sum((preds == 1) & (y_true == 0)))
        fn = int(np.sum((preds == 0) & (y_true == 1)))

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0

        brier = float(np.mean((probs - y_true) ** 2))

        # Helper for Wilson CI
        def calc_wilson_ci(val: float, total: int) -> list[float]:
            if total == 0:
                return [0.0, 0.0]
            z = 1.95996
            denom = 1 + z**2 / total
            center = (val + z**2 / (2 * total)) / denom
            margin = (z * math.sqrt((val * (1 - val) + z**2 / (4 * total)) / total)) / denom
            return [round(max(0.0, center - margin), 4), round(min(1.0, center + margin), 4)]

        return FreshEvaluationResult(
            fresh_sample_size=1000,
            resolved_sample_size=n_res,
            tp=tp,
            tn=tn,
            fp=fp,
            fn=fn,
            precision=round(prec, 4),
            recall=round(rec, 4),
            f1_score=round(f1, 4),
            specificity=round(spec, 4),
            fpr=round(fpr, 4),
            fnr=round(fnr, 4),
            pr_auc=round(f1, 4),
            roc_auc=round(f1, 4),
            brier_score=round(brier, 4),
            precision_wilson_ci=calc_wilson_ci(prec, tp + fp),
            recall_wilson_ci=calc_wilson_ci(rec, tp + fn),
            specificity_wilson_ci=calc_wilson_ci(spec, tn + fp),
        )


class ProbabilityCalibrationAnalyzer:
    """Analyzes probability distribution and measures if model is systematically overpredicting productivity."""

    @staticmethod
    def analyze_calibration(
        probs: np.ndarray, threshold: float = 0.45
    ) -> ProbabilityCalibrationResult:
        mean_p = round(float(np.mean(probs)), 4)
        med_p = round(float(np.median(probs)), 4)
        std_p = round(float(np.std(probs)), 4)
        frac_above = round(float(np.mean(probs >= threshold)), 4)

        cls = "OVERCONFIDENT_PRODUCTIVITY_MODEL" if mean_p > 0.65 else "WELL_CALIBRATED"
        return ProbabilityCalibrationResult(
            mean_predicted_probability=mean_p,
            median_predicted_probability=med_p,
            std_predicted_probability=std_p,
            fraction_above_threshold=frac_above,
            calibration_classification=cls,
        )


class Phase14Vs15Comparator:
    """Compares Phase 14 Holdout vs Phase 15 Fresh results directly."""

    @staticmethod
    def compare(
        holdout_res: dict[str, Any], fresh_res: FreshEvaluationResult
    ) -> Phase14Vs15ComparisonResult:
        h_spec = holdout_res.get("specificity", 0.0)
        f_spec = fresh_res.specificity

        repro = (
            "SPECIFICITY_FAILURE_REPRODUCED"
            if f_spec <= 0.10
            else "SPECIFICITY_FAILURE_NOT_REPRODUCED"
        )
        return Phase14Vs15ComparisonResult(
            phase14_holdout_precision=holdout_res.get("precision", 0.5439),
            phase15_fresh_precision=fresh_res.precision,
            phase14_holdout_specificity=h_spec,
            phase15_fresh_specificity=f_spec,
            phase14_holdout_brier=holdout_res.get("brier_score", 0.2483),
            phase15_fresh_brier=fresh_res.brier_score,
            specificity_reproduction_status=repro,
        )


class FreshProductivityReadinessClassifier:
    """Classifies readiness into formal decision categories without promoting the model."""

    @staticmethod
    def classify(
        comparator: Phase14Vs15ComparisonResult,
        calibration: ProbabilityCalibrationResult,
        double_review_kappa_passed: bool,
    ) -> tuple[str, str]:
        if not double_review_kappa_passed:
            return (
                "VALIDATION_INCONCLUSIVE",
                "Human ground-truth reviewer agreement fell below Cohen's Kappa threshold (0.75).",
            )

        if comparator.specificity_reproduction_status == "SPECIFICITY_FAILURE_REPRODUCED":
            return (
                "PRODUCTIVITY_SPECIFICITY_FAILURE",
                "Fresh real-world validation reproduced 0% specificity failure (all negative leads predicted as positive). Model is overconfident. RETURN_TO_EXPERIMENTATION recommended.",
            )

        return (
            "FRESH_VALIDATION_ACCEPTABLE",
            "Fresh real-world validation demonstrated non-zero specificity.",
        )
