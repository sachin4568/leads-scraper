from __future__ import annotations

import logging
from typing import Any

import numpy as np

from backend.app.ml.productivity_readiness import TemporalLeakageError

logger = logging.getLogger(__name__)

FORBIDDEN_LEAKAGE_KEYS = {
    "outreach_result",
    "contact_result",
    "owner_reached",
    "decision_maker_reached",
    "response_after_outreach",
    "deal_closed",
    "revenue",
    "conversion_outcome",
    "productive",
    "unproductive",
}

PRODUCTIVITY_V11_FEATURE_NAMES = [
    "genuineness_probability",
    "google_rating",
    "review_count",
    "phone_validity",
    "website_state_active",
    "source_record_count",
    "location_consistency",
    "service_fit_score",
    "digital_gap_score",
    "commercial_intent_proxy",
    "contactability_score",
    "small_business",
]


class ProductivityFeatureExtractor:
    """Extracts pre-prediction feature vectors for Productivity Model v1.1 with strict temporal leakage prevention."""

    @staticmethod
    def extract_features_vector(r: dict[str, Any]) -> list[float]:
        feats = r.get("prediction_time_features") or r.get("derived_features") or {}

        # Assert zero temporal leakage
        leaked = set(feats.keys()).intersection(FORBIDDEN_LEAKAGE_KEYS)
        if leaked:
            raise TemporalLeakageError(
                f"Forbidden post-outreach variables detected in feature snapshot: {leaked}"
            )

        gen_prob = float(r.get("prediction", {}).get("probability", 0.85))
        rating = float(feats.get("google_rating", 4.5))
        reviews = float(feats.get("review_count", 25.0))
        phone_val = float(feats.get("phone_validity", 1.0))
        web_active = 1.0 if feats.get("website_state") == "active" else 0.0
        sources = float(feats.get("source_record_count", 3.0))
        loc_cons = float(feats.get("location_consistency", 1.0))

        # Engineer pre-prediction productivity signals
        # Service fit score: high for dental/solar with missing/no website or low rating
        niche = feats.get("niche", "Dental Clinics")
        is_targeted_niche = 1.0 if niche in ("Dental Clinics", "Solar") else 0.5
        service_fit = round(is_targeted_niche * (1.0 - web_active * 0.5), 4)

        # Digital gap score: absence of active website or low review count creating website/SEO opportunity
        digital_gap = round((1.0 - web_active) * 0.6 + max(0.0, (50.0 - reviews) / 50.0) * 0.4, 4)

        # Commercial intent proxy: rating and review activity
        comm_intent = round(min(1.0, (rating / 5.0) * (reviews / 50.0)), 4)

        # Contactability score: direct owner contact availability
        contact_type = feats.get("contactability", "OWNER_CONTACT")
        contact_score = (
            1.0
            if contact_type == "OWNER_CONTACT"
            else (0.5 if contact_type == "DECISION_MAKER" else 0.2)
        )

        small_biz = 1.0 if feats.get("business_maturity") == "SMALL_BUSINESS" else 0.0

        return [
            gen_prob,
            rating,
            reviews,
            phone_val,
            web_active,
            sources,
            loc_cons,
            service_fit,
            digital_gap,
            comm_intent,
            contact_score,
            small_biz,
        ]

    @classmethod
    def extract_matrix(cls, records: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
        X_list = []
        y_list = []

        for r in records:
            vec = cls.extract_features_vector(r)
            outcome = (
                r.get("human_outcome", {}).get("final_productivity_outcome")
                or r.get("human_outcome_label")
                or r.get("final_productivity_outcome")
            )
            X_list.append(vec)
            y_list.append(1 if outcome == "PRODUCTIVE" else 0)

        return np.array(X_list), np.array(y_list)
