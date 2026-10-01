from __future__ import annotations

import datetime
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
from backend.app.intelligence.quality_gate import (
    GENERIC_FACILITY_PATTERNS,
    INVALID_STRING_PATTERNS,
)
from backend.app.verification.geo_phone_codes import (
    KEY_CITY_AREA_CODES,
    TOLL_FREE_AREA_CODES,
    US_STATE_AREA_CODES,
    extract_nanp_area_code,
    resolve_state_code,
)

logger = logging.getLogger(__name__)

# Extended list of directory, review, and food delivery aggregator platforms
THIRD_PARTY_DIRECTORY_DOMAINS: set[str] = {
    "gotoeat.net", "allmenus.com", "menupix.com", "singleplatform.com",
    "sirved.com", "zmenu.com", "restaurantji.com", "menuism.com",
    "yellowpages.com", "superpages.com", "whitepages.com", "dexknows.com",
    "yelp.com", "tripadvisor.com", "opentable.com", "resy.com", "toasttab.com",
    "grubhub.com", "doordash.com", "ubereats.com", "postmates.com", "seamless.com",
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com",
    "mapquest.com", "foursquare.com", "wix.com", "wordpress.com", "squarespace.com",
}

# Domains known to be telemetry, error reporting, or CDN placeholder addresses
TELEMETRY_AND_DUMMY_EMAIL_DOMAINS: set[str] = {
    "sentry.io", "sentry-cdn.com", "wixpress.com", "cloudflare.com",
    "google.com", "schema.org", "w3.org", "gravatar.com", "example.com",
    "test.com", "sample.com", "placeholder.com", "domain.com", "localhost",
}

COMMON_FREE_EMAIL_HOSTS: set[str] = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com",
    "aol.com", "mail.com", "zoho.com", "protonmail.com", "live.com",
}


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass
class FieldVerificationResult:
    field_name: str
    value: Any
    source: str
    verification_status: VerificationStatus
    confidence_score: float  # 0.0 to 1.0
    evidence: dict[str, Any] = field(default_factory=dict)
    last_verified_at: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )


@dataclass
class OverallVerificationResult:
    decision: str  # ACCEPT, REJECT, UNVERIFIED
    composite_confidence: float  # 0.0 to 1.0
    field_results: dict[str, FieldVerificationResult] = field(default_factory=dict)
    is_verified_entity: bool = False
    has_verified_contact: bool = False
    rejection_reasons: list[str] = field(default_factory=list)
    evidence_records: list[dict[str, Any]] = field(default_factory=list)


