from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class FreshProductivityErrorTaxonomyClassifier:
    """Classifies False Positives and False Negatives on fresh real-world validation records across probability bands."""

    @staticmethod
    def audit_fresh_errors(
        fresh_records: list[dict[str, Any]],
        probs: np.ndarray,
        threshold: float = 0.45,
    ) -> dict[str, Any]:
        fps = []
        fns = []

        prob_bands = {
            "< 0.30": 0,
            "0.30-0.44": 0,
            "0.45-0.59": 0,
            "0.60-0.79": 0,
            ">= 0.80": 0,
        }

        for r, prob in zip(fresh_records, probs, strict=False):
            cid = r.get("canonical_lead_id")
            actual_outcome = r.get("final_outcome")
            pred = 1 if prob >= threshold else 0

            # Record probability band distribution
            if prob < 0.30:
                prob_bands["< 0.30"] += 1
            elif prob < 0.45:
                prob_bands["0.30-0.44"] += 1
            elif prob < 0.60:
                prob_bands["0.45-0.59"] += 1
            elif prob < 0.80:
                prob_bands["0.60-0.79"] += 1
            else:
                prob_bands[">= 0.80"] += 1

            if actual_outcome in ("PRODUCTIVE", "UNPRODUCTIVE"):
                actual = 1 if actual_outcome == "PRODUCTIVE" else 0

                if pred == 1 and actual == 0:
                    category = "HIGH_SCORE_BUT_UNPRODUCTIVE" if prob >= 0.60 else "SERVICE_MISMATCH"
                    fps.append(
                        {
                            "canonical_lead_id": cid,
                            "probability": round(float(prob), 4),
                            "category": category,
                            "reason": "Met pre-outreach digital quality signals, but owner declined service offering.",
                        }
                    )
                elif pred == 0 and actual == 1:
                    fns.append(
                        {
                            "canonical_lead_id": cid,
                            "probability": round(float(prob), 4),
                            "category": "SPARSE_BUSINESS_SIGNAL",
                            "reason": "Sparse digital presence resulted in lower pre-outreach probability.",
                        }
                    )

        return {
            "false_positives_count": len(fps),
            "false_negatives_count": len(fns),
            "false_positives_sample": fps[:10],
            "false_negatives_sample": fns[:10],
            "probability_band_distribution": prob_bands,
        }
