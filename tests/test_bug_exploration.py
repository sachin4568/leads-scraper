"""
Bug Condition Exploration Tests — Email Enrichment Deep Scrape Fix
==================================================================

These tests are EXPECTED TO FAIL on unfixed code.
Failure == the bug is confirmed. Do NOT fix the tests when they fail.

Four bug paths are covered:

  Path A — Gate bypass:
    When job_state["enrichments"] is falsy (e.g. []), stage_2_enrich_and_verify
    short-circuits and returns rec.email verbatim — even when it is a phone number.
    Expected counterexample: effective_email == "(905) 334-0732"

  Path B — Shallow crawl:
    ProductionWebsiteEnricher(max_pages=5)._discover_internal_links returns [] when
    no priority-keyword paths exist (e.g. only /our-story). The crawler never visits
    /our-story, so the email on that page is missed.
    Expected counterexample: enr_res.contacts.emails == []

  Path C — No Facebook About scraper:
    ProductionWebsiteEnricher has no scrape_facebook_about method.
    Expected counterexample: AttributeError: 'ProductionWebsiteEnricher' object
    has no attribute 'scrape_facebook_about'

  Path D — No re-enrichment endpoint:
    POST /scrape-jobs/{job_id}/re-enrich-emails does not exist.
    Expected counterexample: HTTP 404 or 405

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6**
"""
from __future__ import annotations

import re
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PHONE_PATTERN = re.compile(r"^\(?\d{3}\)?[\s\-]\d{3}[\s\-]\d{4}$")

KNOWN_PHONE_IN_EMAIL_FIELD = "(905) 334-0732"

HOMEPAGE_HTML_NO_KEYWORD_LINKS = """
<!DOCTYPE html>
<html>
<head><title>Sunrise Dental</title></head>
<body>
  <h1>Sunrise Dental</h1>
  <p>We care about your smile.</p>
  <a href="/our-story">Our Story</a>
  <a href="/pricing">Pricing</a>
  <a href="/blog">Blog</a>
</body>
</html>
"""

