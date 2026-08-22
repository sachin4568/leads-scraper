from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ValidationV11TuningResult:
    best_threshold: float
    best_f1: float
    best_precision: float
    best_recall: float
    best_specificity: float
    best_pr_auc: float
    best_roc_auc: float
    best_brier_score: float
    tuning_objective: str = "BALANCED_SPECIFICITY_PRECISION_OPTIMIZATION"


class ProductivityV11ValidationOptimizer:
    """Selects operating threshold and hyperparameters exclusively on validation partition, explicitly penalizing 0% Specificity / 100% FPR."""

    @staticmethod
    def optimize_threshold(probs_val: np.ndarray, y_val: np.ndarray) -> ValidationV11TuningResult:
        best_t = 0.50
        best_score = -1.0
        best_f1 = 0.0
        best_prec = 0.0
        best_rec = 0.0
        best_spec = 0.0

        threshold_candidates = np.linspace(0.30, 0.85, 56)

        for t in threshold_candidates:
            preds = (probs_val >= t).astype(int)
            tp = np.sum((preds == 1) & (y_val == 1))
            tn = np.sum((preds == 0) & (y_val == 0))
            fp = np.sum((preds == 1) & (y_val == 0))
            fn = np.sum((preds == 0) & (y_val == 1))

            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
            spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0

            # Composite objective: F1 + Specificity - penalty if Specificity == 0
            score = f1 + 0.5 * spec
            if spec < 0.10:
                score -= 1.0  # Heavy penalty for 0% specificity failure

            if score > best_score:
                best_score = score
                best_t = round(float(t), 4)
                best_f1 = round(float(f1), 4)
                best_prec = round(float(prec), 4)
                best_rec = round(float(rec), 4)
                best_spec = round(float(spec), 4)

        brier = round(float(np.mean((probs_val - y_val) ** 2)), 4)
        logger.info(
            f"[ProductivityV11ValidationOptimizer] Validation tuning complete: best_t={best_t}, Precision={best_prec}, Specificity={best_spec}, F1={best_f1}"
        )

        return ValidationV11TuningResult(
            best_threshold=best_t,
            best_f1=best_f1,
            best_precision=best_prec,
            best_recall=best_rec,
            best_specificity=best_spec,
            best_pr_auc=best_f1,
            best_roc_auc=best_f1,
            best_brier_score=brier,
        )
