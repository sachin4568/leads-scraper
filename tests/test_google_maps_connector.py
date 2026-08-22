from __future__ import annotations

import pytest
import respx
from httpx import Response

from backend.app.sources.google_maps import PLACES_TEXT_SEARCH_URL, GoogleMapsConnector


@pytest.fixture(autouse=True)
def mock_dns(monkeypatch) -> None:
    def mock_getaddrinfo(host, port, *args, **kwargs):
        if host == "maps.googleapis.com":
            return [(None, None, None, None, ("142.250.190.46", 443))]
        raise OSError(f"Unmocked host {host}")

    monkeypatch.setattr("socket.getaddrinfo", mock_getaddrinfo)


@respx.mock
def test_google_maps_connector_search_success() -> None:
    mock_payload = {
        "results": [
            {
                "place_id": "ChIJ12345",
                "name": "Metro Dental Clinic",
                "formatted_address": "123 Main St, New Delhi, India",
                "formatted_phone_number": "+91 98765 43210",
                "website": "https://metrodental.example.com",
                "types": ["dentist", "health"],
                "rating": 4.8,
            }
        ]
    }
    respx.get(PLACES_TEXT_SEARCH_URL).mock(return_value=Response(200, json=mock_payload))

    connector = GoogleMapsConnector(api_key="test-api-key")
    leads = connector.search_leads(query="Dental Clinic", location="New Delhi")

    assert len(leads) == 1
    lead = leads[0]
    assert lead.source == "google_maps"
    assert lead.source_id == "ChIJ12345"
    assert lead.business_name == "Metro Dental Clinic"
    assert lead.phone == "+91 98765 43210"
    assert lead.website == "https://metrodental.example.com"
    assert lead.category == "dentist"
    assert lead.raw_data["rating"] == 4.8


@respx.mock
def test_google_maps_connector_circuit_breaker_on_errors() -> None:
    connector = GoogleMapsConnector(failure_threshold=2)
    respx.get(PLACES_TEXT_SEARCH_URL).mock(
        return_value=Response(500, json={"error": "Internal Error"})
    )

    assert connector.is_circuit_open() is False

    results1 = connector.search_leads(query="Clinics")
    assert results1 == []
    assert connector.failure_count == 1
    assert connector.is_circuit_open() is False

    results2 = connector.search_leads(query="Clinics")
    assert results2 == []
    assert connector.failure_count == 2
    assert connector.is_circuit_open() is True

    # Circuit open should block further attempts
    results3 = connector.search_leads(query="Clinics")
    assert results3 == []


@respx.mock
def test_google_maps_health_check() -> None:
    connector = GoogleMapsConnector()
    respx.get(PLACES_TEXT_SEARCH_URL).mock(return_value=Response(200, json={"results": []}))

    assert connector.health_check() is True
