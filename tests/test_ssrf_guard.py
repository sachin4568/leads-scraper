from __future__ import annotations

import pytest

from backend.app.security.ssrf_guard import is_ip_blocked, validate_outbound_url


def test_ip_blocking_ranges() -> None:
    assert is_ip_blocked("127.0.0.1") is True
    assert is_ip_blocked("10.0.0.5") is True
    assert is_ip_blocked("172.16.0.1") is True
    assert is_ip_blocked("192.168.1.1") is True
    assert is_ip_blocked("169.254.169.254") is True
    assert is_ip_blocked("::1") is True
    assert is_ip_blocked("fc00::1") is True
    assert is_ip_blocked("8.8.8.8") is False


def test_ssrf_guard_rejects_non_https_by_default() -> None:
    with pytest.raises(ValueError, match="Prohibited scheme"):
        validate_outbound_url("http://example.com")

    with pytest.raises(ValueError, match="Prohibited scheme"):
        validate_outbound_url("ftp://example.com")


def test_ssrf_guard_rejects_loopback_and_metadata_hostnames(monkeypatch) -> None:
    # Mock socket resolution to return blocked IP
    def mock_getaddrinfo(host, port):
        if host == "localhost":
            return [(None, None, None, None, ("127.0.0.1", 443))]
        if host == "metadata.internal":
            return [(None, None, None, None, ("169.254.169.254", 443))]
        return [(None, None, None, None, ("93.184.216.34", 443))]

    monkeypatch.setattr("socket.getaddrinfo", mock_getaddrinfo)

    with pytest.raises(ValueError, match="SSRF Protection"):
        validate_outbound_url("https://localhost/api")

    with pytest.raises(ValueError, match="SSRF Protection"):
        validate_outbound_url("https://metadata.internal/latest")

    assert validate_outbound_url("https://example.com") == "https://example.com"
