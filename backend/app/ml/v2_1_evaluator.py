from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class HoldoutMetricsV21:
    holdout_name: str
    total_leads: int
    tp: int
    fp: int
    fn: int
    tn: int
    precision: float
    recall: float
    f1_score: float
    specificity: float
    no_website_recall: float
    phone_only_recall: float


class ModelV21Evaluator:
    """Evaluates Real Model v2.1 Challenger on frozen multi-holdout datasets and compares against Model v2 baseline."""

    @staticmethod
    def evaluate_ensemble(
        holdout_name: str,
        cat_model: Any,
        lgb_model: Any,
        X_test: np.ndarray,
        y_test: np.ndarray,
        alpha: float = 0.30,
        threshold: float = 0.50,
        metadata: list[dict[str, Any]] | None = None,
    ) -> HoldoutMetricsV21:
        if len(X_test) == 0:
            return HoldoutMetricsV21(
                holdout_name=holdout_name,
                total_leads=0,
                tp=0,
                fp=0,
                fn=0,
                tn=0,
                precision=0.0,
                recall=0.0,
                f1_score=0.0,
                specificity=0.0,
                no_website_recall=0.0,
                phone_only_recall=0.0,
            )

        p_cat = cat_model.predict_proba(X_test)[:, 1]
        p_lgb = (
            lgb_model.predict_proba(X_test)[:, 1]
            if hasattr(lgb_model, "predict_proba")
            else lgb_model.predict(X_test)
        )
        p_ens = alpha * p_cat + (1.0 - alpha) * p_lgb
        preds = (p_ens >= threshold).astype(int)

        tp = int(np.sum((preds == 1) & (y_test == 1)))
        fp = int(np.sum((preds == 1) & (y_test == 0)))
        fn = int(np.sum((preds == 0) & (y_test == 1)))
        tn = int(np.sum((preds == 0) & (y_test == 0)))

        prec = round(float(tp / (tp + fp)), 4) if (tp + fp) > 0 else 0.0
        rec = round(float(tp / (tp + fn)), 4) if (tp + fn) > 0 else 0.0
        spec = round(float(tn / (tn + fp)), 4) if (tn + fp) > 0 else 0.0
        f1 = round(float(2 * prec * rec / (prec + rec)), 4) if (prec + rec) > 0 else 0.0

        # Calculate NO_WEBSITE and PHONE_ONLY Genuine Recall
        no_web_tp = 0
        no_web_actual = 0
        phone_tp = 0
        phone_actual = 0

        if metadata:
            for i, meta in enumerate(metadata[: len(preds)]):
                if meta.get("is_genuine"):
                    if meta.get("is_phone_only"):
                        phone_actual += 1
                        if preds[i] == 1:
                            phone_tp += 1
                    else:
                        no_web_actual += 1
                        if preds[i] == 1:
                            no_web_tp += 1

        no_web_rec = round(float(no_web_tp / no_web_actual), 4) if no_web_actual > 0 else rec
        phone_rec = round(float(phone_tp / phone_actual), 4) if phone_actual > 0 else rec

        return HoldoutMetricsV21(
            holdout_name=holdout_name,
            total_leads=len(y_test),
            tp=tp,
            fp=fp,
            fn=fn,
            tn=tn,
            precision=prec,
            recall=rec,
            f1_score=f1,
            specificity=spec,
            no_website_recall=no_web_rec,
            phone_only_recall=phone_rec,
        )

    @staticmethod
    def compare_v2_vs_v2_1(
        v2_metrics: dict[str, float], v2_1_metrics: HoldoutMetricsV21
    ) -> dict[str, Any]:
        p_diff = round(v2_1_metrics.precision - v2_metrics.get("precision", 1.0), 4)
        r_diff = round(v2_1_metrics.recall - v2_metrics.get("recall", 0.75), 4)
        f1_diff = round(v2_1_metrics.f1_score - v2_metrics.get("f1_score", 0.8571), 4)
        s_diff = round(v2_1_metrics.specificity - v2_metrics.get("specificity", 1.0), 4)

        improved = v2_1_metrics.recall >= 0.90 and v2_1_metrics.precision >= 0.95

        return {
            "model_v2_fresh_staging": v2_metrics,
            "model_v2_1_challenger": v2_1_metrics.__dict__,
            "precision_diff": p_diff,
            "recall_diff": r_diff,
            "f1_diff": f1_diff,
            "specificity_diff": s_diff,
            "sparse_business_recall_improved": v2_1_metrics.phone_only_recall > 0.80,
            "overall_success": improved,
            "readiness_decision": "MODEL_V2_1_CANDIDATE_FOR_STAGING"
            if improved
            else "MODEL_V2_1_PROMISING",
        }
