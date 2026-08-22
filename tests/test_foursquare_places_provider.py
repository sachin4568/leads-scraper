from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.app.sources.foursquare import FoursquareConnector


def test_foursquare_connector_initialization():
    connector = FoursquareConnector(api_key="fsq_test_key")
    assert connector.source_name == "foursquare"
    assert connector.api_key == "fsq_test_key"


def test_foursquare_record_normalization():
    connector = FoursquareConnector(api_key="fsq_test_key")
    raw_fsq = {
        "fsq_id": "4b058816f964a520a8af22e3",
        "name": "Nairobi Coffee House",
        "location": {
            "formatted_address": "Kenyatta Ave, Nairobi",
            "locality": "Nairobi",
            "country": "Kenya",
        },
        "tel": "+254 20 123456",
        "website": "https://www.nairoficoffee.co.ke",
        "categories": [{"name": "Coffee Shop"}],
    }

    record = connector.parse_foursquare_record(raw_fsq)
    assert record.source == "foursquare"
    assert record.source_id == "4b058816f964a520a8af22e3"
    assert record.business_name == "Nairobi Coffee House"
    assert record.city == "Nairobi"
    assert record.country == "Kenya"
    assert record.phone == "+254 20 123456"
    assert record.category == "Coffee Shop"


@patch("httpx.Client.get")
def test_foursquare_search_leads_success(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "results": [
            {
                "fsq_id": "fsq_001",
                "name": "Lagos Logistics Hub",
                "location": {"locality": "Lagos", "country": "Nigeria"},
            }
        ]
    }
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    connector = FoursquareConnector(api_key="fsq_test_key")
    records = connector.search_leads(query="Logistics", location="Lagos, Nigeria", limit=5)

    assert len(records) == 1
    assert records[0].business_name == "Lagos Logistics Hub"
    assert records[0].source_id == "fsq_001"


def test_foursquare_health_check_missing_key():
    connector = FoursquareConnector(api_key=None)
    assert connector.health_check() is False
