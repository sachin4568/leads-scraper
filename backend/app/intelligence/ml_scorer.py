from __future__ import annotations

import logging

from backend.app.models import Lead

logger = logging.getLogger(__name__)


class MLScorer:
    """Baseline machine learning feature extraction and lead conversion scoring model."""

    def extract_features(self, lead: Lead, opportunity_scores: dict[str, int]) -> dict[str, float]:
        has_website_val = 1.0 if lead.website else 0.0
        has_email_val = 1.0 if lead.email else 0.0
        has_phone_val = 1.0 if lead.phone else 0.0

        return {
            "has_website": has_website_val,
            "has_email": has_email_val,
            "has_phone": has_phone_val,
            "web_design_opp": float(opportunity_scores.get("web_design", 0)),
            "seo_opp": float(opportunity_scores.get("seo", 0)),
            "social_opp": float(opportunity_scores.get("social_media", 0)),
            "ads_opp": float(opportunity_scores.get("paid_ads", 0)),
        }

    def predict_conversion_probability(
        self, lead: Lead, opportunity_scores: dict[str, int]
    ) -> float:
        features = self.extract_features(lead, opportunity_scores)

        # Baseline feature weighting (higher contactability + high opportunity = higher probability)
        base = (
            (features["has_email"] * 0.25)
            + (features["has_phone"] * 0.25)
            + (features["has_website"] * 0.10)
        )

        avg_opp = (
            features["web_design_opp"]
            + features["seo_opp"]
            + features["social_opp"]
            + features["ads_opp"]
        ) / 400.0

        raw_prob = (base * 0.5) + (avg_opp * 0.5)
        return round(min(1.0, max(0.0, raw_prob)), 2)
