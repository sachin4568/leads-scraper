from __future__ import annotations

from unittest.mock import patch

from backend.app.enrichment.email_verifier import EmailVerifier


def test_email_verifier_valid_email() -> None:
    verifier = EmailVerifier()
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 80))]):
        res = verifier.verify("alex.smith@company.com")
        assert res.is_valid is True
        assert res.syntax_valid is True
        assert res.has_mx_records is True
        assert res.is_disposable is False
        assert res.domain == "company.com"


def test_email_verifier_invalid_syntax() -> None:
    verifier = EmailVerifier()
    res1 = verifier.verify("not-an-email")
    assert res1.is_valid is False
    assert res1.syntax_valid is False

    res2 = verifier.verify("user@")
    assert res2.is_valid is False
    assert res2.syntax_valid is False


def test_email_verifier_disposable_domain() -> None:
    verifier = EmailVerifier()
    res = verifier.verify("user123@mailinator.com")
    assert res.is_valid is False
    assert res.syntax_valid is True
    assert res.is_disposable is True
    assert "Disposable" in res.error_message


def test_email_verifier_dns_failure() -> None:
    verifier = EmailVerifier()
    with patch("socket.getaddrinfo", side_effect=OSError("DNS error")):
        res = verifier.verify("user@nonexistent-domain-987654.com")
        assert res.is_valid is False
        assert res.syntax_valid is True
        assert res.has_mx_records is False
        assert "DNS" in res.error_message
