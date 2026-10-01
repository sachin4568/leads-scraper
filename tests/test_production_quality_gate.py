import pytest
from backend.app.intelligence.quality_gate import (
    QualityGateEngine,
    QualityGateDecision,
    RejectionReason,
)
from backend.app.intelligence.lead_intelligence import (
    LeadIntelligenceEngine,
    OpportunityCategory,
)


def test_candidate_with_name_only_is_rejected():
    res = QualityGateEngine.evaluate_candidate(
        business_name="Acme Dental Clinic",
        phone=None,
        email=None,
        website=None,
    )
    assert res.decision == QualityGateDecision.REJECT
    assert res.is_valid is False
    assert res.is_contactable is False
    assert res.rejection_reason == RejectionReason.NO_ACTIONABLE_CONTACT_PATH


def test_candidate_with_name_address_coords_only_is_rejected():
    res = QualityGateEngine.evaluate_candidate(
        business_name="Goregaon Orthodontics",
        address="123 SV Road, Goregaon West",
        city="Mumbai",
        phone=None,
        email=None,
        website=None,
    )
    assert res.decision == QualityGateDecision.REJECT
    assert res.is_contactable is False
    assert res.rejection_reason == RejectionReason.NO_ACTIONABLE_CONTACT_PATH


def test_candidate_with_verified_phone_is_accepted():
    res = QualityGateEngine.evaluate_candidate(
        business_name="Apex Dental Care",
        phone="+91 98201 12345",
        city="Mumbai",
    )
    assert res.decision == QualityGateDecision.ACCEPT
    assert res.is_valid is True
    assert res.is_contactable is True
    assert "PHONE" in res.contact_channels
    assert res.rejection_reason is None


def test_candidate_with_verified_website_is_accepted():
    res = QualityGateEngine.evaluate_candidate(
        business_name="Modern Smile Clinic",
        website="https://www.modernsmilemumbai.in",
        city="Mumbai",
    )
    assert res.decision == QualityGateDecision.ACCEPT
    assert res.is_contactable is True
    assert "WEBSITE" in res.contact_channels


def test_candidate_with_verified_email_is_accepted():
    res = QualityGateEngine.evaluate_candidate(
        business_name="Care First Dental",
        email="contact@carefirstdental.in",
        city="Mumbai",
    )
    assert res.decision == QualityGateDecision.ACCEPT
    assert res.is_contactable is True
    assert "EMAIL" in res.contact_channels


def test_candidate_with_multi_channel_contacts_is_strong():
    res = QualityGateEngine.evaluate_candidate(
        business_name="Elite Dental Studio",
        phone="+91 98200 99999",
        email="info@elitedental.com",
        website="https://elitedental.com",
        social_profiles={"instagram": "https://instagram.com/elitedental"},
    )
    assert res.decision == QualityGateDecision.ACCEPT
    assert len(res.contact_channels) >= 4
    assert res.contactability_score >= 80
    assert res.actionability_score >= 50


def test_candidate_with_blacklisted_aggregator_website_is_rejected():
    res = QualityGateEngine.evaluate_candidate(
        business_name="City Dental",
        website="https://www.yelp.com/biz/city-dental-mumbai",
        phone=None,
    )
    assert res.decision == QualityGateDecision.REJECT
    assert res.rejection_reason == RejectionReason.NO_ACTIONABLE_CONTACT_PATH


def test_candidate_with_invalid_phone_is_rejected():
    # All identical digits
    res1 = QualityGateEngine.evaluate_candidate(
        business_name="Smile Zone",
        phone="0000000000",
    )
    assert res1.decision == QualityGateDecision.REJECT

    # Sequential dummy
    res2 = QualityGateEngine.evaluate_candidate(
        business_name="Smile Zone",
        phone="1234567890",
    )
    assert res2.decision == QualityGateDecision.REJECT


def test_placeholder_strings_never_count_as_valid():
    res = QualityGateEngine.evaluate_candidate(
        business_name="Not available",
        phone="N/A",
        email="null",
        website="none",
    )
    assert res.decision == QualityGateDecision.REJECT
    assert res.rejection_reason == RejectionReason.INVALID_BUSINESS_NAME


def test_generic_facility_is_rejected():
    res = QualityGateEngine.evaluate_candidate(
        business_name="ATM Goregaon Station",
        phone="+91 98201 12345",
    )
    assert res.decision == QualityGateDecision.REJECT
    assert res.rejection_reason == RejectionReason.GENERIC_FACILITY


def test_intelligence_scoring_caps_uncontactable_records():
    report = LeadIntelligenceEngine.evaluate_lead(
        business_name="Ghost Dental",
        website=None,
        phone=None,
        email=None,
    )
    assert report.contactability_score == 0
    assert report.opportunity_category == OpportunityCategory.MINIMAL
    assert report.overall_opportunity_score <= 25


def test_intelligence_scoring_rewards_contactable_leads():
    report = LeadIntelligenceEngine.evaluate_lead(
        business_name="Prime Dental Care",
        website="https://primedental.com",
        phone="+91 98201 12345",
        email="info@primedental.com",
        genuineness_score=0.90,
        seo_evidence={"title": "Prime Dental Clinic"},
    )
    assert report.contactability_score >= 60
    assert report.overall_opportunity_score >= 50
    assert report.opportunity_category in (OpportunityCategory.HIGH, OpportunityCategory.VERY_HIGH, OpportunityCategory.MEDIUM)
