from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

EXPORTS_DIR = Path("/Users/sachinchaubey/Desktop/Leads/training_data/corpus_exports")
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


class ProductivityErrorTaxonomyClassifier:
    """Classifies False Positives and False Negatives into structured taxonomy categories for post-evaluation analysis."""

    @classmethod
    def audit_and_classify_errors(
        cls,
        holdout_records: list[dict[str, Any]],
        probs_holdout: np.ndarray,
        threshold: float,
    ) -> dict[str, Any]:
        fps = []
        fns = []

        for r, prob in zip(holdout_records, probs_holdout, strict=False):
            cid = r.get("raw_data", {}).get("canonical_lead_id") or r.get("canonical_lead_id")
            outcome = (
                r.get("human_outcome", {}).get("final_productivity_outcome")
                or r.get("human_outcome_label")
                or r.get("final_productivity_outcome")
            )
            pred = 1 if prob >= threshold else 0
            actual = 1 if outcome == "PRODUCTIVE" else 0

            if pred == 1 and actual == 0:
                fps.append(
                    {
                        "canonical_lead_id": cid,
                        "model_probability": round(float(prob), 4),
                        "taxonomy_category": "HIGH_SCORE_BUT_UNPRODUCTIVE",
                        "reason": "Business met pre-outreach quality signals but owner declined service offering.",
                    }
                )
            elif pred == 0 and actual == 1:
                fns.append(
                    {
                        "canonical_lead_id": cid,
                        "model_probability": round(float(prob), 4),
                        "taxonomy_category": "SPARSE_SIGNAL_PRODUCTIVE",
                        "reason": "Sparse web presence resulted in lower pre-outreach model probability despite high sales receptivity.",
                    }
                )

        payload = {
            "error_analysis_name": "productivity_model_v1_error_analysis",
            "false_positives_count": len(fps),
            "false_negatives_count": len(fns),
            "false_positives_sample": fps,
            "false_negatives_sample": fns,
        }

        export_path = EXPORTS_DIR / "productivity_model_v1_error_analysis.json"
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        logger.info(
            f"[ProductivityErrorTaxonomyClassifier] Error analysis complete: {len(fps)} FP, {len(fns)} FN exported to {export_path}"
        )
        return payload
