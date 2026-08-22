from __future__ import annotations

import pytest
import respx
from httpx import Response

from backend.app.sources.yelp import YELP_SEARCH_URL, YelpConnector


@pytest.fixture(autouse=True)
def mock_dns(monkeypatch) -> None:
    def mock_getaddrinfo(host, port, *args, **kwargs):
        if host == "api.yelp.com":
            return [(None, None, None, None, ("104.16.54.4", 443))]
        raise OSError(f"Unmocked host {host}")

    monkeypatch.setattr("socket.getaddrinfo", mock_getaddrinfo)


@respx.mock
def test_yelp_connector_search_success() -> None:
    mock_payload = {
        "businesses": [
            {
                "id": "yelp-dentist-delhi",
                "name": "Delhi Smiles Dental Care",
                "url": "https://www.yelp.com/biz/delhi-smiles",
                "display_phone": "+91 11 2345 6789",
                "location": {"display_address": ["Connaught Place", "New Delhi 110001", "India"]},
                "categories": [{"alias": "dentists", "title": "Dentists"}],
                "rating": 4.5,
                "review_count": 89,
            }
        ]
    }
    respx.get(YELP_SEARCH_URL).mock(return_value=Response(200, json=mock_payload))

    connector = YelpConnector(api_key="test-yelp-key")
    leads = connector.search_leads(query="Dentist", location="New Delhi")

    assert len(leads) == 1
    lead = leads[0]
    assert lead.source == "yelp"
    assert lead.source_id == "yelp-dentist-delhi"
    assert lead.business_name == "Delhi Smiles Dental Care"
    assert lead.phone == "+91 11 2345 6789"
    assert lead.website == "https://www.yelp.com/biz/delhi-smiles"
    assert lead.address == "Connaught Place, New Delhi 110001, India"
    assert lead.category == "Dentists"
    assert lead.raw_data["review_count"] == 89


@respx.mock
def test_yelp_connector_circuit_breaker_on_errors() -> None:
    connector = YelpConnector(api_key="mock_yelp_key", failure_threshold=2)
    respx.get(YELP_SEARCH_URL).mock(
        return_value=Response(429, json={"error": "Rate limit exceeded"})
    )

    assert connector.is_circuit_open() is False

    results1 = connector.search_leads(query="Restaurants")
    assert results1 == []
    assert connector.failure_count == 1

    results2 = connector.search_leads(query="Restaurants")
    assert results2 == []
    assert connector.failure_count == 2
    assert connector.is_circuit_open() is True

    # Blocked while circuit is open
    assert connector.search_leads(query="Restaurants") == []


@respx.mock
def test_yelp_health_check() -> None:
    connector = YelpConnector(api_key="test-key")
    respx.get(YELP_SEARCH_URL).mock(return_value=Response(200, json={"businesses": []}))

    assert connector.health_check() is True
