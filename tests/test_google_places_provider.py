from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.app.sources.google_maps import GooglePlacesConnector


def test_google_places_connector_initialization():
    connector = GooglePlacesConnector(api_key="test_key_123")
    assert connector.source_name == "google_places"
    assert connector.api_key == "test_key_123"


def test_google_places_normalization():
    connector = GooglePlacesConnector(api_key="test_key_123")
    raw_payload = {
        "place_id": "ChIJ_test_google_001",
        "name": "Solar Tech Solutions",
        "formatted_address": "123 Energy Way, Austin, TX",
        "formatted_phone_number": "+1 512 555 0100",
        "website": "https://www.solartech.com",
        "types": ["solar_installer", "contractor"],
    }

    record = connector.parse_place_record(raw_payload)
    assert record.source == "google_places"
    assert record.source_id == "ChIJ_test_google_001"
    assert record.business_name == "Solar Tech Solutions"
    assert record.phone == "+1 512 555 0100"
    assert record.website == "https://www.solartech.com"
    assert record.category == "solar_installer"


@patch("httpx.Client.get")
def test_google_places_search_leads_success(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "results": [
            {
                "place_id": "g_001",
                "name": "Austin Dental Care",
                "formatted_address": "456 Main St, Austin, TX",
                "formatted_phone_number": "+1 512 555 0200",
            }
        ]
    }
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    connector = GooglePlacesConnector(api_key="test_key")
    records = connector.search_leads(query="Dentist", location="Austin, TX", limit=10)

    assert len(records) == 1
    assert records[0].business_name == "Austin Dental Care"
    assert records[0].source_id == "g_001"


def test_google_places_health_check_missing_key():
    connector = GooglePlacesConnector(api_key=None)
    assert connector.health_check() is False
