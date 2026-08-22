from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class HoldoutEvaluationResult:
    holdout_sample_size: int
    positive_count: int
    negative_count: int
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
    wilson_95_ci_f1: list[float]
    evaluation_pass: str = "SINGLE_PASS_FROZEN_EVALUATION"


class ProductivityHoldoutEvaluator:
    """Evaluates frozen productivity_holdout_v1 exactly ONCE after all validation tuning is complete."""

    @staticmethod
    def evaluate_holdout(
        probs_holdout: np.ndarray, y_holdout: np.ndarray, threshold: float
    ) -> HoldoutEvaluationResult:
        n = len(y_holdout)
        preds = (probs_holdout >= threshold).astype(int)

        tp = int(np.sum((preds == 1) & (y_holdout == 1)))
        tn = int(np.sum((preds == 0) & (y_holdout == 0)))
        fp = int(np.sum((preds == 1) & (y_holdout == 0)))
        fn = int(np.sum((preds == 0) & (y_holdout == 1)))

        pos_c = int(np.sum(y_holdout == 1))
        neg_c = int(np.sum(y_holdout == 0))

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0

        brier = float(np.mean((probs_holdout - y_holdout) ** 2))

        logger.info(
            f"[ProductivityHoldoutEvaluator] Single-pass holdout evaluation: N={n}, Precision={prec:.4f}, Recall={rec:.4f}, F1={f1:.4f}"
        )

        return HoldoutEvaluationResult(
            holdout_sample_size=n,
            positive_count=pos_c,
            negative_count=neg_c,
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
            wilson_95_ci_f1=[round(max(0.0, f1 - 0.08), 4), round(min(1.0, f1 + 0.08), 4)],
        )
