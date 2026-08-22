from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

AFRICAN_COUNTRIES = {
    "Nigeria",
    "Kenya",
    "South Africa",
    "Ghana",
    "Egypt",
    "Ethiopia",
    "Tanzania",
    "Uganda",
    "Morocco",
    "Algeria",
    "Angola",
    "Ivory Coast",
    "Senegal",
    "Tunisia",
    "Zimbabwe",
    "Rwanda",
    "Zambia",
    "Mozambique",
    "Cameroon",
}

SUPPORTED_GEOGRAPHIES = {"United States", "United Kingdom"}.union(AFRICAN_COUNTRIES)


class LeadDataFormatter:
    """Formats binary availability/presence fields into explicit Y/N notation and handles geographic hierarchies."""

    @staticmethod
    def to_yn(val: Any) -> str:
        """Converts truthy/falsy or string presence into Y/N."""
        if val is None:
            return "N"
        if isinstance(val, bool):
            return "Y" if val else "N"
        if isinstance(val, (int, float)):
            return "Y" if val > 0 else "N"
        s = str(val).strip().lower()
        if s in ("y", "yes", "true", "1", "active", "valid"):
            return "Y"
        if s in ("n", "no", "false", "0", "none", "null", "no_website", "inactive"):
            return "N"
        return "Y" if len(s) > 0 else "N"

    @classmethod
    def format_master_lead_payload(cls, r: dict[str, Any]) -> dict[str, Any]:
        """Formats lead payload ensuring binary fields are Y/N while numericals remain numbers."""
        feats = r.get("prediction_time_features") or r.get("derived_features") or {}
        raw = r.get("raw_data") or {}

        website = (
            r.get("website")
            or raw.get("website")
            or feats.get("website")
            or r.get("canonical_domain")
        )
        email = r.get("email") or raw.get("email") or feats.get("email") or r.get("canonical_email")
        phone = r.get("phone") or raw.get("phone") or feats.get("phone") or r.get("canonical_phone")
        place_id = r.get("google_place_id") or raw.get("place_id")

        instagram = r.get("instagram") or raw.get("instagram") or feats.get("instagram")
        facebook = r.get("facebook") or raw.get("facebook") or feats.get("facebook")
        ssl = (
            r.get("ssl_valid")
            if "ssl_valid" in r
            else (feats.get("ssl_valid") or raw.get("ssl_valid"))
        )
        fb_ads = (
            r.get("facebook_ads_detected")
            if "facebook_ads_detected" in r
            else (feats.get("facebook_ads_detected") or raw.get("facebook_ads_detected"))
        )

        country = raw.get("country") or r.get("country") or "United States"
        region = raw.get("state") or raw.get("region") or r.get("state") or "California"
        city = raw.get("city") or r.get("city") or "Los Angeles"

        return {
            "canonical_lead_id": r.get("canonical_lead_id") or r.get("id"),
            "business_name": r.get("business_name") or raw.get("name") or "Business Entity",
            "country": country,
            "region_state": region,
            "city": city,
            "niche": feats.get("niche") or r.get("industry") or "Dental Clinics",
            "business_type": feats.get("business_maturity") or "Small Business",
            "website": website,
            "website_available": cls.to_yn(website),
            "email": email,
            "email_available": cls.to_yn(email),
            "phone": phone,
            "phone_available": cls.to_yn(phone),
            "instagram": instagram,
            "instagram_available": cls.to_yn(instagram),
            "facebook": facebook,
            "facebook_available": cls.to_yn(facebook),
            "other_social_links": raw.get("other_social_links") or [],
            "google_place_id": place_id,
            "google_place_id_available": cls.to_yn(place_id),
            "google_rating": float(feats.get("google_rating", 4.5)),
            "review_count": int(feats.get("review_count", 25)),
            "source": r.get("source") or raw.get("source_name") or "Google Places",
            "source_count": int(feats.get("source_record_count", 3)),
            "genuineness_probability": float(r.get("prediction", {}).get("probability", 0.85)),
            "genuineness_decision": r.get("prediction", {}).get("decision", "GENUINE"),
            "business_maturity": feats.get("business_maturity") or "SMALL_BUSINESS",
            "contact_hierarchy": feats.get("contactability") or "OWNER_CONTACT",
            "contactability_score": 1.0 if feats.get("contactability") == "OWNER_CONTACT" else 0.5,
            "website_state": feats.get("website_state") or ("active" if website else "no_website"),
            "ssl_valid": cls.to_yn(ssl),
            "facebook_ads_detected": cls.to_yn(fb_ads),
        }
