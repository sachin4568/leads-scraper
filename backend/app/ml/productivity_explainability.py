from __future__ import annotations

import logging
from typing import Any

from catboost import CatBoostClassifier

logger = logging.getLogger(__name__)

FEATURE_NAMES = [
    "google_rating",
    "review_count",
    "phone_validity",
    "website_state_active",
    "source_record_count",
    "location_consistency",
    "contact_owner",
    "small_business",
    "niche_dental",
    "geography_dehradun",
    "genuineness_probability",
]


class ProductivityExplainabilityEngine:
    """Computes global feature importance for Productivity Model v1 Challenger."""

    @staticmethod
    def compute_feature_importance(model: CatBoostClassifier) -> dict[str, Any]:
        raw_importances = model.get_feature_importance()
        ranked = []
        for name, val in zip(FEATURE_NAMES, raw_importances, strict=False):
            ranked.append({"feature_name": name, "importance_score": round(float(val), 4)})

        ranked.sort(key=lambda x: x["importance_score"], reverse=True)

        return {
            "top_10_features": ranked[:10],
            "correlation_vs_causation_note": "Feature importance represents statistical predictive correlation, not causal impact.",
        }
