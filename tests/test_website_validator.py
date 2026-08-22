from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.app.enrichment.website_validator import WebsiteValidator


def test_website_validator_rejects_ssrf_urls() -> None:
    validator = WebsiteValidator()

    # Private IP
    res1 = validator.validate("http://10.0.0.1")
    assert res1.is_valid is False
    assert "SSRF" in res1.error_message

    # AWS Cloud Metadata
    res2 = validator.validate("http://169.254.169.254")
    assert res2.is_valid is False
    assert "SSRF" in res2.error_message

    # Loopback IP
    res3 = validator.validate("http://127.0.0.1")
    assert res3.is_valid is False
    assert "SSRF" in res3.error_message


def test_website_validator_handles_dns_failure() -> None:
    validator = WebsiteValidator()
    res = validator.validate("https://nonexistent-domain-123456789.com")
    assert res.is_valid is False
    assert res.dns_resolved is False
    assert (
        "DNS" in res.error_message
        or "SSRF" in res.error_message
        or "Could not resolve" in res.error_message
    )


def test_website_validator_success_flow() -> None:
    validator = WebsiteValidator()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.url = "https://example.com"

    with (
        patch(
            "backend.app.enrichment.website_validator.validate_outbound_url",
            return_value="https://example.com",
        ),
        patch("socket.create_connection"),
        patch("ssl.create_default_context"),
        patch("httpx.Client.get", return_value=mock_response),
    ):
        res = validator.validate("https://example.com")
        assert res.is_valid is True
        assert res.http_status == 200
        assert res.dns_resolved is True
        assert res.final_url == "https://example.com"
