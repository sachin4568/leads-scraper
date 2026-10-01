from __future__ import annotations

import pytest
from backend.app.verification import (
    VerificationAndEvidenceEngine,
    VerificationStatus,
)
from backend.app.intelligence.lead_intelligence import (
    LeadIntelligenceEngine,
    OpportunityCategory,
)


def test_business_name_verification():
    # Valid commercial entity
    res_valid = VerificationAndEvidenceEngine.verify_business_name("Real Seafood Company")
    assert res_valid.verification_status == VerificationStatus.VERIFIED
    assert res_valid.confidence_score >= 0.90

    # Placeholders
    for placeholder in ["n/a", "unknown business", "---", "test", "demo", "none"]:
        res_ph = VerificationAndEvidenceEngine.verify_business_name(placeholder)
        assert res_ph.verification_status == VerificationStatus.REJECTED
        assert res_ph.confidence_score == 0.0

    # Generic public facility
    res_fac = VerificationAndEvidenceEngine.verify_business_name("Public Toilet")
    assert res_fac.verification_status == VerificationStatus.REJECTED


def test_website_ownership_and_aggregator_rejection():
    # Official brand domain
    res_official = VerificationAndEvidenceEngine.verify_website(
        website="https://www.tiosmexicancafe.com/",
        business_name="Tios Mexican Cafe",
    )
    assert res_official.verification_status == VerificationStatus.VERIFIED
    assert res_official.confidence_score >= 0.85

    # Unofficial menu aggregator domain
    res_agg = VerificationAndEvidenceEngine.verify_website(
        website="https://theolivegardenmenus.us/",
        business_name="Olive Garden",
    )
    assert res_agg.verification_status == VerificationStatus.REJECTED

    # Third party ordering directory
    res_dir = VerificationAndEvidenceEngine.verify_website(
        website="https://northsidegrill.gotoeat.net/menu",
        business_name="Northside Grill",
    )
    assert res_dir.verification_status == VerificationStatus.REJECTED

    # Aggregator directory (Yelp, TripAdvisor, AllMenus)
    for bad_url in [
        "https://www.yelp.com/biz/some-restaurant",
        "https://www.tripadvisor.com/Restaurant_Review-g29556",
        "https://www.allmenus.com/mi/ann-arbor/12345-restaurant",
    ]:
        res_bad = VerificationAndEvidenceEngine.verify_website(bad_url, "Some Restaurant")
        assert res_bad.verification_status == VerificationStatus.REJECTED


def test_phone_number_syntax_and_geo_consistency():
    # Valid local metro match in Ann Arbor MI (Area code 734)
    res_local = VerificationAndEvidenceEngine.verify_phone(
        phone="+1 734 769 5960",
        target_city="Ann Arbor",
        target_state="MI",
    )
    assert res_local.verification_status == VerificationStatus.VERIFIED
    assert res_local.confidence_score >= 0.95
    assert res_local.evidence.get("geo_match") == "LOCAL_METRO_MATCH"

    # Valid state-level match in MI (Area code 313)
    res_state = VerificationAndEvidenceEngine.verify_phone(
        phone="+1 (313) 555-0199",
        target_city="Ann Arbor",
        target_state="MI",
    )
    assert res_state.verification_status == VerificationStatus.VERIFIED
    assert res_state.confidence_score >= 0.85
    assert res_state.evidence.get("geo_match") == "STATE_LEVEL_MATCH"

    # Out of state area code (952 MN in Ann Arbor MI)
    res_mismatch = VerificationAndEvidenceEngine.verify_phone(
        phone="+1 952-467-3334",
        target_city="Ann Arbor",
        target_state="MI",
    )
    assert res_mismatch.verification_status == VerificationStatus.UNVERIFIED
    assert res_mismatch.confidence_score < 0.50
    assert res_mismatch.evidence.get("geo_match") == "OUT_OF_STATE_MISMATCH"

    # Malformed internal license/fax/date format
    res_malformed = VerificationAndEvidenceEngine.verify_phone(
        phone="6550-00427370",
        target_city="Ann Arbor",
        target_state="MI",
    )
    assert res_malformed.verification_status == VerificationStatus.REJECTED
    assert res_malformed.confidence_score == 0.0

    # Dummy repeating sequence
    res_dummy = VerificationAndEvidenceEngine.verify_phone("1111111111")
    assert res_dummy.verification_status == VerificationStatus.REJECTED


def test_email_domain_verification_and_telemetry_exclusion():
    # Official website domain match
    res_official = VerificationAndEvidenceEngine.verify_email(
        email="info@tiosmexicancafe.com",
        verified_website="https://www.tiosmexicancafe.com",
        business_name="Tios Mexican Cafe",
    )
    assert res_official.verification_status == VerificationStatus.VERIFIED
    assert res_official.confidence_score >= 0.95
    assert res_official.evidence.get("domain_match") == "MATCHES_OFFICIAL_WEBSITE"

    # Standard email provider
    res_standard = VerificationAndEvidenceEngine.verify_email(
        email="owner@gmail.com",
        business_name="Tios Mexican Cafe",
    )
    assert res_standard.verification_status == VerificationStatus.VERIFIED
    assert res_standard.confidence_score >= 0.80

    # Sentry / Telemetry / Junk tracking email
    for bad_email in [
        "7c58b1d893b343b6b4a6d266429dac0b@o19836.ingest.sentry.io",
        "feedback@static.wixpress.com",
        "admin@example.com",
    ]:
        res_bad = VerificationAndEvidenceEngine.verify_email(bad_email)
        assert res_bad.verification_status == VerificationStatus.REJECTED
        assert res_bad.confidence_score == 0.0


def test_opportunity_qualification_bounded_by_verification_confidence():
    # High opportunity candidate with LOW verification confidence (unverified candidate)
    report_low_verif = LeadIntelligenceEngine.evaluate_lead(
        business_name="Unverified Plumbing LLC",
        phone=None,
        email=None,
        website=None,
        genuineness_score=0.40,  # low verification confidence
    )
    # Must be capped and never qualify for HIGH or VERY_HIGH
    assert report_low_verif.overall_opportunity_score <= 35
    assert report_low_verif.opportunity_category in (OpportunityCategory.LOW, OpportunityCategory.MINIMAL)

    # High opportunity candidate with HIGH verification confidence
    report_high_verif = LeadIntelligenceEngine.evaluate_lead(
        business_name="Real Seafood Company",
        website="https://realseafoodcorestaurant.com",
        phone="+1 734 769 5960",
        email="info@realseafood.com",
        genuineness_score=0.90,  # verified confidence
        website_health={"is_reachable": True, "is_https": True},
        seo_evidence={"seo_score": 50, "title": "Real Seafood", "meta_description": "", "h1_tags": []},
    )
    assert report_high_verif.opportunity_category in (OpportunityCategory.HIGH, OpportunityCategory.VERY_HIGH)


def test_candidate_verification_overall_flow():
    res = VerificationAndEvidenceEngine.verify_candidate(
        business_name="Pita Kabob Grill",
        website="https://www.pitakabobgrill.com/",
        phone="+1 734 622 8082",
        email=None,
        city="Ann Arbor",
        state="MI",
        target_location="Ann Arbor, MI",
        source="osm_overpass",
    )
    assert res.decision == "ACCEPT"
    assert res.is_verified_entity is True
    assert res.has_verified_contact is True
    assert res.composite_confidence >= 0.70

    # Ensure structured evidence records are present for persistence
    field_names = [e["field_name"] for e in res.evidence_records]
    assert "business_name" in field_names
    assert "website" in field_names
    assert "phone" in field_names