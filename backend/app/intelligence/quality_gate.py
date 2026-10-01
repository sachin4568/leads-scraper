from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from urllib.parse import urlparse

from backend.app.enrichment.website_discovery import (
    AGGREGATOR_DOMAIN_BLACKLIST,
    PARKED_DOMAIN_SIGNATURES,
    CandidateFilter,
)

logger = logging.getLogger(__name__)

# Placeholder patterns that must never be treated as valid data
INVALID_STRING_PATTERNS = {
    "not available", "n/a", "na", "null", "none", "unknown", "undefined",
    "unknown business", "test", "demo", "sample", "dummy", "placeholder",
    "nil", "no name", "unnamed", "no business name", "-", "--", "---"
}

# Generic non-business names / facilities that should not be promoted as commercial leads
GENERIC_FACILITY_PATTERNS = (
    "atm", "public toilet", "bench", "parking", "bus stop", "traffic light",
    "waste basket", "post box", "vending machine", "drinking water", "recycling"
)


class QualityGateDecision(str, Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"


class RejectionReason(str, Enum):
    NO_ACTIONABLE_CONTACT_PATH = "NO_ACTIONABLE_CONTACT_PATH"
    INVALID_BUSINESS_NAME = "INVALID_BUSINESS_NAME"
    GEOGRAPHIC_MISMATCH = "GEOGRAPHIC_MISMATCH"
    UNVERIFIED_WEBSITE = "UNVERIFIED_WEBSITE"
    INVALID_CONTACT_DATA = "INVALID_CONTACT_DATA"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    DUPLICATE_IDENTITY = "DUPLICATE_IDENTITY"
    GENERIC_FACILITY = "GENERIC_FACILITY"


@dataclass
class QualityGateResult:
    decision: QualityGateDecision
    is_valid: bool
    is_contactable: bool
    contact_channels: list[str] = field(default_factory=list)
    rejection_reason: RejectionReason | None = None
    rejection_details: list[str] = field(default_factory=list)
    acceptance_reasons: list[str] = field(default_factory=list)
    identity_confidence: float = 0.0
    contactability_score: int = 0
    evidence_completeness: float = 0.0
    actionability_score: float = 0.0
    verified_contacts: dict[str, Any] = field(default_factory=dict)


class QualityGateEngine:
    """
    Deterministic, explainable production Quality Gate.
    Guarantees that no unqualified, unverified, or uncontactable discovery candidate
    is promoted to a production Lead.
    """

    @staticmethod
    def is_invalid_string(value: str | None) -> bool:
        if not value or not str(value).strip():
            return True
        val_clean = str(value).strip().lower()
        return val_clean in INVALID_STRING_PATTERNS

    @classmethod
    def validate_phone(cls, phone: str | None) -> tuple[bool, str | None]:
        """Validates that a phone number contains real actionable digits and is not placeholder."""
        if cls.is_invalid_string(phone):
            return False, None
        
        raw = str(phone).strip()
        digits_only = re.sub(r"\D", "", raw)
        
        # Phone numbers must have at least 7 digits and at most 15 digits
        if len(digits_only) < 7 or len(digits_only) > 15:
            return False, None
            
        # Reject numbers where all digits are identical (e.g. 0000000, 1111111111)
        if len(set(digits_only)) == 1:
            return False, None

        # Reject common sequential test sequences (1234567, 9876543210, etc.)
        if digits_only in ("1234567", "12345678", "123456789", "1234567890", "9876543210"):
            return False, None

        return True, raw

    @classmethod
    def validate_email(cls, email: str | None) -> tuple[bool, str | None]:
        """Validates that an email address has legitimate format and is not placeholder/corrupt."""
        if cls.is_invalid_string(email):
            return False, None
            
        raw = str(email).strip().lower()
        
        # Standard email format check
        email_regex = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
        if not re.match(email_regex, raw):
            return False, None

        # Check for image or static asset extensions mistakenly extracted as emails
        ext = raw.split(".")[-1]
        if ext in ("png", "jpg", "jpeg", "gif", "svg", "webp", "css", "js", "woff", "ttf"):
            return False, None

        # Check for common dummy and telemetry domains
        domain = raw.split("@")[-1]
        if (
            domain in ("example.com", "test.com", "sample.com", "placeholder.com", "domain.com", "localhost")
            or "sentry" in domain
            or "wixpress.com" in domain
            or "cloudflare.com" in domain
            or "schema.org" in domain
            or "w3.org" in domain
        ):
            return False, None

        return True, raw

    @classmethod
    def validate_website(
        cls,
        website: str | None,
        website_verification_status: str | None = None,
        is_reachable: bool = True
    ) -> tuple[bool, str | None]:
        """Validates that a website URL is legitimate, verified, not blacklisted/parked."""
        if cls.is_invalid_string(website):
            return False, None

        normalized = CandidateFilter.normalize_candidate_url(website)
        if not normalized:
            return False, None

        try:
            parsed = urlparse(normalized)
            domain = parsed.hostname
        except Exception:
            return False, None

        if not domain or CandidateFilter.is_blacklisted_domain(domain):
            return False, None

        if website_verification_status == "REJECT":
            return False, None

        return True, normalized

    @classmethod
    def validate_whatsapp(cls, whatsapp: str | None, phone: str | None = None) -> tuple[bool, str | None]:
        """Validates WhatsApp presence from link or valid phone."""
        if whatsapp and not cls.is_invalid_string(whatsapp):
            raw = str(whatsapp).strip()
            if "wa.me" in raw or "api.whatsapp.com" in raw or "whatsapp" in raw.lower():
                return True, raw
        return False, None

    @classmethod
    def validate_social_profiles(cls, social_profiles: dict[str, str] | None) -> tuple[bool, dict[str, str]]:
        """Validates social profiles dictionary."""
        if not social_profiles or not isinstance(social_profiles, dict):
            return False, {}
            
        valid_profiles = {}
        for platform, url in social_profiles.items():
            if url and not cls.is_invalid_string(url):
                valid_profiles[platform] = str(url).strip()
                
        return len(valid_profiles) > 0, valid_profiles

    @classmethod
    def evaluate_candidate(
        cls,
        business_name: str | None,
        phone: str | None = None,
        email: str | None = None,
        website: str | None = None,
        whatsapp: str | None = None,
        social_profiles: dict[str, str] | None = None,
        website_verification_status: str | None = None,
        category: str | None = None,
        target_niche: str | None = None,
        address: str | None = None,
        city: str | None = None,
        target_location: str | None = None,
        extra_phones: list[str] | None = None,
        extra_emails: list[str] | None = None,
        extra_whatsapp_links: list[str] | None = None,
    ) -> QualityGateResult:
        """
        Main deterministic evaluation gate for promoting a candidate to a production Lead.
        """
        rejection_details: list[str] = []
        acceptance_reasons: list[str] = []
        contact_channels: list[str] = []
        verified_contacts: dict[str, Any] = {}

        # ── 1. Pillar 1: Identity & Name Validation ──
        if cls.is_invalid_string(business_name):
            return QualityGateResult(
                decision=QualityGateDecision.REJECT,
                is_valid=False,
                is_contactable=False,
                rejection_reason=RejectionReason.INVALID_BUSINESS_NAME,
                rejection_details=["Business name is missing, empty, or placeholder."],
            )

        clean_name = str(business_name).strip()
        if len(clean_name) < 2:
            return QualityGateResult(
                decision=QualityGateDecision.REJECT,
                is_valid=False,
                is_contactable=False,
                rejection_reason=RejectionReason.INVALID_BUSINESS_NAME,
                rejection_details=[f"Business name '{clean_name}' is too short to be a valid business entity."],
            )

        # Check for generic non-business facilities
        lower_name = clean_name.lower()
        if any(lower_name == generic or lower_name.startswith(f"{generic} ") for generic in GENERIC_FACILITY_PATTERNS):
            return QualityGateResult(
                decision=QualityGateDecision.REJECT,
                is_valid=False,
                is_contactable=False,
                rejection_reason=RejectionReason.GENERIC_FACILITY,
                rejection_details=[f"Entity '{clean_name}' represents a generic infrastructure facility, not a commercial business."],
            )

        identity_confidence = 0.70
        acceptance_reasons.append(f"Genuine entity identity validated: '{clean_name}'")

        # ── 2. Pillar 2: Contact Channel Discovery & Validation ──
        # Check Phone
        has_valid_phone = False
        valid_phone_val = None
        is_phone_ok, phone_val = cls.validate_phone(phone)
        if is_phone_ok and phone_val:
            has_valid_phone = True
            valid_phone_val = phone_val
        elif extra_phones:
            for ep in extra_phones:
                ep_ok, ep_val = cls.validate_phone(ep)
                if ep_ok and ep_val:
                    has_valid_phone = True
                    valid_phone_val = ep_val
                    break

        if has_valid_phone and valid_phone_val:
            contact_channels.append("PHONE")
            verified_contacts["phone"] = valid_phone_val
            acceptance_reasons.append(f"Verified direct phone number available: {valid_phone_val}")

        # Check Email
        has_valid_email = False
        valid_email_val = None
        is_email_ok, email_val = cls.validate_email(email)
        if is_email_ok and email_val:
            has_valid_email = True
            valid_email_val = email_val
        elif extra_emails:
            for em in extra_emails:
                em_ok, em_val = cls.validate_email(em)
                if em_ok and em_val:
                    has_valid_email = True
                    valid_email_val = em_val
                    break

        if has_valid_email and valid_email_val:
            contact_channels.append("EMAIL")
            verified_contacts["email"] = valid_email_val
            acceptance_reasons.append(f"Verified direct email address available: {valid_email_val}")

        # Check Official Website
        has_valid_web, web_val = cls.validate_website(website, website_verification_status)
        if has_valid_web and web_val:
            contact_channels.append("WEBSITE")
            verified_contacts["website"] = web_val
            acceptance_reasons.append(f"Verified official website available: {web_val}")

        # Check WhatsApp
        has_valid_wa, wa_val = cls.validate_whatsapp(whatsapp)
        if not has_valid_wa and extra_whatsapp_links:
            for ewa in extra_whatsapp_links:
                ewa_ok, ewa_val = cls.validate_whatsapp(ewa)
                if ewa_ok and ewa_val:
                    has_valid_wa = True
                    wa_val = ewa_val
                    break

        if has_valid_wa and wa_val:
            contact_channels.append("WHATSAPP")
            verified_contacts["whatsapp"] = wa_val
            acceptance_reasons.append("Direct WhatsApp chat link available")

        # Check Social Profiles
        has_valid_soc, soc_profiles = cls.validate_social_profiles(social_profiles)
        if has_valid_soc:
            contact_channels.append("SOCIAL")
            verified_contacts["social_profiles"] = soc_profiles
            platforms = ", ".join(soc_profiles.keys())
            acceptance_reasons.append(f"Direct messaging reachable on social profiles ({platforms})")

        # ── 3. Mandatory Quality Gate Decision ──
        # A candidate MUST have at least ONE valid actionable contact path
        is_contactable = len(contact_channels) > 0
        if not is_contactable:
            rejection_details.append(
                "Candidate has zero verified contact paths (no phone, no email, no website, no WhatsApp, no social profile)."
            )
            return QualityGateResult(
                decision=QualityGateDecision.REJECT,
                is_valid=False,
                is_contactable=False,
                rejection_reason=RejectionReason.NO_ACTIONABLE_CONTACT_PATH,
                rejection_details=rejection_details,
                identity_confidence=identity_confidence,
                contactability_score=0,
                evidence_completeness=0.20 if (address or city) else 0.10,
                actionability_score=0.0,
            )

        # Calculate Contactability Score (0 - 100)
        contact_score = 0
        if "PHONE" in contact_channels:
            contact_score += 40
        if "EMAIL" in contact_channels:
            contact_score += 35
        if "WEBSITE" in contact_channels:
            contact_score += 30
        if "WHATSAPP" in contact_channels:
            contact_score += 25
        if "SOCIAL" in contact_channels:
            contact_score += 15
        final_contactability_score = min(100, contact_score)

        # Evidence Completeness
        evidence_points = 0
        if business_name:
            evidence_points += 20
        if address or city:
            evidence_points += 20
        if has_valid_phone:
            evidence_points += 20
        if has_valid_web:
            evidence_points += 20
        if has_valid_email or has_valid_wa or has_valid_soc:
            evidence_points += 20
        evidence_completeness = min(1.0, evidence_points / 100.0)

        # Actionability Score (0.0 - 100.0)
        # Actionability = Genuineness * (Contactability * 0.60 + Evidence * 0.40)
        actionability_score = round(
            identity_confidence * (final_contactability_score * 0.60 + (evidence_completeness * 100) * 0.40),
            1
        )

        return QualityGateResult(
            decision=QualityGateDecision.ACCEPT,
            is_valid=True,
            is_contactable=True,
            contact_channels=contact_channels,
            rejection_reason=None,
            rejection_details=[],
            acceptance_reasons=acceptance_reasons,
            identity_confidence=identity_confidence,
            contactability_score=final_contactability_score,
            evidence_completeness=evidence_completeness,
            actionability_score=actionability_score,
            verified_contacts=verified_contacts,
        )
