from __future__ import annotations

import pytest

from backend.app.services.classification_agent import (
    MultiLabelClassificationAgent,
)
from backend.app.services.formatter import LeadDataFormatter
from backend.app.services.service_engine import ServiceOpportunityEngine


@pytest.fixture
def sample_raw_leads():
    return [
        {
            "canonical_lead_id": "lead_test_001",
            "business_name": "Nairobi Dental Spa",
            "country": "Kenya",
            "state": "Nairobi County",
            "city": "Nairobi",
            "industry": "Dental Clinics",
            "website": None,  # High Web Dev
            "email": "nairobi@dentalspa.co.ke",
            "phone": "+254 700 123456",
            "instagram": "https://instagram.com/nairobi_dental",
            "facebook": "https://facebook.com/nairobidental",
            "prediction": {"probability": 0.88, "decision": "GENUINE"},
            "prediction_time_features": {
                "google_rating": 4.7,
                "review_count": 55,
                "website_state": "no_website",
                "contactability": "OWNER_CONTACT",
                "business_maturity": "SMALL_BUSINESS",
            },
        },
        {
            "canonical_lead_id": "lead_test_002",
            "business_name": "Austin Solar Energy",
            "country": "United States",
            "state": "Texas",
            "city": "Austin",
            "industry": "Solar",
            "website": "https://www.austinsolar.com",
            "email": "info@austinsolar.com",
            "phone": "+1 512 555 0199",
            "instagram": "https://instagram.com/austin_solar",
            "facebook": "https://facebook.com/austinsolar",
            "ssl_valid": False,  # SEO Opportunity
            "facebook_ads_detected": True,  # Marketing Opportunity
            "prediction": {"probability": 0.94, "decision": "GENUINE"},
            "prediction_time_features": {
                "google_rating": 4.9,
                "review_count": 120,
                "website_state": "active",
                "contactability": "OWNER_CONTACT",
                "business_maturity": "SMALL_BUSINESS",
            },
        },
    ]


def test_data_loss_prevention_invariant(sample_raw_leads) -> None:
    raw_count_before = len(sample_raw_leads)
    classified, summary = MultiLabelClassificationAgent.process_master_batch(sample_raw_leads)
    raw_count_after = len(classified)

    assert raw_count_before == raw_count_after
    assert summary.data_loss_audit_passed is True


def test_multi_label_service_classification(sample_raw_leads) -> None:
    lead_1 = MultiLabelClassificationAgent.classify_lead(sample_raw_leads[0])
    c_map_1 = lead_1["service_classifications"]

    # Lead 1: Web Dev (Y), SEO (N), Social Mgmt (Y), Social Mktg (Y)
    assert c_map_1["website_development"]["eligible"] is True
    assert c_map_1["website_seo"]["eligible"] is False
    assert c_map_1["social_media_management"]["eligible"] is True
    assert c_map_1["social_media_marketing"]["eligible"] is True


def test_yn_binary_presence_formatting(sample_raw_leads) -> None:
    formatted_1 = LeadDataFormatter.format_master_lead_payload(sample_raw_leads[0])
    assert formatted_1["website_available"] == "N"
    assert formatted_1["email_available"] == "Y"
    assert formatted_1["phone_available"] == "Y"
    assert formatted_1["instagram_available"] == "Y"
    assert formatted_1["facebook_available"] == "Y"

    formatted_2 = LeadDataFormatter.format_master_lead_payload(sample_raw_leads[1])
    assert formatted_2["website_available"] == "Y"
    assert formatted_2["ssl_valid"] == "N"
    assert formatted_2["facebook_ads_detected"] == "Y"


def test_numerical_fields_preservation(sample_raw_leads) -> None:
    formatted_1 = LeadDataFormatter.format_master_lead_payload(sample_raw_leads[0])
    assert isinstance(formatted_1["google_rating"], float)
    assert isinstance(formatted_1["review_count"], int)
    assert isinstance(formatted_1["genuineness_probability"], float)
    assert formatted_1["google_rating"] == 4.7
    assert formatted_1["review_count"] == 55


def test_explainable_service_scores_and_reasons(sample_raw_leads) -> None:
    eval_res = ServiceOpportunityEngine.evaluate_all_services(sample_raw_leads[0])
    dev_res = eval_res["WEBSITE_DEVELOPMENT"]

    assert 0.0 <= dev_res.score <= 100.0
    assert len(dev_res.reasons) > 0
    assert "No website detected" in dev_res.reasons[0]


def test_country_hierarchy_support(sample_raw_leads) -> None:
    f_kenya = LeadDataFormatter.format_master_lead_payload(sample_raw_leads[0])
    assert f_kenya["country"] == "Kenya"
    assert f_kenya["city"] == "Nairobi"

    f_us = LeadDataFormatter.format_master_lead_payload(sample_raw_leads[1])
    assert f_us["country"] == "United States"
    assert f_us["city"] == "Austin"


def test_frozen_ml_predictions_untouched(sample_raw_leads) -> None:
    lead_1 = MultiLabelClassificationAgent.classify_lead(sample_raw_leads[0])
    assert lead_1["genuineness_probability"] == 0.88
    assert lead_1["genuineness_decision"] == "GENUINE"
