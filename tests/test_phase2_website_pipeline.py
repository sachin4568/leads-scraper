import pytest
import uuid
import httpx
from unittest.mock import patch, MagicMock

from backend.app.enrichment.website_pipeline import (
    fetch_and_evaluate_website,
    normalize_url,
    is_platform_domain
)

def test_normalize_url():
    assert normalize_url("example.com") == "https://example.com"
    assert normalize_url("http://example.com") == "http://example.com"

def test_platform_domain():
    assert is_platform_domain("https://facebook.com/mybusiness") == True
    assert is_platform_domain("https://www.myrealbusiness.com") == False

# A. HTTP 200 + business name only -> NOT VERIFIED (UNVERIFIED)
@patch("backend.app.enrichment.website_pipeline.httpx.Client")
def test_business_name_only(mock_client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.url = httpx.URL("https://randomdomain.com")
    mock_resp.text = "<html><body>Welcome to My Business Inc.</body></html>"
    mock_client.return_value.__enter__.return_value.get.return_value = mock_resp

    cls, conf, details = fetch_and_evaluate_website("randomdomain.com", "My Business Inc", "", "")
    assert cls == "UNVERIFIED"

# B. HTTP 200 + unrelated business -> NOT_BUSINESS_WEBSITE or UNVERIFIED
@patch("backend.app.enrichment.website_pipeline.httpx.Client")
def test_unrelated_business(mock_client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.url = httpx.URL("https://unrelated.com")
    mock_resp.text = "<html><body>Nothing matches here.</body></html>"
    mock_client.return_value.__enter__.return_value.get.return_value = mock_resp

    cls, conf, details = fetch_and_evaluate_website("unrelated.com", "My Business Inc", "555-1234", "")
    assert cls == "NOT_BUSINESS_WEBSITE"

# D. Matching phone + matching business identity -> strong confidence
@patch("backend.app.enrichment.website_pipeline.httpx.Client")
def test_matching_phone_and_name(mock_client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.url = httpx.URL("https://mybusiness.com")
    mock_resp.text = "<html><body>My Business Inc. Call 555-1234.</body></html>"
    mock_client.return_value.__enter__.return_value.get.return_value = mock_resp

    cls, conf, details = fetch_and_evaluate_website("mybusiness.com", "My Business Inc", "555-1234", "")
    assert cls == "VERIFIED_BUSINESS_WEBSITE"
    assert conf >= 80

# E. Matching address + matching business identity -> strong confidence
@patch("backend.app.enrichment.website_pipeline.httpx.Client")
def test_matching_address(mock_client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.url = httpx.URL("https://mybusiness.com")
    mock_resp.text = "<html><body>My Business Inc. Location: 123 Main Street Suite 100.</body></html>"
    mock_client.return_value.__enter__.return_value.get.return_value = mock_resp

    cls, conf, details = fetch_and_evaluate_website("mybusiness.com", "My Business Inc", "", "123 Main Street Suite 100")
    assert cls == "VERIFIED_BUSINESS_WEBSITE"

# F. Matching name + phone + address -> VERIFIED
@patch("backend.app.enrichment.website_pipeline.httpx.Client")
def test_matching_all(mock_client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.url = httpx.URL("https://mybusiness.com")
    mock_resp.text = "<html><body>My Business Inc. 555-1234. 123 Main Street Suite 100. <script type='application/ld+json'>LocalBusiness</script></body></html>"
    mock_client.return_value.__enter__.return_value.get.return_value = mock_resp

    cls, conf, details = fetch_and_evaluate_website("mybusiness.com", "My Business Inc", "555-1234", "123 Main Street")
    assert cls == "VERIFIED_BUSINESS_WEBSITE"
    assert conf == 100  # Caps at 100

# G. Platform URL -> NOT_BUSINESS_WEBSITE
def test_platform_url():
    cls, conf, details = fetch_and_evaluate_website("facebook.com/mybiz", "My Business", "123", "")
    assert cls == "NOT_BUSINESS_WEBSITE"

# H. Redirect to unrelated business (Mocked by returning unrelated domain)
@patch("backend.app.enrichment.website_pipeline.httpx.Client")
def test_redirect_to_unrelated(mock_client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.url = httpx.URL("https://some-unrelated-domain.com")
    mock_resp.text = "<html><body>Something else</body></html>"
    mock_client.return_value.__enter__.return_value.get.return_value = mock_resp

    cls, conf, details = fetch_and_evaluate_website("initial-domain.com", "My Business", "123", "")
    assert cls == "NOT_BUSINESS_WEBSITE"

# I. Redirect to genuine matching business domain
@patch("backend.app.enrichment.website_pipeline.httpx.Client")
def test_redirect_to_genuine(mock_client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.url = httpx.URL("https://mybusiness.com")
    mock_resp.text = "<html><body>My Business Inc. 555-1234</body></html>"
    mock_client.return_value.__enter__.return_value.get.return_value = mock_resp

    cls, conf, details = fetch_and_evaluate_website("initial-domain.com", "My Business Inc", "555-1234", "")
    assert cls == "VERIFIED_BUSINESS_WEBSITE"
    assert details["final_url"] == "https://mybusiness.com"

@patch("backend.app.enrichment.website_pipeline.httpx.Client")
def test_broken_website(mock_client):
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.url = httpx.URL("https://broken.com")
    mock_client.return_value.__enter__.return_value.get.return_value = mock_resp
    cls, conf, details = fetch_and_evaluate_website("broken.com", "My Biz", "", "")
    assert cls == "BROKEN"

@patch("backend.app.enrichment.website_pipeline.httpx.Client")
def test_network_timeout(mock_client):
    mock_client.return_value.__enter__.return_value.get.side_effect = httpx.ConnectTimeout("Timeout")
    cls, conf, details = fetch_and_evaluate_website("timeout.com", "My Biz", "", "")
    assert cls == "UNREACHABLE"
    assert details["reason"] == "Connection Timeout"