OUR_STORY_HTML_WITH_EMAIL = """
<!DOCTYPE html>
<html>
<body>
  <h1>About Us</h1>
  <p>Reach us at owner@sunrisedental.ca for appointments.</p>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Helper — build minimal orchestrator stub for Path A
# ---------------------------------------------------------------------------

def _build_minimal_orchestrator(job_state_overrides: dict | None = None) -> object:
    """
    Returns a minimal stub that exposes only the attributes accessed by
    stage_2_enrich_and_verify before and inside the early-return block,
    so we can call the real method without a database job.
    """
    from backend.app.orchestration.discovery_orchestrator import (
        DiscoveryOrchestrator,
        OrchestratorMetrics,
    )
    from backend.app.verification import OverallVerificationResult

    job_id = uuid.uuid4()
    base_job_state: dict = {
        "id": job_id,
        "workspace_id": uuid.uuid4(),
        "niche": "dental",
        "target_lead_count": 1,
        "country": "Canada",
        "region": "Ontario",
        "state": "Ontario",
        "enrichments": [],        # <-- the bug condition: falsy enrichments
        "sources": ["osm_overpass"],
        "service": None,
        "leads_scraped": 0,
        "progress_percent": 0.0,
        "status": "RUNNING",
        "discovered_count": 0,
        "valid_count": 0,
        "error_message": None,
        "current_source": "",
        "current_query": "",
    }
    if job_state_overrides:
        base_job_state.update(job_state_overrides)

    # Build a stub — avoid calling DiscoveryOrchestrator.__init__ (needs DB)
    stub = object.__new__(DiscoveryOrchestrator)
    stub.job_state = base_job_state
    stub.metrics = OrchestratorMetrics(requested=1)
    stub.enricher = MagicMock()
    stub.discovery_engine = MagicMock()
    stub.resolver = MagicMock()
    stub._is_job_cancelled = lambda: False
    return stub


# ===========================================================================
# Path A — Gate bypass test
# ===========================================================================

def test_path_a_gate_bypass_effective_email_is_not_phone_number():
    """
    BUG PATH A — EXPECTED TO FAIL on unfixed code.

    When job_state["enrichments"] is [] (falsy), stage_2_enrich_and_verify returns
    rec.email verbatim via the early-return block (lines 832–849 of
    discovery_orchestrator.py). If Google Maps placed a phone number in the email
    column, the phone number propagates unchanged to effective_email.

    Correct behaviour (post-fix): the system MUST still call enrich_website to
    attempt real email discovery, and MUST NOT store a phone number in effective_email.

    Counterexample on unfixed code:
        effective_email == "(905) 334-0732"  (phone number in email field)
    """
    from backend.app.sources.base import NormalizedLeadRecord

    orchestrator = _build_minimal_orchestrator({"enrichments": []})

    candidate = NormalizedLeadRecord(
        source="google_maps",
        source_id="node/test_gate_bypass_001",
        business_name="Joe's Plumbing",
        website="https://example.com",
        phone="+1 905 334 0732",
        email=KNOWN_PHONE_IN_EMAIL_FIELD,  # phone number stored in email column
        address="123 Main St, Toronto, ON",
        city="Toronto",
        state="Ontario",
        country="Canada",
    )

    with patch("backend.app.orchestration.discovery_orchestrator.publish_job_progress"):
        results = orchestrator.stage_2_enrich_and_verify([candidate])

    assert len(results) == 1
    effective_email = results[0]["effective_email"]

    # ASSERTION: effective_email must NOT be a phone number.
    # On UNFIXED code this assertion FAILS because effective_email == "(905) 334-0732".
    assert effective_email is None or not PHONE_PATTERN.match(str(effective_email).strip()), (
        f"BUG PATH A CONFIRMED: effective_email is a phone number: {effective_email!r}. "
        "The early-return block returned rec.email verbatim without email crawling."
    )


# ===========================================================================
# Path B — Shallow crawl test
# ===========================================================================

def test_path_b_shallow_crawl_email_discovered_on_non_keyword_page():
    """
    BUG PATH B — EXPECTED TO FAIL on unfixed code.

    When ProductionWebsiteEnricher(max_pages=5) processes a site whose homepage
    links contain only non-keyword paths (/our-story, /pricing, /blog),
    _discover_internal_links returns []. The crawler never visits /our-story,
    so owner@sunrisedental.ca on that page is never found.

    Correct behaviour (post-fix): a generic-link fallback crawls /our-story and
    discovers the email. max_pages should also increase to 10.

    Counterexample on unfixed code:
        enr_res.contacts.emails == []   (email on /our-story not discovered)
    """
    from backend.app.enrichment.website_enricher import PageFetchResult, ProductionWebsiteEnricher

    enricher = ProductionWebsiteEnricher(max_pages=5)

    def _mock_fetch(url: str) -> PageFetchResult:
        """Return homepage with only /our-story link, then our-story with email."""
        if "our-story" in url:
            return PageFetchResult(
                url=url,
                status_code=200,
                html=OUR_STORY_HTML_WITH_EMAIL,
                response_time_ms=12.0,
                content_type="text/html",
            )
        # Homepage — returns only non-keyword internal links
        return PageFetchResult(
            url="https://sunrisedental.ca",
            status_code=200,
            html=HOMEPAGE_HTML_NO_KEYWORD_LINKS,
            response_time_ms=10.0,
            content_type="text/html",
        )

    with patch.object(enricher, "_fetch_page", side_effect=_mock_fetch):
        enr_res = enricher.enrich_website(
            target_url="https://sunrisedental.ca",
            provider_email=None,
        )

    # ASSERTION: the email on /our-story must be discovered.
    # On UNFIXED code this FAILS because _discover_internal_links returns [] for
    # non-keyword paths, so /our-story is never fetched.
    assert enr_res.contacts.emails, (
        "BUG PATH B CONFIRMED: enr_res.contacts.emails is empty. "
        "_discover_internal_links returned no links because /our-story has no "
        "priority keyword in its path. Email on /our-story was never discovered."
    )


# ===========================================================================
# Path C — Facebook About test
# ===========================================================================

def test_path_c_facebook_about_method_exists_and_returns_list():
    """
    BUG PATH C — EXPECTED TO FAIL on unfixed code.

    ProductionWebsiteEnricher has no scrape_facebook_about method. Leads with a
    Facebook Business page URL receive no fallback email extraction.

    Correct behaviour (post-fix): scrape_facebook_about(fb_url) returns a list of
    email dicts (may be empty on network errors, but must not raise AttributeError).

    Counterexample on unfixed code:
        AttributeError: 'ProductionWebsiteEnricher' object has no attribute
        'scrape_facebook_about'
    """
    from backend.app.enrichment.website_enricher import PageFetchResult, ProductionWebsiteEnricher

    enricher = ProductionWebsiteEnricher()

    # ASSERTION: method must exist without raising AttributeError.
    # On UNFIXED code this FAILS with AttributeError.
    assert hasattr(enricher, "scrape_facebook_about"), (
        "BUG PATH C CONFIRMED: ProductionWebsiteEnricher has no scrape_facebook_about "
        "attribute. Leads with Facebook Business URLs cannot have emails extracted from "
        "the Facebook About page."
    )

    # If the method exists, it should return a list (never raise).
    with patch.object(
        enricher,
        "_fetch_page",
        return_value=PageFetchResult(
            url="https://www.facebook.com/sunrisedental/about",
            status_code=200,
            html="<html><body>Contact: owner@sunrisedental.ca</body></html>",
            response_time_ms=50.0,
            content_type="text/html",
        ),
    ):
        result = enricher.scrape_facebook_about("https://facebook.com/sunrisedental")

    assert isinstance(result, list), (
        f"scrape_facebook_about must return a list, got {type(result)}"
    )


# ===========================================================================
# Path D — Re-enrichment endpoint test
# ===========================================================================

def test_path_d_re_enrich_emails_endpoint_returns_200():
    """
    BUG PATH D — EXPECTED TO FAIL on unfixed code.

    There is no POST /scrape-jobs/{job_id}/re-enrich-emails endpoint.
    Leads already scraped without enrichment have no automated path to get their
    email column re-populated.

    Correct behaviour (post-fix): POST /api/v1/scrape-jobs/{job_id}/re-enrich-emails
    returns HTTP 200 with a JSON body containing updated/skipped/failed counts.

    Counterexample on unfixed code:
        HTTP 404 (route not registered)  OR  HTTP 405 (method not allowed)
    """
    from backend.app.main import app

    sentinel_job_id = "00000000-0000-0000-0000-000000000001"
    url = f"/api/v1/scrape-jobs/{sentinel_job_id}/re-enrich-emails"

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(url)

    # ASSERTION: endpoint must exist and return HTTP 200.
    # On UNFIXED code this FAILS because the route is not registered (404).
    assert response.status_code == 200, (
        f"BUG PATH D CONFIRMED: POST {url} returned HTTP {response.status_code}. "
        "The re-enrichment endpoint does not exist yet. Leads with missing/phone "
        "emails cannot be retroactively re-enriched."
    )
