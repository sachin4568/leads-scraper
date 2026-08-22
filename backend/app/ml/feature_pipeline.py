from __future__ import annotations

import math
from typing import Any

from backend.app.ml.leakage_guard import LeakageGuard


class FeaturePipeline:
    """Extracts, encodes, and transforms objective lead attributes into ML feature vectors."""

    def __init__(self) -> None:
        self.feature_allowlist = LeakageGuard.get_feature_allowlist()

    def process_records(
        self, raw_records: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[int], list[dict[str, Any]]]:
        """Transforms raw dataset records into ML features, binary targets, and preserved uncertain triage records."""
        # 1. Leakage Protection Verification
        LeakageGuard.check_for_leakage(list(self.feature_allowlist))

        processed_features: list[dict[str, Any]] = []
        targets: list[int] = []
        uncertain_triage: list[dict[str, Any]] = []

        for record in raw_records:
            gt_label = str(record.get("Ground Truth Genuine", "")).strip().upper()

            if gt_label == "UNCERTAIN":
                uncertain_triage.append(record)
                continue
            elif gt_label == "GENUINE":
                y = 1
            elif gt_label == "NOT_GENUINE":
                y = 0
            else:
                continue

            # Extract objective candidate features
            industry = str(record.get("Industry", "Unknown"))
            location = str(record.get("Location", "Unknown"))
            state = str(record.get("State", "Unknown"))

            try:
                rating = float(record.get("Google Rating", 3.5))
            except (ValueError, TypeError):
                rating = 3.5

            try:
                review_count = int(record.get("Review Count", 0))
            except (ValueError, TypeError):
                review_count = 0

            log_reviews = math.log1p(max(0, review_count))

            has_web = 1.0 if str(record.get("Has Website", "")).upper() == "TRUE" else 0.0
            web_status = str(record.get("Website Status", "No Website"))
            ssl_valid = 1.0 if str(record.get("SSL Valid", "")).upper() == "TRUE" else 0.0

            has_email = 1.0 if str(record.get("Has Email", "")).upper() == "TRUE" else 0.0
            email_valid = 1.0 if str(record.get("Email Valid", "")).upper() == "TRUE" else 0.0
            email_mx = 1.0 if str(record.get("Email MX", "")).upper() == "TRUE" else 0.0

            has_phone = 1.0 if str(record.get("Has Phone", "")).upper() == "TRUE" else 0.0
            phone_valid = 1.0 if str(record.get("Phone Valid", "")).upper() == "TRUE" else 0.0

            features = {
                "industry": industry,
                "location": location,
                "state": state,
                "google_rating": rating,
                "review_count": review_count,
                "log_review_count": round(log_reviews, 4),
                "has_website": has_web,
                "website_status": web_status,
                "ssl_valid": ssl_valid,
                "has_email": has_email,
                "email_valid": email_valid,
                "email_mx": email_mx,
                "has_phone": has_phone,
                "phone_valid": phone_valid,
                "business_name": record.get("Business Name", ""),
                "lead_id": record.get("Lead ID", ""),
            }

            processed_features.append(features)
            targets.append(y)

        return processed_features, targets, uncertain_triage
