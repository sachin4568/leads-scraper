from __future__ import annotations

from backend.app.enrichment.confidence import ConfidenceScorer
from backend.app.enrichment.email_verifier import EmailVerificationResult
from backend.app.enrichment.phone_validator import PhoneValidationResult
from backend.app.enrichment.website_validator import WebsiteValidationResult


def test_field_confidence_scoring() -> None:
    # Website SSL valid
    web_res = WebsiteValidationResult(
        is_valid=True, ssl_valid=True, http_status=200, dns_resolved=True
    )
    assert ConfidenceScorer.compute_website_confidence(web_res) == 100

    # Email valid with MX
    email_res = EmailVerificationResult(
        is_valid=True, email="user@co.com", syntax_valid=True, has_mx_records=True
    )
    assert ConfidenceScorer.compute_email_confidence(email_res) == 100

    # Phone valid
    phone_res = PhoneValidationResult(
        is_valid=True, original_phone="4155552671", e164_format="+14155552671"
    )
    assert ConfidenceScorer.compute_phone_confidence(phone_res) == 100


def test_overall_lead_confidence_calculation() -> None:
    web_res = WebsiteValidationResult(
        is_valid=True, ssl_valid=True, http_status=200, dns_resolved=True
    )
    email_res = EmailVerificationResult(
        is_valid=True, email="user@co.com", syntax_valid=True, has_mx_records=True
    )
    phone_res = PhoneValidationResult(
        is_valid=True, original_phone="4155552671", e164_format="+14155552671"
    )

    overall, field_scores = ConfidenceScorer.calculate_lead_confidence(
        web_res, email_res, phone_res, source_count=1
    )
    assert overall == 100
    assert field_scores["website"] == 100
    assert field_scores["email"] == 100
    assert field_scores["phone"] == 100


def test_multi_source_bonus() -> None:
    web_res = WebsiteValidationResult(
        is_valid=True, ssl_valid=False, http_status=200, dns_resolved=True
    )  # 80
    email_res = EmailVerificationResult(
        is_valid=True, email="u@c.com", syntax_valid=True, has_mx_records=True
    )  # 100
    phone_res = None  # 0

    # Weighted: (80 * 0.3) + (100 * 0.4) + (0 * 0.3) = 24 + 40 = 64
    score_1_source, _ = ConfidenceScorer.calculate_lead_confidence(
        web_res, email_res, phone_res, source_count=1
    )
    assert score_1_source == 64

    # Multi-source bonus (+5 for 2 sources) -> 69
    score_2_sources, _ = ConfidenceScorer.calculate_lead_confidence(
        web_res, email_res, phone_res, source_count=2
    )
    assert score_2_sources == 69
