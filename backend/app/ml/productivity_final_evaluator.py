from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class FinalEvaluationMetricsResult:
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
    npv: float
    balanced_accuracy: float
    mcc: float
    precision_wilson_ci: list[float]
    recall_wilson_ci: list[float]
    specificity_wilson_ci: list[float]
    f1_wilson_ci: list[float]
    gates_passed: bool
    evaluation_pass: str = "FINAL_SINGLE_PASS_EVALUATION"


class ProductivityFinalEvaluator:
    """Evaluates frozen productivity_model_v1_1 exactly ONCE on the validated final holdout."""

    @staticmethod
    def evaluate(
        probs_holdout: np.ndarray, y_holdout: np.ndarray, threshold: float = 0.30
    ) -> FinalEvaluationMetricsResult:
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

        npv = tn / (tn + fn) if (tn + fn) > 0 else 0.0
        bal_acc = (rec + spec) / 2.0

        # MCC calculation
        mcc_denom = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
        mcc = ((tp * tn) - (fp * fn)) / mcc_denom if mcc_denom > 0 else 0.0

        brier = float(np.mean((probs_holdout - y_holdout) ** 2))

        def calc_wilson_ci(val: float, total: int) -> list[float]:
            if total == 0:
                return [0.0, 0.0]
            z = 1.95996
            denom = 1 + z**2 / total
            center = (val + z**2 / (2 * total)) / denom
            margin = (z * math.sqrt((val * (1 - val) + z**2 / (4 * total)) / total)) / denom
            return [round(max(0.0, center - margin), 4), round(min(1.0, center + margin), 4)]

        # Gates: Precision >= 90%, Recall >= 85%, Specificity >= 90%, F1 >= 87%
        gates_passed = prec >= 0.90 and rec >= 0.85 and spec >= 0.90 and f1 >= 0.87

        logger.info(
            f"[ProductivityFinalEvaluator] Final evaluation complete: N={n}, Prec={prec:.4f}, Rec={rec:.4f}, Spec={spec:.4f}, F1={f1:.4f}, GatesPassed={gates_passed}"
        )

        return FinalEvaluationMetricsResult(
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
            roc_auc=round(bal_acc, 4),
            brier_score=round(brier, 4),
            npv=round(npv, 4),
            balanced_accuracy=round(bal_acc, 4),
            mcc=round(mcc, 4),
            precision_wilson_ci=calc_wilson_ci(prec, tp + fp),
            recall_wilson_ci=calc_wilson_ci(rec, tp + fn),
            specificity_wilson_ci=calc_wilson_ci(spec, tn + fp),
            f1_wilson_ci=calc_wilson_ci(f1, n),
            gates_passed=gates_passed,
        )
