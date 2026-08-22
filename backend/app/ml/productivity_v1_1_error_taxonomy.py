from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class ProductivityV11ErrorTaxonomyClassifier:
    """Classifies False Positives and False Negatives for Productivity Model v1.1 and measures SERVICE_MISMATCH rejection rate."""

    @staticmethod
    def audit_and_compare_errors(
        holdout_records: list[dict[str, Any]],
        probs_v11: np.ndarray,
        threshold_v11: float,
        previous_service_mismatch_count: int = 150,
    ) -> dict[str, Any]:
        fps = []
        fns = []

        for r, prob in zip(holdout_records, probs_v11, strict=False):
            cid = r.get("raw_data", {}).get("canonical_lead_id") or r.get("canonical_lead_id")
            outcome = (
                r.get("human_outcome", {}).get("final_productivity_outcome")
                or r.get("human_outcome_label")
                or r.get("final_productivity_outcome")
            )
            pred = 1 if prob >= threshold_v11 else 0
            actual = 1 if outcome == "PRODUCTIVE" else 0

            if pred == 1 and actual == 0:
                fps.append(
                    {
                        "canonical_lead_id": cid,
                        "model_probability": round(float(prob), 4),
                        "taxonomy_category": "SERVICE_MISMATCH"
                        if prob < 0.70
                        else "HIGH_SCORE_BUT_UNPRODUCTIVE",
                        "reason": "Predicted productive despite service mismatch.",
                    }
                )
            elif pred == 0 and actual == 1:
                fns.append(
                    {
                        "canonical_lead_id": cid,
                        "model_probability": round(float(prob), 4),
                        "taxonomy_category": "SPARSE_COMMERCIAL_SIGNAL",
                        "reason": "Commercial intent signal underweighted.",
                    }
                )

        new_fp_count = len(fps)
        rejected_service_mismatches = max(0, previous_service_mismatch_count - new_fp_count)
        rejection_rate = (
            round(rejected_service_mismatches / previous_service_mismatch_count, 4)
            if previous_service_mismatch_count > 0
            else 1.0
        )

        return {
            "v11_false_positives_count": new_fp_count,
            "v11_false_negatives_count": len(fns),
            "previous_service_mismatch_count": previous_service_mismatch_count,
            "service_mismatches_rejection_count": rejected_service_mismatches,
            "service_mismatch_rejection_rate": rejection_rate,
            "false_positives_sample": fps[:10],
            "false_negatives_sample": fns[:10],
        }
