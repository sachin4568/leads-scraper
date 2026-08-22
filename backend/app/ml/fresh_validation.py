from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class FreshValidationMetrics:
    total_validated_leads: int
    tp: int
    fp: int
    fn: int
    tn: int
    precision: float
    recall: float
    f1_score: float
    specificity: float
    false_positive_rate: float
    false_negative_rate: float
    brier_score: float
    recall_wilson_ci_lower: float
    recall_wilson_ci_upper: float


@dataclass
class ProductionGateStatus:
    overall_precision_passed: bool
    overall_recall_passed: bool
    overall_f1_passed: bool
    overall_specificity_passed: bool
    no_website_recall_passed: bool
    phone_only_recall_passed: bool
    sparse_presence_recall_passed: bool
    all_gates_passed: bool
    readiness_classification: (
        str  # BLOCKED, STAGING_CONTINUE, READY_FOR_LIMITED_PRODUCTION, PRODUCTION_CANDIDATE
    )


class FreshCohortIsolationValidator:
    """Ensures zero dataset ID overlap between fresh leads and historical train/val/holdout partitions."""

    @staticmethod
    def verify_cohort_isolation(fresh_ids: list[str], historical_ids: set[str]) -> bool:
        overlap = set(fresh_ids).intersection(historical_ids)
        if overlap:
            logger.error(
                f"[FreshCohortIsolationValidator] Dataset contamination detected! Overlapping IDs: {overlap}"
            )
            return False
        logger.info(
            f"[FreshCohortIsolationValidator] Zero overlap confirmed for {len(fresh_ids)} fresh leads."
        )
        return True


class FrozenModelInference:
    """Executes read-only inference using frozen model_v2_1 configuration."""

    def __init__(
        self,
        model_version: str = "real_model_v2_1",
        alpha: float = 0.10,
        threshold: float = 0.40,
    ) -> None:
        self.model_version = model_version
        self.alpha = alpha
        self.threshold = threshold
        self.inference_mode = "READ_ONLY"

    def predict_prob(self, p_cat: float, p_lgb: float) -> float:
        return round(self.alpha * p_cat + (1.0 - self.alpha) * p_lgb, 4)

    def classify_decision(self, prob: float) -> str:
        return "GENUINE" if prob >= self.threshold else "REJECTED"


class FreshPerformanceEvaluator:
    """Computes overall metrics, Wilson score confidence intervals, and Brier calibration scores."""

    @staticmethod
    def calculate_metrics(
        y_true: np.ndarray, y_probs: np.ndarray, threshold: float = 0.40
    ) -> FreshValidationMetrics:
        preds = (y_probs >= threshold).astype(int)

        tp = int(np.sum((preds == 1) & (y_true == 1)))
        fp = int(np.sum((preds == 1) & (y_true == 0)))
        fn = int(np.sum((preds == 0) & (y_true == 1)))
        tn = int(np.sum((preds == 0) & (y_true == 0)))

        prec = round(float(tp / (tp + fp)), 4) if (tp + fp) > 0 else 0.0
        rec = round(float(tp / (tp + fn)), 4) if (tp + fn) > 0 else 0.0
        spec = round(float(tn / (tn + fp)), 4) if (tn + fp) > 0 else 0.0
        f1 = round(float(2 * prec * rec / (prec + rec)), 4) if (prec + rec) > 0 else 0.0
        fpr = round(float(fp / (fp + tn)), 4) if (fp + tn) > 0 else 0.0
        fnr = round(float(fn / (fn + tp)), 4) if (fn + tp) > 0 else 0.0

        brier = round(float(np.mean((y_probs - y_true) ** 2)), 4)

        # Wilson 95% CI for recall
        n_actual = tp + fn
        if n_actual > 0:
            z = 1.95996
            p_hat = rec
            denom = 1 + (z**2 / n_actual)
            center = (p_hat + (z**2 / (2 * n_actual))) / denom
            spread = (
                z * math.sqrt((p_hat * (1 - p_hat) / n_actual) + (z**2 / (4 * n_actual**2))) / denom
            )
            ci_lower = round(max(0.0, center - spread), 4)
            ci_upper = round(min(1.0, center + spread), 4)
        else:
            ci_lower, ci_upper = 0.0, 0.0

        return FreshValidationMetrics(
            total_validated_leads=len(y_true),
            tp=tp,
            fp=fp,
            fn=fn,
            tn=tn,
            precision=prec,
            recall=rec,
            f1_score=f1,
            specificity=spec,
            false_positive_rate=fpr,
            false_negative_rate=fnr,
            brier_score=brier,
            recall_wilson_ci_lower=ci_lower,
            recall_wilson_ci_upper=ci_upper,
        )


class SlicePerformanceAnalyzer:
    """Computes slice-level metrics across niche, website state, and contactability."""

    @staticmethod
    def analyze_slice(
        y_true: np.ndarray, y_probs: np.ndarray, threshold: float = 0.40
    ) -> dict[str, Any]:
        metrics = FreshPerformanceEvaluator.calculate_metrics(y_true, y_probs, threshold)
        return {
            "total_leads": metrics.total_validated_leads,
            "tp": metrics.tp,
            "fp": metrics.fp,
            "fn": metrics.fn,
            "tn": metrics.tn,
            "precision": metrics.precision,
            "recall": metrics.recall,
            "specificity": metrics.specificity,
        }


class ProductionReadinessClassifier:
    """Evaluates target production gates and classifies final deployment readiness."""

    @staticmethod
    def evaluate_gates(
        overall: FreshValidationMetrics,
        no_web_recall: float,
        phone_only_recall: float,
        sparse_recall: float,
    ) -> ProductionGateStatus:
        p_pass = overall.precision >= 0.95
        r_pass = overall.recall >= 0.90
        f1_pass = overall.f1_score >= 0.92
        spec_pass = overall.specificity >= 0.95

        no_web_pass = no_web_recall >= 0.90
        phone_pass = phone_only_recall >= 0.90
        sparse_pass = sparse_recall >= 0.90

        all_pass = (
            p_pass
            and r_pass
            and f1_pass
            and spec_pass
            and no_web_pass
            and phone_pass
            and sparse_pass
        )

        if all_pass:
            classification = "READY_FOR_LIMITED_PRODUCTION"
        elif r_pass and p_pass:
            classification = "STAGING_CONTINUE"
        else:
            classification = "BLOCKED"

        return ProductionGateStatus(
            overall_precision_passed=p_pass,
            overall_recall_passed=r_pass,
            overall_f1_passed=f1_pass,
            overall_specificity_passed=spec_pass,
            no_website_recall_passed=no_web_pass,
            phone_only_recall_passed=phone_pass,
            sparse_presence_recall_passed=sparse_pass,
            all_gates_passed=all_pass,
            readiness_classification=classification,
        )
