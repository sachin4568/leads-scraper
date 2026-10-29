from __future__ import annotations

import pytest

from backend.app.sources.data_axle import DataAxleConnector
from backend.app.sources.foursquare import FoursquareConnector
from backend.app.sources.google_search import GoogleSearchConnector
from backend.app.sources.linkedin import LinkedInConnector
from backend.app.sources.yelp import YelpConnector


@pytest.mark.parametrize(
    ("module_name", "connector", "result_key", "record"),
    [
        (
            "google_search",
            GoogleSearchConnector(api_key="test-key", cse_id="test-cse"),
            "items",
            {
                "title": "Acme Plumbing",
                "link": "https://acme-plumbing.example",
                "snippet": "Plumbing services",
                "displayLink": "acme-plumbing.example",
            },
        ),
        (
            "foursquare",
            FoursquareConnector(api_key="test-key"),
            "results",
            {"fsq_id": "fsq-1", "name": "Acme Plumbing", "location": {}},
        ),
        (
            "yelp",
            YelpConnector(api_key="test-key"),
            "businesses",
            {"id": "yelp-1", "name": "Acme Plumbing", "location": {}},
        ),
        (
            "data_axle",
            DataAxleConnector(api_key="test-key"),
            "documents",
            {"id": "da-1", "name": "Acme Plumbing"},
        ),
        (
            "linkedin",
            LinkedInConnector(access_token="test-token"),
            "elements",
            {"id": "li-1", "localizedName": "Acme Plumbing"},
        ),
    ],
)
def test_full_page_advances_and_short_page_exhausts(
    monkeypatch,
    module_name,
    connector,
    result_key,
    record,
):
    import importlib

    module = importlib.import_module(f"backend.app.sources.{module_name}")
    monkeypatch.setattr(module, "validate_outbound_url", lambda url: url)

    class Response:
        status_code = 200

        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    responses = [
        Response({result_key: [record]}),
        Response({result_key: []}),
    ]

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get(self, *_args, **_kwargs):
            return responses.pop(0)

    monkeypatch.setattr(module.httpx, "Client", lambda **_kwargs: Client())
    pagination_state = {}

    first_page = connector.search_leads(
        query="plumbing",
        location="London",
        limit=1,
        page=1,
        pagination_state=pagination_state,
    )
    assert len(first_page) == 1
    assert pagination_state["has_more"] is True

    second_page = connector.search_leads(
        query="plumbing",
        location="London",
        limit=1,
        page=2,
        pagination_state=pagination_state,
    )
    assert second_page == []
    assert pagination_state["has_more"] is False
