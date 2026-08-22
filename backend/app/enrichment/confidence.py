from __future__ import annotations

import logging
from typing import ClassVar

from backend.app.enrichment.email_verifier import EmailVerificationResult
from backend.app.enrichment.phone_validator import PhoneValidationResult
from backend.app.enrichment.website_validator import WebsiteValidationResult

logger = logging.getLogger(__name__)


class ConfidenceScorer:
    WEIGHT_WEBSITE: ClassVar[float] = 0.30
    WEIGHT_EMAIL: ClassVar[float] = 0.40
    WEIGHT_PHONE: ClassVar[float] = 0.30

    @staticmethod
    def compute_website_confidence(result: WebsiteValidationResult | None) -> int:
        if not result:
            return 0
        if result.is_valid:
            if result.ssl_valid:
                return 100
            return 80
        if result.dns_resolved:
            return 40
        return 0

    @staticmethod
    def compute_email_confidence(result: EmailVerificationResult | None) -> int:
        if not result or result.is_disposable:
            return 0
        if result.is_valid and result.has_mx_records:
            return 100
        if result.syntax_valid:
            return 40
        return 0

    @staticmethod
    def compute_phone_confidence(result: PhoneValidationResult | None) -> int:
        if not result or not result.is_valid:
            return 0
        if result.line_type == "toll_free":
            return 75
        return 100

    @classmethod
    def calculate_lead_confidence(
        cls,
        website_result: WebsiteValidationResult | None,
        email_result: EmailVerificationResult | None,
        phone_result: PhoneValidationResult | None,
        source_count: int = 1,
    ) -> tuple[int, dict[str, int]]:
        web_score = cls.compute_website_confidence(website_result)
        email_score = cls.compute_email_confidence(email_result)
        phone_score = cls.compute_phone_confidence(phone_result)

        field_scores = {
            "website": web_score,
            "email": email_score,
            "phone": phone_score,
        }

        weighted_sum = (
            (web_score * cls.WEIGHT_WEBSITE)
            + (email_score * cls.WEIGHT_EMAIL)
            + (phone_score * cls.WEIGHT_PHONE)
        )

        # Multi-source bonus (+5 per additional distinct source confirming lead)
        source_bonus = max(0, (source_count - 1) * 5)
        overall_score = min(100, max(0, round(weighted_sum + source_bonus)))

        return overall_score, field_scores
