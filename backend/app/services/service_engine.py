from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from backend.app.services.formatter import LeadDataFormatter

logger = logging.getLogger(__name__)


@dataclass
class ServiceScoreResult:
    service_type: str
    eligible: bool
    score: float
    confidence: float
    reasons: list[str]
    facebook_ads_detected: str
    ssl_valid: str


class ServiceOpportunityEngine:
    """Calculates FOUR independent 0-100 service opportunity scores with explainable reasons."""

    @classmethod
    def calculate_website_development(cls, formatted_lead: dict[str, Any]) -> ServiceScoreResult:
        score = 0.0
        reasons = []

        web_avail = formatted_lead.get("website_available") == "Y"
        ig_avail = formatted_lead.get("instagram_available") == "Y"
        fb_avail = formatted_lead.get("facebook_available") == "Y"
        phone_avail = formatted_lead.get("phone_available") == "Y"
        email_avail = formatted_lead.get("email_available") == "Y"
        gen_prob = formatted_lead.get("genuineness_probability", 0.85)

        if not web_avail:
            score += 40.0
            reasons.append("No website detected (Primary Website Development Signal)")

        if ig_avail or fb_avail:
            score += 25.0
            social_name = "Instagram" if ig_avail else "Facebook"
            reasons.append(
                f"Active {social_name} presence creating high digital conversion potential"
            )

        if phone_avail or email_avail:
            score += 15.0
            reasons.append("Valid contactability (Direct phone/email available)")

        if gen_prob >= 0.70:
            score += 10.0
            reasons.append(f"High business genuineness confidence ({int(gen_prob * 100)}%)")

        if formatted_lead.get("business_maturity") in (
            "SMALL_BUSINESS",
            "LOCAL_BUSINESS",
            "STARTUP",
        ):
            score += 10.0
            reasons.append("Small/local business profile fitting development service model")

        score = round(min(100.0, score), 1)
        eligible = score >= 50.0

        return ServiceScoreResult(
            service_type="WEBSITE_DEVELOPMENT",
            eligible=eligible,
            score=score,
            confidence=round(gen_prob, 2),
            reasons=reasons,
            facebook_ads_detected=formatted_lead.get("facebook_ads_detected", "N"),
            ssl_valid=formatted_lead.get("ssl_valid", "N"),
        )

    @classmethod
    def calculate_website_seo(cls, formatted_lead: dict[str, Any]) -> ServiceScoreResult:
        score = 0.0
        reasons = []

        web_avail = formatted_lead.get("website_available") == "Y"
        ssl_val = formatted_lead.get("ssl_valid") == "Y"
        rating = formatted_lead.get("google_rating", 4.5)
        reviews = formatted_lead.get("review_count", 25)
        gen_prob = formatted_lead.get("genuineness_probability", 0.85)

        if web_avail:
            score += 30.0
            reasons.append("Active website available for search engine optimization")

            if not ssl_val:
                score += 25.0
                reasons.append("SSL Certificate invalid or missing HTTPS encryption")
            else:
                reasons.append("SSL encryption present")

            if reviews < 30:
                score += 20.0
                reasons.append(f"Low review count ({reviews} reviews) indicating local SEO gap")

            if rating >= 4.0:
                score += 15.0
                reasons.append(
                    f"High Google rating ({rating}) creates strong SEO conversion opportunity"
                )

            if gen_prob >= 0.70:
                score += 10.0
                reasons.append("Verified genuine business entity")
        else:
            reasons.append("No active website available for SEO service")

        score = round(min(100.0, score), 1)
        eligible = score >= 50.0 and web_avail

        return ServiceScoreResult(
            service_type="WEBSITE_SEO",
            eligible=eligible,
            score=score,
            confidence=round(gen_prob, 2),
            reasons=reasons,
            facebook_ads_detected=formatted_lead.get("facebook_ads_detected", "N"),
            ssl_valid=formatted_lead.get("ssl_valid", "N"),
        )

    @classmethod
    def calculate_social_media_management(
        cls, formatted_lead: dict[str, Any]
    ) -> ServiceScoreResult:
        score = 0.0
        reasons = []

        ig_avail = formatted_lead.get("instagram_available") == "Y"
        fb_avail = formatted_lead.get("facebook_available") == "Y"
        reviews = formatted_lead.get("review_count", 25)
        gen_prob = formatted_lead.get("genuineness_probability", 0.85)

        if ig_avail or fb_avail:
            score += 35.0
            reasons.append("Existing social media accounts present")

            if reviews >= 20:
                score += 30.0
                reasons.append(
                    f"Active local customer volume ({reviews} Google reviews) vs idle social profiles"
                )

            if formatted_lead.get("contact_hierarchy") in ("OWNER_CONTACT", "DECISION_MAKER"):
                score += 20.0
                reasons.append("Direct decision-maker contact available for management approval")

            if gen_prob >= 0.70:
                score += 15.0
                reasons.append("High genuineness probability")
        else:
            reasons.append("No social media handles detected for management service")

        score = round(min(100.0, score), 1)
        eligible = score >= 50.0 and (ig_avail or fb_avail)

        return ServiceScoreResult(
            service_type="SOCIAL_MEDIA_MANAGEMENT",
            eligible=eligible,
            score=score,
            confidence=round(gen_prob, 2),
            reasons=reasons,
            facebook_ads_detected=formatted_lead.get("facebook_ads_detected", "N"),
            ssl_valid=formatted_lead.get("ssl_valid", "N"),
        )

    @classmethod
    def calculate_social_media_marketing(cls, formatted_lead: dict[str, Any]) -> ServiceScoreResult:
        score = 0.0
        reasons = []

        fb_ads = formatted_lead.get("facebook_ads_detected") == "Y"
        ig_avail = formatted_lead.get("instagram_available") == "Y"
        fb_avail = formatted_lead.get("facebook_available") == "Y"
        reviews = formatted_lead.get("review_count", 25)
        gen_prob = formatted_lead.get("genuineness_probability", 0.85)

        if fb_ads:
            score += 40.0
            reasons.append("Facebook Ads Detected: Y (Proven paid advertising budget)")
        elif ig_avail or fb_avail:
            score += 25.0
            reasons.append("Social platform infrastructure ready for paid campaigns")

        if reviews >= 15:
            score += 25.0
            reasons.append("Proven commercial activity and local customer demand")

        if formatted_lead.get("niche") in (
            "Dental Clinics",
            "Solar",
            "Roofing",
            "Legal Services",
            "HVAC",
        ):
            score += 20.0
            reasons.append(
                f"High customer-lifetime-value niche ({formatted_lead.get('niche')}) ideal for paid ads"
            )

        if gen_prob >= 0.70:
            score += 15.0
            reasons.append("High business genuineness confidence")

        score = round(min(100.0, score), 1)
        eligible = score >= 50.0

        return ServiceScoreResult(
            service_type="SOCIAL_MEDIA_MARKETING",
            eligible=eligible,
            score=score,
            confidence=round(gen_prob, 2),
            reasons=reasons,
            facebook_ads_detected=formatted_lead.get("facebook_ads_detected", "N"),
            ssl_valid=formatted_lead.get("ssl_valid", "N"),
        )

    @classmethod
    def evaluate_all_services(cls, raw_lead_data: dict[str, Any]) -> dict[str, ServiceScoreResult]:
        formatted = LeadDataFormatter.format_master_lead_payload(raw_lead_data)
        return {
            "WEBSITE_DEVELOPMENT": cls.calculate_website_development(formatted),
            "WEBSITE_SEO": cls.calculate_website_seo(formatted),
            "SOCIAL_MEDIA_MANAGEMENT": cls.calculate_social_media_management(formatted),
            "SOCIAL_MEDIA_MARKETING": cls.calculate_social_media_marketing(formatted),
        }
