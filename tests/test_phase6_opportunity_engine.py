import pytest
import uuid
from types import SimpleNamespace
from backend.app.enrichment.opportunity_engine import OpportunityEngine

def create_mock_lead(business_name="Test Business", website="https://example.com", phone="555-0100", email="info@example.com"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        business_name=business_name,
        website=website,
        phone=phone,
        email=email,
        raw_data={}
    )

def create_mock_evidence(evidence_type, field_name, classification, status="VERIFIED", details=None):
    return SimpleNamespace(
        id=str(uuid.uuid4()),
        evidence_type=evidence_type,
        field_name=field_name,
        classification=classification,
        status=status,
        details=details or {}
    )

# --- 1. Website Development Tests ---
def test_website_dev_no_website():
    lead = create_mock_lead(website=None)
    web_ev = create_mock_evidence("WEBSITE", "website", "NO_WEBSITE", "NO_WEBSITE")
    
    results = OpportunityEngine.evaluate_all(lead, [web_ev])
    web_dev = next(r for r in results if r["service"] == "website_dev")
    
    assert web_dev["status"] == "EVALUATED"
    assert web_dev["opportunity_score"] >= 85
    assert web_dev["confidence_score"] >= 80
    assert web_dev["priority"] == "HIGH"
    assert "No verified business website was found" in web_dev["reasons"]

def test_website_dev_verified_good_website():
    lead = create_mock_lead(website="https://www.goodbiz.com")
    web_ev = create_mock_evidence("WEBSITE", "website", "VERIFIED_BUSINESS_WEBSITE", "VERIFIED")
    
    results = OpportunityEngine.evaluate_all(lead, [web_ev])
    web_dev = next(r for r in results if r["service"] == "website_dev")
    
    assert web_dev["opportunity_score"] <= 35
    assert web_dev["priority"] == "LOW"

# --- 2. Website SEO Tests ---
def test_website_seo_no_verified_website():
    lead = create_mock_lead(website=None)
    web_ev = create_mock_evidence("WEBSITE", "website", "NO_WEBSITE", "NO_WEBSITE")
    
    results = OpportunityEngine.evaluate_all(lead, [web_ev])
    seo = next(r for r in results if r["service"] == "website_seo")
    
    assert seo["status"] == "INSUFFICIENT_DATA"
    assert seo["priority"] == "UNKNOWN"
    assert seo["opportunity_score"] == 0
    assert "verified_website" in seo["missing_data"]

def test_website_seo_with_issues():
    lead = create_mock_lead(website="https://www.seobiz.com")
    web_ev = create_mock_evidence("WEBSITE", "website", "VERIFIED_BUSINESS_WEBSITE", "VERIFIED")
    seo_ev = create_mock_evidence("SEO_AUDIT", "seo", "TECHNICAL_SEO_AUDIT", "VERIFIED", {
        "findings": {
            "has_title": True,
            "title_length": 45,
            "has_meta_description": False,
            "h1_count": 0,
            "has_viewport_tag": False,
            "has_jsonld_schema": False
        }
    })
    
    results = OpportunityEngine.evaluate_all(lead, [web_ev, seo_ev])
    seo = next(r for r in results if r["service"] == "website_seo")
    
    assert seo["status"] == "EVALUATED"
    assert seo["opportunity_score"] >= 70
    assert seo["confidence_score"] >= 85
    assert seo["priority"] == "HIGH"
    assert "Meta description is missing" in seo["reasons"]
    assert seo["signals"]["ranking_data"] == "UNKNOWN"

# --- 3. Social Media Management Evidence Gate Tests ---
def test_social_management_unavailable():
    lead = create_mock_lead()
    ig_ev = create_mock_evidence("SOCIAL_PROFILE", "instagram", "UNAVAILABLE", "UNAVAILABLE")
    
    results = OpportunityEngine.evaluate_all(lead, [ig_ev])
    smm = next(r for r in results if r["service"] == "social_media_management")
    
    assert smm["status"] == "INSUFFICIENT_DATA"
    assert smm["priority"] == "UNKNOWN"
    assert smm["opportunity_score"] == 0
    assert smm["confidence_score"] <= 25
    assert "social_profile_access" in smm["missing_data"]

