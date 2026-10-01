import pytest
from unittest.mock import patch, MagicMock

from backend.app.enrichment.email_pipeline import (
    normalize_email,
    is_valid_email_syntax,
    classify_email,
    extract_emails_from_html,
    run_email_discovery
)

def test_normalize_email():
    assert normalize_email("INFO@COMPANY.COM") == "info@company.com"
    assert normalize_email("info [at] company.com") == "info@company.com"
    assert normalize_email("info(at)company.com") == "info@company.com"
    assert normalize_email("info @ company.com") == "info@company.com"
    assert normalize_email(" Contact us at info@company.com.") == "contact us at info@company.com"

def test_is_valid_email():
    assert is_valid_email_syntax("info@company.com") == True
    assert is_valid_email_syntax("info@company") == False
    assert is_valid_email_syntax("invalid email@company.com") == False

def test_classify_email():
    # Role based, match
    cls, dm = classify_email("info@company.com", "company.com")
    assert cls == "ROLE_BASED"
    assert dm == True

    # Role based, no match
    cls, dm = classify_email("info@other.com", "company.com")
    assert cls == "ROLE_BASED"
    assert dm == False

    # Generic provider
    cls, dm = classify_email("mybusiness@gmail.com", "company.com")
    assert cls == "GENERIC_PROVIDER"
    assert dm == False

    # Personal, match
    cls, dm = classify_email("john@company.com", "company.com")
    assert cls == "PERSONAL_BUSINESS"
    assert dm == True

def test_extract_emails_from_html():
    html = """
    <html>
        <body>
            <a href="mailto:info@company.com">Email Us</a>
            <p>You can also reach john@company.com or sales [at] company.com.</p>
            <script type="application/ld+json">
                {"@type": "Organization", "email": "support@company.com"}
            </script>
        </body>
    </html>
    """
    found = extract_emails_from_html(html, "https://company.com")
    emails = {e["email"]: e["source_type"] for e in found}
    
    assert "info@company.com" in emails
    assert emails["info@company.com"] == "mailto_link"
    assert "john@company.com" in emails
    assert emails["john@company.com"] == "visible_text"
    assert "sales@company.com" in emails
    assert emails["sales@company.com"] == "visible_text"
    assert "support@company.com" in emails
    assert emails["support@company.com"] == "json_ld"

@patch("backend.app.enrichment.email_pipeline.httpx.Client")
def test_run_email_discovery_success(mock_client):
    # Mock homepage
    mock_resp_home = MagicMock()
    mock_resp_home.status_code = 200
    mock_resp_home.url = "https://company.com"
    mock_resp_home.text = """
    <html>
        <body>
            <a href="/contact">Contact</a>
            <p>hello@company.com</p>
        </body>
    </html>
    """
    
    # Mock contact page
    mock_resp_contact = MagicMock()
    mock_resp_contact.status_code = 200
    mock_resp_contact.url = "https://company.com/contact"
    mock_resp_contact.text = "<html><body>info@company.com, CEO: john@company.com</body></html>"
    
    # Configure mock side_effect based on URL
    def get_side_effect(url, **kwargs):
        if url == "https://company.com": return mock_resp_home
        if url == "https://company.com/contact": return mock_resp_contact
        resp = MagicMock()
        resp.status_code = 404
        return resp
        
    mock_client.return_value.__enter__.return_value.get.side_effect = get_side_effect

    status, emails, _ = run_email_discovery("https://company.com", "company.com")
    
    assert status == "COMPLETED"
    em_list = [e["email"] for e in emails]
    assert "info@company.com" in em_list
    assert "hello@company.com" in em_list
    assert "john@company.com" in em_list
    
    # Verify ranking (Role based + domain match first)
    assert emails[0]["classification"] == "ROLE_BASED"
    assert emails[0]["domain_match"] == True

@patch("backend.app.enrichment.email_pipeline.httpx.Client")
def test_run_email_discovery_no_email(mock_client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.url = "https://company.com"
    mock_resp.text = "<html><body>No email here!</body></html>"
    mock_client.return_value.__enter__.return_value.get.return_value = mock_resp

    status, emails, _ = run_email_discovery("https://company.com", "company.com")
    assert status == "COMPLETED"
    assert len(emails) == 0

@patch("backend.app.enrichment.email_pipeline.httpx.Client")
def test_run_email_discovery_unreachable(mock_client):
    import httpx
    mock_client.return_value.__enter__.return_value.get.side_effect = httpx.RequestError("Failed")

    status, emails, _ = run_email_discovery("https://company.com", "company.com")
    assert status == "UNAVAILABLE"
    assert len(emails) == 0

