from __future__ import annotations

import pytest
import respx
from httpx import Response

from backend.app.sources.google_search import CUSTOM_SEARCH_URL, GoogleSearchConnector


@pytest.fixture(autouse=True)
def mock_dns(monkeypatch) -> None:
    def mock_getaddrinfo(host, port, *args, **kwargs):
        if host == "www.googleapis.com":
            return [(None, None, None, None, ("142.250.190.46", 443))]
        raise OSError(f"Unmocked host {host}")

    monkeypatch.setattr("socket.getaddrinfo", mock_getaddrinfo)


@respx.mock
def test_google_search_connector_search_success() -> None:
    mock_payload = {
        "items": [
            {
                "title": "Apex Dental Clinic - Best Dentist in Delhi",
                "link": "https://apexdental.example.com",
                "snippet": "Contact Apex Dental Clinic at +91 98765 43210 for appointment booking.",
                "displayLink": "apexdental.example.com",
            }
        ]
    }
    respx.get(CUSTOM_SEARCH_URL).mock(return_value=Response(200, json=mock_payload))

    connector = GoogleSearchConnector(api_key="test-api-key", cse_id="test-cse-id")
    leads = connector.search_leads(query="Dental Clinic", location="Delhi")

    assert len(leads) == 1
    lead = leads[0]
    assert lead.source == "google_search"
    assert lead.source_id == "https://apexdental.example.com"
    assert lead.business_name == "Apex Dental Clinic"
    assert lead.website == "https://apexdental.example.com"
    assert lead.phone == "+91 98765 43210"


@respx.mock
def test_google_search_connector_circuit_breaker_on_errors() -> None:
    connector = GoogleSearchConnector(failure_threshold=2)
    respx.get(CUSTOM_SEARCH_URL).mock(return_value=Response(403, json={"error": "Quota Exceeded"}))

    assert connector.is_circuit_open() is False

    results1 = connector.search_leads(query="SEO Services")
    assert results1 == []
    assert connector.failure_count == 1

    results2 = connector.search_leads(query="SEO Services")
    assert results2 == []
    assert connector.failure_count == 2
    assert connector.is_circuit_open() is True

    # Circuit open prevents request
    assert connector.search_leads(query="SEO Services") == []


@respx.mock
def test_google_search_health_check() -> None:
    connector = GoogleSearchConnector(api_key="test-key", cse_id="test-cx")
    respx.get(CUSTOM_SEARCH_URL).mock(return_value=Response(200, json={"items": []}))

    assert connector.health_check() is True
