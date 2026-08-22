from __future__ import annotations

import pytest
import respx
from httpx import Response

from backend.app.sources.meta import META_GRAPH_PAGES_SEARCH_URL, MetaConnector


@pytest.fixture(autouse=True)
def mock_dns(monkeypatch) -> None:
    def mock_getaddrinfo(host, port, *args, **kwargs):
        if host == "graph.facebook.com":
            return [(None, None, None, None, ("157.240.22.35", 443))]
        raise OSError(f"Unmocked host {host}")

    monkeypatch.setattr("socket.getaddrinfo", mock_getaddrinfo)


@respx.mock
def test_meta_connector_search_success() -> None:
    mock_payload = {
        "data": [
            {
                "id": "102938475",
                "name": "Urban Fitness Studio",
                "website": "https://urbanfitness.example.com",
                "phone": "+1 555 234 5678",
                "single_line_address": "456 Market St, San Francisco, CA",
                "category": "Gym/Physical Fitness Center",
                "fan_count": 12500,
                "verification_status": "verified",
                "instagram_business_account": "urbanfitness_official",
                "has_active_ads": True,
            }
        ]
    }
    respx.get(META_GRAPH_PAGES_SEARCH_URL).mock(return_value=Response(200, json=mock_payload))

    connector = MetaConnector(access_token="test-meta-token")
    leads = connector.search_leads(query="Gym")

    assert len(leads) == 1
    lead = leads[0]
    assert lead.source == "meta"
    assert lead.source_id == "102938475"
    assert lead.business_name == "Urban Fitness Studio"
    assert lead.phone == "+1 555 234 5678"
    assert lead.website == "https://urbanfitness.example.com"
    assert lead.category == "Gym/Physical Fitness Center"

    evidence = lead.raw_data
    assert evidence["facebook_page_id"] == "102938475"
    assert evidence["instagram_business_account"] == "urbanfitness_official"
    assert "ads/library" in evidence["advertising_signals"]["ad_library_url"]
    assert evidence["advertising_signals"]["has_active_ads_signal"] is True


@respx.mock
def test_meta_connector_circuit_breaker_on_errors() -> None:
    connector = MetaConnector(failure_threshold=2)
    respx.get(META_GRAPH_PAGES_SEARCH_URL).mock(
        return_value=Response(401, json={"error": {"message": "Invalid token"}})
    )

    assert connector.is_circuit_open() is False

    results1 = connector.search_leads(query="Fitness")
    assert results1 == []
    assert connector.failure_count == 1

    results2 = connector.search_leads(query="Fitness")
    assert results2 == []
    assert connector.failure_count == 2
    assert connector.is_circuit_open() is True

    # Blocked while circuit is open
    assert connector.search_leads(query="Fitness") == []


@respx.mock
def test_meta_health_check() -> None:
    connector = MetaConnector(access_token="test-token")
    respx.get(META_GRAPH_PAGES_SEARCH_URL).mock(return_value=Response(200, json={"data": []}))

    assert connector.health_check() is True
