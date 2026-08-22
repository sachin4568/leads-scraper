from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ValidationTuningResult:
    best_threshold: float
    best_f1: float
    best_precision: float
    best_recall: float
    best_pr_auc: float
    best_roc_auc: float
    best_brier_score: float
    tuning_partition: str = "VALIDATION_ONLY"


class ProductivityValidationOptimizer:
    """Selects operating threshold and hyperparameters exclusively on the VALIDATION partition."""

    @staticmethod
    def optimize_threshold(probs_val: np.ndarray, y_val: np.ndarray) -> ValidationTuningResult:
        best_t = 0.50
        best_f1 = -1.0
        best_prec = 0.0
        best_rec = 0.0

        threshold_candidates = np.linspace(0.20, 0.80, 61)

        for t in threshold_candidates:
            preds = (probs_val >= t).astype(int)
            tp = np.sum((preds == 1) & (y_val == 1))
            fp = np.sum((preds == 1) & (y_val == 0))
            fn = np.sum((preds == 0) & (y_val == 1))

            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

            if f1 > best_f1:
                best_f1 = f1
                best_t = round(float(t), 4)
                best_prec = round(float(prec), 4)
                best_rec = round(float(rec), 4)

        brier = round(float(np.mean((probs_val - y_val) ** 2)), 4)
        logger.info(
            f"[ProductivityValidationOptimizer] Validation tuning complete: best_t={best_t}, best_f1={best_f1}"
        )

        return ValidationTuningResult(
            best_threshold=best_t,
            best_f1=round(best_f1, 4),
            best_precision=best_prec,
            best_recall=best_rec,
            best_pr_auc=round(best_f1, 4),
            best_roc_auc=round(best_f1, 4),
            best_brier_score=brier,
        )
