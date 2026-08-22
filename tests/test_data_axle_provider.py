from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.app.sources.data_axle import DataAxleConnector


def test_data_axle_connector_initialization():
    connector = DataAxleConnector(api_key="da_key_123")
    assert connector.source_name == "data_axle"
    assert connector.api_key == "da_key_123"


def test_data_axle_record_normalization():
    connector = DataAxleConnector(api_key="da_key_123")
    raw_da = {
        "id": "da_998877",
        "name": "London Financial Advisors",
        "street": "100 Bishopsgate",
        "city": "London",
        "country": "United Kingdom",
        "phone": "+44 20 7946 0912",
        "website": "https://www.londonfa.co.uk",
        "primary_sic_description": "Financial Planning Consultants",
    }

    record = connector.parse_data_axle_record(raw_da)
    assert record.source == "data_axle"
    assert record.source_id == "da_998877"
    assert record.business_name == "London Financial Advisors"
    assert record.city == "London"
    assert record.country == "United Kingdom"
    assert record.phone == "+44 20 7946 0912"
    assert record.category == "Financial Planning Consultants"


@patch("httpx.Client.get")
def test_data_axle_search_leads_success(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "documents": [
            {
                "id": "da_001",
                "name": "Johannesburg Solar",
                "city": "Johannesburg",
                "country": "South Africa",
            }
        ]
    }
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    connector = DataAxleConnector(api_key="da_key_123")
    records = connector.search_leads(query="Solar", location="Johannesburg", limit=5)

    assert len(records) == 1
    assert records[0].business_name == "Johannesburg Solar"
    assert records[0].source_id == "da_001"


def test_data_axle_health_check_missing_key():
    connector = DataAxleConnector(api_key=None)
    assert connector.health_check() is False