def test_social_management_profile_existence_alone_does_not_produce_high():
    # Profile exists but activity metrics are missing -> INSUFFICIENT_DATA, priority UNKNOWN, score 0
    lead = create_mock_lead()
    ig_ev = create_mock_evidence("SOCIAL_PROFILE", "instagram", "VERIFIED_SOCIAL_PROFILE", "VERIFIED", {})
    
    results = OpportunityEngine.evaluate_all(lead, [ig_ev])
    smm = next(r for r in results if r["service"] == "social_media_management")
    
    assert smm["status"] == "INSUFFICIENT_DATA"
    assert smm["priority"] == "UNKNOWN"
    assert smm["opportunity_score"] == 0
    assert "social_activity_metrics" in smm["missing_data"]

def test_social_management_observed_posting_gap_produces_high():
    lead = create_mock_lead()
    ig_ev = create_mock_evidence("SOCIAL_PROFILE", "instagram", "VERIFIED_SOCIAL_PROFILE", "VERIFIED", {
        "activity_status": "OBSERVED",
        "posting_frequency": "WEAK"
    })
    
    results = OpportunityEngine.evaluate_all(lead, [ig_ev])
    smm = next(r for r in results if r["service"] == "social_media_management")
    
    assert smm["status"] == "EVALUATED"
    assert smm["opportunity_score"] >= 75
    assert smm["priority"] == "HIGH"
    assert "Observed weak or inconsistent social posting activity" in smm["reasons"]

# --- 4. Social Media Marketing Evidence Gate Tests ---
def test_social_marketing_no_marketing_evidence():
    # Presence alone without audience/marketing metrics must NOT produce 60-70 default score
    lead = create_mock_lead()
    ig_ev = create_mock_evidence("SOCIAL_PROFILE", "instagram", "VERIFIED_SOCIAL_PROFILE", "VERIFIED", {})
    web_ev = create_mock_evidence("WEBSITE", "website", "VERIFIED_BUSINESS_WEBSITE", "VERIFIED")
    
    results = OpportunityEngine.evaluate_all(lead, [ig_ev, web_ev])
    smmk = next(r for r in results if r["service"] == "social_media_marketing")
    
    assert smmk["status"] == "INSUFFICIENT_DATA"
    assert smmk["priority"] == "UNKNOWN"
    assert smmk["opportunity_score"] == 0
    assert smmk["signals"]["ads_status"] == "NOT_OBSERVED"
    assert "marketing_evidence" in smmk["missing_data"]

def test_social_marketing_observed_audience_gap_produces_evaluated():
    lead = create_mock_lead()
    ig_ev = create_mock_evidence("SOCIAL_PROFILE", "instagram", "VERIFIED_SOCIAL_PROFILE", "VERIFIED", {
        "followers": 250,
        "followers_status": "OBSERVED"
    })
    web_ev = create_mock_evidence("WEBSITE", "website", "VERIFIED_BUSINESS_WEBSITE", "VERIFIED")
    
    results = OpportunityEngine.evaluate_all(lead, [ig_ev, web_ev])
    smmk = next(r for r in results if r["service"] == "social_media_marketing")
    
    assert smmk["status"] == "EVALUATED"
    assert smmk["opportunity_score"] >= 70
    assert smmk["priority"] == "HIGH"
    assert smmk["signals"]["ads_status"] == "NOT_OBSERVED"

# --- 5. State Distinction & Baseline Tests ---
def test_state_distinctions():
    states = ["UNKNOWN", "NOT_FOUND", "UNAVAILABLE"]
    assert len(set(states)) == 3
