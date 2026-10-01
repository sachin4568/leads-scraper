from __future__ import annotations

import pytest
from backend.app.intelligence.lead_intelligence import (
    LeadIntelligenceEngine,
    OpportunityCategory,
)


def test_high_opportunity_lead():
    """Weak website (unencrypted, bad SEO) with strong contactability produces HIGH or VERY_HIGH opportunity."""
    report = LeadIntelligenceEngine.evaluate_lead(
        business_name="Downtown Dental Clinic",
        website="http://downtowndental.com",  # Missing HTTPS
        phone="+91 9820112233",
        email="appointments@downtowndental.com",
        genuineness_score=0.90,
        website_health={"is_reachable": True, "is_https": False},
        contacts_evidence={"whatsapp_links": ["https://wa.me/919820112233"], "addresses": [{"address": "Downtown"}]},
        seo_evidence={"seo_score": 40, "title": "Home", "meta_description": ""},
        social_evidence={"profiles": {}},  # Missing all socials
    )

    assert report.overall_opportunity_score >= 65
    assert report.opportunity_category in (OpportunityCategory.HIGH, OpportunityCategory.VERY_HIGH)
    assert report.contactability_score >= 80
    assert report.website_opportunity_score >= 60
    assert len(report.top_reasons) > 0
    assert any("HTTPS" in r for r in report.top_reasons)


def test_low_opportunity_lead():
    """Flawless website with strong SEO, HTTPS, Schema.org, and all social channels produces LOW or MINIMAL opportunity."""
    report = LeadIntelligenceEngine.evaluate_lead(
        business_name="Apex Global Law",
        website="https://apexlaw.com",
        phone="+91 9820999999",
        email="contact@apexlaw.com",
        genuineness_score=0.95,
        website_health={"is_reachable": True, "is_https": True},
        contacts_evidence={"whatsapp_links": [], "addresses": [{"address": "Apex Tower"}]},
        seo_evidence={
            "seo_score": 100,
            "title": "Apex Global Law - Corporate Litigation Attorneys",
            "meta_description": "Premier corporate litigation and international dispute attorneys.",
            "canonical_url": "https://apexlaw.com/",
            "h1_tags": ["Apex Global Law"],
            "og_title": "Apex Global Law",
            "schema_types": ["LegalService"],
        },
        social_evidence={
            "profiles": {
                "instagram": "https://instagram.com/apexlaw",
                "facebook": "https://facebook.com/apexlaw",
                "linkedin": "https://linkedin.com/company/apexlaw",
                "x": "https://x.com/apexlaw",
                "youtube": "https://youtube.com/@apexlaw",
            }
        },
    )

    # Low website improvement opportunity
    assert report.website_opportunity_score <= 25
    assert report.seo_opportunity_score <= 20
    assert report.digital_presence_gap_score == 0
    assert report.overall_opportunity_score < 45
    assert report.opportunity_category in (OpportunityCategory.LOW, OpportunityCategory.MINIMAL)


def test_no_website_lead():
    """Lead without a website receives maximum website development opportunity score (95)."""
    report = LeadIntelligenceEngine.evaluate_lead(
        business_name="Local Corner Bakery",
        website=None,
        phone="+91 9820000000",
        genuineness_score=0.85,
    )

    assert report.website_opportunity_score == 95
    assert report.service_opportunities["WEBSITE_DEVELOPMENT"].eligible is True
    assert report.service_opportunities["WEBSITE_DEVELOPMENT"].opportunity_score == 95
    assert any("No website detected" in r for r in report.top_reasons)


def test_contactability_progression():
    """Verifies that multiple contact channels (Phone + Email + WhatsApp) yield higher contactability than phone alone."""
    phone_only_score, _ = LeadIntelligenceEngine.calculate_contactability(phone="+91 9820112233")
    multi_channel_score, _ = LeadIntelligenceEngine.calculate_contactability(
        phone="+91 9820112233",
        email="info@test.com",
        whatsapp_links=["https://wa.me/919820112233"],
        social_profiles={"instagram": "https://instagram.com/test"},
    )

    assert phone_only_score == 35
    assert multi_channel_score == 95
    assert multi_channel_score > phone_only_score


def test_conflicting_data_handling():
    """Verifies that conflicting provider vs website evidence triggers DATA_CONFLICT and reduces confidence."""
    conflict_data = {
        "phone": {
            "provider_value": "+91 9999999999",
            "website_values": ["+91 8888888888"],
            "conflict": True,
        }
    }

    report = LeadIntelligenceEngine.evaluate_lead(
        business_name="Conflict Cafe",
        website="https://conflictcafe.com",
        phone="+91 9999999999",
        genuineness_score=0.90,
        conflicts_evidence=conflict_data,
    )

    assert report.has_conflict is True
    assert report.confidence_score < 0.90  # Confidence reduced
    assert any("DATA_CONFLICT" in r for r in report.top_reasons)


def test_genuineness_vs_opportunity_independence():
    """Verifies that genuineness score (legitimacy) and opportunity score (sales pitch value) remain independent."""
    # Highly genuine business with low opportunity (everything already optimized)
    rep1 = LeadIntelligenceEngine.evaluate_lead(
        business_name="Big Tech Corp",
        website="https://bigtech.com",
        phone="1234567890",
        genuineness_score=0.99,
        seo_evidence={"seo_score": 100, "title": "Big Tech Corp - Leading Enterprise Solutions", "meta_description": "Global enterprise solutions.", "canonical_url": "https://bigtech.com", "h1_tags": ["Home"], "og_title": "Big Tech"},
        social_evidence={"profiles": {"facebook": "fb", "instagram": "ig", "linkedin": "li", "x": "x", "youtube": "yt"}},
    )
    assert rep1.genuineness_score == 0.99
    assert rep1.overall_opportunity_score <= 35

    # Genuine small business with high opportunity (no website, high contactability)
    rep2 = LeadIntelligenceEngine.evaluate_lead(
        business_name="Mom & Pop Diner",
        website=None,
        phone="9820112233",
        email="diner@gmail.com",
        genuineness_score=0.90,
    )
    assert rep2.genuineness_score == 0.90
    assert rep2.overall_opportunity_score >= 60


def test_explainability_and_determinism():
    """Verifies that scores are 100% deterministic and accompanied by explicit human-readable reasons."""
    kwargs = dict(
        business_name="Deterministic Test Co",
        website="https://detco.in",
        phone="+91 9820112233",
        email="test@detco.in",
        genuineness_score=0.85,
        seo_evidence={"seo_score": 60, "title": "Det Co", "meta_description": "Short"},
        social_evidence={"profiles": {"instagram": "https://instagram.com/detco"}},
    )

    run1 = LeadIntelligenceEngine.evaluate_lead(**kwargs)
    run2 = LeadIntelligenceEngine.evaluate_lead(**kwargs)

    # Strict Determinism
    assert run1.overall_opportunity_score == run2.overall_opportunity_score
    assert run1.contactability_score == run2.contactability_score
    assert run1.website_opportunity_score == run2.website_opportunity_score
    assert run1.top_reasons == run2.top_reasons

    # Explainability: every non-zero score is backed by clear reasons
    assert len(run1.top_reasons) >= 3
