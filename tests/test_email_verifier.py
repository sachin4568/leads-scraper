from __future__ import annotations

from unittest.mock import patch

from backend.app.enrichment.email_verifier import EmailVerifier


def test_email_verifier_valid_email() -> None:
    verifier = EmailVerifier()
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 80))]):
        res = verifier.verify("alex.smith@acmeplumbingcorp.com")
        assert res.is_valid is True
        assert res.syntax_valid is True
        assert res.has_mx_records is True
        assert res.is_disposable is False
        assert res.domain == "acmeplumbingcorp.com"


def test_email_verifier_invalid_syntax() -> None:
    verifier = EmailVerifier()
    res1 = verifier.verify("not-an-email")
    assert res1.is_valid is False
    assert res1.syntax_valid is False

    res2 = verifier.verify("user@")
    assert res2.is_valid is False
    assert res2.syntax_valid is False

    res3 = verifier.verify("213-34-21@32-294")
    assert res3.is_valid is False
    assert res3.syntax_valid is False


def test_email_verifier_disposable_domain() -> None:
    verifier = EmailVerifier()
    res = verifier.verify("user123@mailinator.com")
    assert res.is_valid is False
    assert res.syntax_valid is True
    assert res.is_disposable is True
    assert "Disposable" in res.error_message


def test_email_verifier_rejects_consumer_provider_when_business_domain_required() -> None:
    res = EmailVerifier().verify("hello@gmail.com", require_business_domain=True)

    assert res.is_valid is False
    assert res.syntax_valid is True
    assert "Consumer email provider" in res.error_message


def test_email_verifier_accepts_legitimate_provider_and_digits() -> None:
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("142.250.190.46", 80))]):
        res = EmailVerifier().verify("plumber.john42@gmail.com", require_business_domain=False)
        assert res.is_valid is True
        assert res.syntax_valid is True
        assert res.has_mx_records is True
        assert res.is_generic_provider is True
        assert res.deliverability_status == "DELIVERABILITY_UNKNOWN"


def test_email_verifier_rejects_fabricated_email_without_source() -> None:
    res = EmailVerifier().verify("jane.doe@company.com", source_backed=False)
    assert res.is_valid is False
    assert "source evidence" in res.error_message.lower()


def test_email_verifier_can_require_business_domain_match() -> None:
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 80))]):
        res = EmailVerifier().verify(
            "person@unrelated.com",
            business_name="Acme Plumbing",
            website="https://acmeplumbing.com",
            require_business_domain=True,
        )

    assert res.is_valid is False
    assert res.domain_matched is False


def test_email_verifier_dns_failure() -> None:
    verifier = EmailVerifier()
    with patch("socket.getaddrinfo", side_effect=OSError("DNS error")):
        res = verifier.verify("contact@nonexistent-domain-987654.com")
        assert res.is_valid is False
        assert res.syntax_valid is True
        assert res.has_mx_records is False
        assert "DNS" in res.error_message
