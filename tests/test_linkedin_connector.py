from __future__ import annotations

import pytest
import respx
from httpx import Response

from backend.app.sources.linkedin import LINKEDIN_ORGANIZATIONS_URL, LinkedInConnector


@pytest.fixture(autouse=True)
def mock_dns(monkeypatch) -> None:
    def mock_getaddrinfo(host, port, *args, **kwargs):
        if host == "api.linkedin.com":
            return [(None, None, None, None, ("13.107.42.14", 443))]
        raise OSError(f"Unmocked host {host}")

    monkeypatch.setattr("socket.getaddrinfo", mock_getaddrinfo)


@respx.mock
def test_linkedin_connector_search_success() -> None:
    mock_payload = {
        "elements": [
            {
                "id": 1029384,
                "urn": "urn:li:organization:1029384",
                "localizedName": "Acme Tech Solutions",
                "vanityName": "acme-tech",
                "website": "https://acme.example.com",
                "primaryIndustry": "Software Development",
                "locations": [{"address": {"line1": "100 Tech Blvd", "city": "San Francisco"}}],
            }
        ]
    }
    respx.get(LINKEDIN_ORGANIZATIONS_URL).mock(return_value=Response(200, json=mock_payload))

    connector = LinkedInConnector(access_token="test-oauth-token")
    leads = connector.search_leads(query="Acme Tech")

    assert len(leads) == 1
    lead = leads[0]
    assert lead.source == "linkedin"
    assert lead.source_id == "urn:li:organization:1029384"
    assert lead.business_name == "Acme Tech Solutions"
    assert lead.website == "https://acme.example.com"
    assert lead.address == "100 Tech Blvd"
    assert lead.category == "Software Development"


@respx.mock
def test_linkedin_connector_circuit_breaker_on_unauthorized() -> None:
    connector = LinkedInConnector(failure_threshold=2)
    respx.get(LINKEDIN_ORGANIZATIONS_URL).mock(
        return_value=Response(401, json={"message": "Invalid token"})
    )

    assert connector.is_circuit_open() is False

    results1 = connector.search_leads(query="Software")
    assert results1 == []
    assert connector.failure_count == 1

    results2 = connector.search_leads(query="Software")
    assert results2 == []
    assert connector.failure_count == 2
    assert connector.is_circuit_open() is True

    # Blocked while circuit is open
    assert connector.search_leads(query="Software") == []


@respx.mock
def test_linkedin_health_check() -> None:
    connector = LinkedInConnector(access_token="test-token")
    respx.get(LINKEDIN_ORGANIZATIONS_URL).mock(return_value=Response(200, json={"elements": []}))

    assert connector.health_check() is True