class VerificationAndEvidenceEngine:
    """
    Production Verification & Evidence Engine.
    Verifies that collected field values genuinely belong to the discovered business
    and attaches structured, evidence-backed confidence scores.
    """

    @classmethod
    def is_invalid_string(cls, value: str | None) -> bool:
        if not value or not str(value).strip():
            return True
        return str(value).strip().lower() in INVALID_STRING_PATTERNS

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Business Name Verification
    # ─────────────────────────────────────────────────────────────────────────
    @classmethod
    def verify_business_name(
        cls, business_name: str | None, source: str = "raw_source"
    ) -> FieldVerificationResult:
        if cls.is_invalid_string(business_name):
            return FieldVerificationResult(
                field_name="business_name",
                value=business_name,
                source=source,
                verification_status=VerificationStatus.REJECTED,
                confidence_score=0.0,
                evidence={"reason": "Business name is missing, placeholder, or invalid"},
            )

        name_clean = str(business_name).strip()
        name_lower = name_clean.lower()

        # Check for non-business public infrastructure/facilities
        for pattern in GENERIC_FACILITY_PATTERNS:
            if name_lower == pattern or (len(name_lower) < 20 and name_lower.startswith(f"{pattern} ")):
                return FieldVerificationResult(
                    field_name="business_name",
                    value=name_clean,
                    source=source,
                    verification_status=VerificationStatus.REJECTED,
                    confidence_score=0.0,
                    evidence={"reason": f"Generic municipal or public facility ('{pattern}')", "matched_pattern": pattern},
                )

        if len(name_clean) < 2:
            return FieldVerificationResult(
                field_name="business_name",
                value=name_clean,
                source=source,
                verification_status=VerificationStatus.REJECTED,
                confidence_score=0.0,
                evidence={"reason": "Business name too short (< 2 characters)"},
            )

        return FieldVerificationResult(
            field_name="business_name",
            value=name_clean,
            source=source,
            verification_status=VerificationStatus.VERIFIED,
            confidence_score=0.95,
            evidence={"checks_passed": ["non_empty", "not_placeholder", "commercial_entity_name"]},
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Website Ownership & Authenticity Verification
    # ─────────────────────────────────────────────────────────────────────────
    @classmethod
    def verify_website(
        cls,
        website: str | None,
        business_name: str | None,
        source: str = "raw_source",
        page_title: str | None = None,
        h1_tags: list[str] | None = None,
        schema_name: str | None = None,
        is_reachable: bool = True,
    ) -> FieldVerificationResult:
        if cls.is_invalid_string(website):
            return FieldVerificationResult(
                field_name="website",
                value=None,
                source=source,
                verification_status=VerificationStatus.UNVERIFIED,
                confidence_score=0.0,
                evidence={"reason": "No website URL provided"},
            )

        normalized_url = CandidateFilter.normalize_candidate_url(website)
        if not normalized_url:
            return FieldVerificationResult(
                field_name="website",
                value=website,
                source=source,
                verification_status=VerificationStatus.REJECTED,
                confidence_score=0.0,
                evidence={"reason": "Malformed or invalid URL syntax"},
            )

        try:
            parsed = urlparse(normalized_url)
            domain = parsed.hostname.lower() if parsed.hostname else ""
        except Exception:
            return FieldVerificationResult(
                field_name="website",
                value=normalized_url,
                source=source,
                verification_status=VerificationStatus.REJECTED,
                confidence_score=0.0,
                evidence={"reason": "Unable to parse domain hostname"},
            )

        # 2a. Reject Aggregator / Directory / Social Domains claiming to be the business website
        is_menu_aggregator = bool(
            re.search(r"(?:menus?\.(?:us|com|net|info)|(?:restaurant-?menus|online-?menu|allmenus|menupix|sirved))", domain)
        )
        if CandidateFilter.is_blacklisted_domain(domain) or any(
            agg in domain for agg in THIRD_PARTY_DIRECTORY_DOMAINS
        ) or is_menu_aggregator:
            return FieldVerificationResult(
                field_name="website",
                value=normalized_url,
                source=source,
                verification_status=VerificationStatus.REJECTED,
                confidence_score=0.0,
                evidence={
                    "reason": "Third-party directory, menu aggregator, or social platform domain",
                    "domain": domain,
                },
            )

        # 2b. Reject Parked / For Sale / Error domains
        for sig in PARKED_DOMAIN_SIGNATURES:
            if sig in domain:
                return FieldVerificationResult(
                    field_name="website",
                    value=normalized_url,
                    source=source,
                    verification_status=VerificationStatus.REJECTED,
                    confidence_score=0.0,
                    evidence={"reason": "Parked or spam domain detected", "signature": sig},
                )

        # 2c. Brand Token Matching
        b_name = str(business_name or "").lower().strip()
        stop_words = {"the", "and", "llc", "inc", "co", "corp", "ltd", "bar", "grill", "restaurant", "cafe", "services", "company"}
        name_tokens_list = re.findall(r"[a-z0-9]+", b_name)
        brand_tokens = [t for t in name_tokens_list if t not in stop_words and len(t) >= 3]
        b_condensed = "".join(brand_tokens)

        # Check domain token overlap
        domain_clean = re.sub(r"^(?:www\.)?", "", domain)
        domain_clean = re.sub(r"\.[a-z]{2,}(?:\.[a-z]{2,})?$", "", domain_clean)
        domain_tokens = set(re.findall(r"[a-z0-9]+", domain_clean))

        domain_token_match = bool(set(brand_tokens).intersection(domain_tokens))
        domain_substring_match = any(t in domain_clean for t in brand_tokens if len(t) >= 4) or (
            len(b_condensed) >= 4 and (b_condensed in domain_clean or domain_clean in b_condensed)
        )
        domain_match = domain_token_match or domain_substring_match

        title_match = False
        if page_title:
            title_tokens = set(re.findall(r"[a-z0-9]+", str(page_title).lower()))
            title_match = bool(set(brand_tokens).intersection(title_tokens))
        schema_match = False
        if schema_name:
            sch_tokens = set(re.findall(r"[a-z0-9]+", str(schema_name).lower()))
            schema_match = bool(set(brand_tokens).intersection(sch_tokens))

        if domain_match or schema_match or title_match:
            confidence = 0.95 if domain_match else 0.85
            return FieldVerificationResult(
                field_name="website",
                value=normalized_url,
                source=source,
                verification_status=VerificationStatus.VERIFIED,
                confidence_score=confidence,
                evidence={
                    "domain": domain,
                    "domain_match": domain_match,
                    "title_match": title_match,
                    "schema_match": schema_match,
                    "brand_tokens": brand_tokens,
                },
            )

        # If domain has brand in full string (e.g. "realseafoodcorestaurant" for "Real Seafood Company")
        b_condensed = "".join([t for t in name_tokens_list if t not in stop_words])
        if len(b_condensed) >= 5 and (b_condensed in domain_clean or domain_clean in b_condensed):
            return FieldVerificationResult(
                field_name="website",
                value=normalized_url,
                source=source,
                verification_status=VerificationStatus.VERIFIED,
                confidence_score=0.90,
                evidence={"domain": domain, "condensed_name_match": True},
            )

        # Reachable standalone domain without strong brand match
        return FieldVerificationResult(
            field_name="website",
            value=normalized_url,
            source=source,
            verification_status=VerificationStatus.INCONCLUSIVE,
            confidence_score=0.50,
            evidence={
                "domain": domain,
                "note": "Standalone domain verified reachable but brand tokens differ",
            },
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Phone Number Verification (Syntax + Geo-Consistency)
    # ─────────────────────────────────────────────────────────────────────────
    @classmethod
    def verify_phone(
        cls,
        phone: str | None,
        source: str = "raw_source",
        target_city: str | None = None,
        target_state: str | None = None,
        target_location: str | None = None,
    ) -> FieldVerificationResult:
        if cls.is_invalid_string(phone):
            return FieldVerificationResult(
                field_name="phone",
                value=None,
                source=source,
                verification_status=VerificationStatus.UNVERIFIED,
                confidence_score=0.0,
                evidence={"reason": "No phone number provided"},
            )

        raw = str(phone).strip()
        digits_only = re.sub(r"\D", "", raw)

        # Reject malformed license/fax/date strings (e.g. "6550-00427370", coords, dates)
        if len(digits_only) < 7 or len(digits_only) > 15:
            return FieldVerificationResult(
                field_name="phone",
                value=raw,
                source=source,
                verification_status=VerificationStatus.REJECTED,
                confidence_score=0.0,
                evidence={"reason": f"Invalid digit count ({len(digits_only)} digits)", "digits": digits_only},
            )

        # In NANP (US/Canada), numbers are 10 digits or 11 digits starting with 1.
        # Numbers without a '+' that have 12+ digits or invalid NANP area codes (starting with 0/1) are malformed internal IDs.
        if not raw.startswith("+"):
            if len(digits_only) > 11 or (len(digits_only) == 11 and not digits_only.startswith("1")):
                return FieldVerificationResult(
                    field_name="phone",
                    value=raw,
                    source=source,
                    verification_status=VerificationStatus.REJECTED,
                    confidence_score=0.0,
                    evidence={"reason": "Malformed non-standard phone or internal ID format", "digits": digits_only},
                )
            if len(digits_only) == 10 and digits_only[0] in ("0", "1"):
                return FieldVerificationResult(
                    field_name="phone",
                    value=raw,
                    source=source,
                    verification_status=VerificationStatus.REJECTED,
                    confidence_score=0.0,
                    evidence={"reason": "Invalid NANP area code starting with 0 or 1", "digits": digits_only},
                )

        # Reject all identical digits (e.g. 0000000) or test sequences
        if len(set(digits_only)) == 1 or digits_only in ("1234567", "12345678", "123456789", "1234567890", "9876543210"):
            return FieldVerificationResult(
                field_name="phone",
                value=raw,
                source=source,
                verification_status=VerificationStatus.REJECTED,
                confidence_score=0.0,
                evidence={"reason": "Dummy or test number sequence", "digits": digits_only},
            )

        # 3b. Geographic Area Code Consistency
        area_code = extract_nanp_area_code(raw)
        state_code = resolve_state_code(target_state or target_location)
        city_clean = str(target_city or target_location or "").lower().strip()

        evidence_info: dict[str, Any] = {"digits": digits_only, "area_code": area_code}

        if not area_code:
            # International or non-NANP standard phone number
            return FieldVerificationResult(
                field_name="phone",
                value=raw,
                source=source,
                verification_status=VerificationStatus.VERIFIED,
                confidence_score=0.85,
                evidence=evidence_info,
            )

        # Check toll-free
        if area_code in TOLL_FREE_AREA_CODES:
            evidence_info["geo_match"] = "TOLL_FREE"
            return FieldVerificationResult(
                field_name="phone",
                value=raw,
                source=source,
                verification_status=VerificationStatus.VERIFIED,
                confidence_score=0.85,
                evidence=evidence_info,
            )

        # Check city metro match
        for city_name, city_codes in KEY_CITY_AREA_CODES.items():
            if city_name in city_clean and area_code in city_codes:
                evidence_info["geo_match"] = "LOCAL_METRO_MATCH"
                evidence_info["city"] = city_name
                return FieldVerificationResult(
                    field_name="phone",
                    value=raw,
                    source=source,
                    verification_status=VerificationStatus.VERIFIED,
                    confidence_score=0.98,
                    evidence=evidence_info,
                )

        # Check state level match
        if state_code and state_code in US_STATE_AREA_CODES:
            valid_state_codes = US_STATE_AREA_CODES[state_code]
            if area_code in valid_state_codes:
                evidence_info["geo_match"] = "STATE_LEVEL_MATCH"
                evidence_info["state"] = state_code
                return FieldVerificationResult(
                    field_name="phone",
                    value=raw,
                    source=source,
                    verification_status=VerificationStatus.VERIFIED,
                    confidence_score=0.90,
                    evidence=evidence_info,
                )
            else:
                evidence_info["geo_match"] = "OUT_OF_STATE_MISMATCH"
                evidence_info["expected_state"] = state_code
                return FieldVerificationResult(
                    field_name="phone",
                    value=raw,
                    source=source,
                    verification_status=VerificationStatus.UNVERIFIED,
                    confidence_score=0.45,
                    evidence=evidence_info,
                )

        return FieldVerificationResult(
            field_name="phone",
            value=raw,
            source=source,
            verification_status=VerificationStatus.VERIFIED,
            confidence_score=0.85,
            evidence=evidence_info,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Email Verification (Syntax, Telemetry Exclusions, Domain Alignment)
    # ─────────────────────────────────────────────────────────────────────────
    @classmethod
    def verify_email(
        cls,
        email: str | None,
        verified_website: str | None = None,
        business_name: str | None = None,
        source: str = "raw_source",
    ) -> FieldVerificationResult:
        if cls.is_invalid_string(email):
            return FieldVerificationResult(
                field_name="email",
                value=None,
                source=source,
                verification_status=VerificationStatus.UNVERIFIED,
                confidence_score=0.0,
                evidence={"reason": "No email address provided"},
            )

        raw = str(email).strip().lower()

        # Email format check
        email_regex = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
        if not re.match(email_regex, raw):
            return FieldVerificationResult(
                field_name="email",
                value=raw,
                source=source,
                verification_status=VerificationStatus.REJECTED,
                confidence_score=0.0,
                evidence={"reason": "Invalid RFC email format"},
            )

        domain = raw.split("@")[-1]

        # 4a. Exclude Telemetry / Sentry / Dummy domains
        if any(bad in domain for bad in ("sentry", "wixpress.com", "cloudflare.com", "schema.org", "w3.org")) or domain in TELEMETRY_AND_DUMMY_EMAIL_DOMAINS:
            return FieldVerificationResult(
                field_name="email",
                value=raw,
                source=source,
                verification_status=VerificationStatus.REJECTED,
                confidence_score=0.0,
                evidence={"reason": "Telemetry, error reporting, or dummy domain", "domain": domain},
            )

        # 4b. Domain alignment against verified website
        web_domain = ""
        if verified_website:
            try:
                p = urlparse(verified_website)
                web_domain = p.hostname.lower() if p.hostname else ""
                web_domain = re.sub(r"^(?:www\.)?", "", web_domain)
            except Exception:
                pass

        if web_domain and (domain == web_domain or domain.endswith(f".{web_domain}") or web_domain.endswith(f".{domain}")):
            return FieldVerificationResult(
                field_name="email",
                value=raw,
                source=source,
                verification_status=VerificationStatus.VERIFIED,
                confidence_score=0.98,
                evidence={"domain": domain, "domain_match": "MATCHES_OFFICIAL_WEBSITE"},
            )

        # Common free email providers (e.g. gmail.com for local trades / restaurants)
        if domain in COMMON_FREE_EMAIL_HOSTS:
            return FieldVerificationResult(
                field_name="email",
                value=raw,
                source=source,
                verification_status=VerificationStatus.VERIFIED,
                confidence_score=0.80,
                evidence={"domain": domain, "domain_match": "STANDARD_HOST_EMAIL"},
            )

        # Check brand tokens in email domain or username
        b_tokens = set(re.findall(r"[a-z0-9]+", str(business_name or "").lower()))
        em_tokens = set(re.findall(r"[a-z0-9]+", raw))
        if b_tokens.intersection(em_tokens):
            return FieldVerificationResult(
                field_name="email",
                value=raw,
                source=source,
                verification_status=VerificationStatus.VERIFIED,
                confidence_score=0.88,
                evidence={"domain": domain, "domain_match": "BRAND_TOKEN_MATCH"},
            )

        return FieldVerificationResult(
            field_name="email",
            value=raw,
            source=source,
            verification_status=VerificationStatus.INCONCLUSIVE,
            confidence_score=0.55,
            evidence={"domain": domain, "domain_match": "UNLINKED_DOMAIN"},
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 5. Location Verification (Address, City, State, Postal Code)
    # ─────────────────────────────────────────────────────────────────────────
    @classmethod
    def verify_location(
        cls,
        address: str | None = None,
        city: str | None = None,
        state: str | None = None,
        postal_code: str | None = None,
        target_location: str | None = None,
        source: str = "raw_source",
    ) -> FieldVerificationResult:
        loc_str = str(address or city or "").strip()
        if not loc_str or cls.is_invalid_string(loc_str):
            return FieldVerificationResult(
                field_name="location",
                value=None,
                source=source,
                verification_status=VerificationStatus.UNVERIFIED,
                confidence_score=0.0,
                evidence={"reason": "No geographic location data"},
            )

        score = 0.70
        checks: list[str] = []
        if address and not cls.is_invalid_string(address):
            score += 0.15
            checks.append("street_address_present")
        if postal_code and re.search(r"\b\d{5}(?:-\d{4})?\b", str(postal_code)):
            score += 0.10
            checks.append("valid_us_postal_code")

        state_code = resolve_state_code(state or target_location)
        if state_code:
            checks.append(f"resolved_state_{state_code}")

        return FieldVerificationResult(
            field_name="location",
            value={"address": address, "city": city, "state": state, "postal_code": postal_code},
            source=source,
            verification_status=VerificationStatus.VERIFIED,
            confidence_score=min(1.0, score),
            evidence={"checks_passed": checks, "target_location": target_location},
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 6. Social URLs Verification
    # ─────────────────────────────────────────────────────────────────────────
    @classmethod
    def verify_social_urls(
        cls, social_profiles: dict[str, str] | None, source: str = "raw_source"
    ) -> FieldVerificationResult:
        if not social_profiles or not isinstance(social_profiles, dict):
            return FieldVerificationResult(
                field_name="social_urls",
                value={},
                source=source,
                verification_status=VerificationStatus.UNVERIFIED,
                confidence_score=0.0,
                evidence={"reason": "No social profile links found"},
            )

        valid_profiles: dict[str, str] = {}
        for platform, url in social_profiles.items():
            if url and not cls.is_invalid_string(url):
                # Ensure it is not just bare homepage
                p_url = str(url).strip()
                if not re.match(r"^https?://(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]+/?$", p_url):
                    valid_profiles[platform] = p_url

        if not valid_profiles:
            return FieldVerificationResult(
                field_name="social_urls",
                value={},
                source=source,
                verification_status=VerificationStatus.UNVERIFIED,
                confidence_score=0.0,
                evidence={"reason": "Social URLs were bare platform homepages"},
            )

        return FieldVerificationResult(
            field_name="social_urls",
            value=valid_profiles,
            source=source,
            verification_status=VerificationStatus.VERIFIED,
            confidence_score=0.90,
            evidence={"verified_platforms": list(valid_profiles.keys())},
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Master Candidate Verification & Evidence Aggregator
    # ─────────────────────────────────────────────────────────────────────────
    @classmethod
    def verify_candidate(
        cls,
        business_name: str | None,
        website: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        address: str | None = None,
        city: str | None = None,
        state: str | None = None,
        postal_code: str | None = None,
        social_profiles: dict[str, str] | None = None,
        target_location: str | None = None,
        source: str = "discovery",
        page_title: str | None = None,
        h1_tags: list[str] | None = None,
        schema_name: str | None = None,
    ) -> OverallVerificationResult:
        """Executes independent verification across all fields and computes composite confidence."""
        name_res = cls.verify_business_name(business_name, source=source)
        web_res = cls.verify_website(
            website, business_name, source=source,
            page_title=page_title, h1_tags=h1_tags, schema_name=schema_name,
        )
        effective_website = web_res.value if web_res.verification_status == VerificationStatus.VERIFIED else None

        phone_res = cls.verify_phone(
            phone, source=source,
            target_city=city, target_state=state, target_location=target_location,
        )
        email_res = cls.verify_email(
            email, verified_website=effective_website,
            business_name=business_name, source=source,
        )
        loc_res = cls.verify_location(
            address=address, city=city, state=state,
            postal_code=postal_code, target_location=target_location, source=source,
        )
        soc_res = cls.verify_social_urls(social_profiles, source=source)

        field_results = {
            "business_name": name_res,
            "website": web_res,
            "phone": phone_res,
            "email": email_res,
            "location": loc_res,
            "social_urls": soc_res,
        }

        rejections: list[str] = []
        if name_res.verification_status == VerificationStatus.REJECTED:
            rejections.append(f"Business name rejected: {name_res.evidence.get('reason')}")

        is_verified_entity = name_res.verification_status == VerificationStatus.VERIFIED
        has_verified_contact = (
            phone_res.verification_status == VerificationStatus.VERIFIED
            or email_res.verification_status == VerificationStatus.VERIFIED
            or web_res.verification_status == VerificationStatus.VERIFIED
            or soc_res.verification_status == VerificationStatus.VERIFIED
        )

        # Composite verification confidence calculation
        weights = {
            "business_name": 0.30,
            "website": 0.25,
            "phone": 0.20,
            "email": 0.15,
            "location": 0.10,
        }
        composite_score = (
            (name_res.confidence_score * weights["business_name"])
            + (web_res.confidence_score * weights["website"])
            + (phone_res.confidence_score * weights["phone"])
            + (email_res.confidence_score * weights["email"])
            + (loc_res.confidence_score * weights["location"])
        )

        # Decision
        if not is_verified_entity:
            decision = "REJECT"
        elif not has_verified_contact:
            decision = "UNVERIFIED"
        else:
            decision = "ACCEPT"

        # Structured evidence records ready for DB persistence
        evidence_records: list[dict[str, Any]] = []
        for f_name, f_res in field_results.items():
            if f_res.value is not None and f_res.verification_status != VerificationStatus.UNVERIFIED:
                evidence_records.append({
                    "field_name": f_name,
                    "status": f_res.verification_status.value,
                    "confidence_score": int(round(f_res.confidence_score * 100)),
                    "source": f_res.source,
                    "details": {
                        "value": str(f_res.value)[:255] if not isinstance(f_res.value, dict) else f_res.value,
                        **f_res.evidence,
                    },
                })

        return OverallVerificationResult(
            decision=decision,
            composite_confidence=round(composite_score, 2),
            field_results=field_results,
            is_verified_entity=is_verified_entity,
            has_verified_contact=has_verified_contact,
            rejection_reasons=rejections,
            evidence_records=evidence_records,
        )