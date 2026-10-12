"""
Unit Tests — Email Enrichment Deep Scrape Fix (Four Changes)
=============================================================

Tests all four code changes made in tasks 3.1–3.4:

  Change 1 — stage_2_enrich_and_verify gate removal
    Email crawling runs unconditionally (email_crawl_enabled=True) even when
    job_state["enrichments"] is falsy.  VerificationAndEvidenceEngine is still
    gated on enrichment_enabled.

  Change 2 — _discover_internal_links fallback + max_pages increase
    When no priority-keyword pages exist, a generic-link fallback returns any
    same-domain internal links.  Default max_pages raised from 5 → 10.

  Change 3 — scrape_facebook_about method
    ProductionWebsiteEnricher.scrape_facebook_about(url) exists, normalises
    the URL to the /about path, extracts emails, and returns [] on errors.

  Change 4 — POST /scrape-jobs/{job_id}/re-enrich-emails endpoint
    Returns HTTP 400 for non-UUID job IDs; HTTP 200 with zero counts for
    unknown jobs; correctly updates/skips leads based on email validity.
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helper — minimal orchestrator stub (mirrors test_bug_exploration.py)
# ---------------------------------------------------------------------------

def _build_minimal_orchestrator(job_state_overrides: dict | None = None) -> object:
    """
    Returns a minimal stub that exposes only the attributes accessed by
    stage_2_enrich_and_verify, allowing the real method to be called without a DB.
    """
    from backend.app.orchestration.discovery_orchestrator import (
        DiscoveryOrchestrator,
        OrchestratorMetrics,
    )

    job_id = uuid.uuid4()
    base_job_state: dict = {
        "id": job_id,
        "workspace_id": uuid.uuid4(),
        "niche": "dental",
        "target_lead_count": 1,
        "country": "Canada",
        "region": "Ontario",
        "state": "Ontario",
        "enrichments": [],          # falsy by default — tests Change 1
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

    stub = object.__new__(DiscoveryOrchestrator)
    stub.job_state = base_job_state
    stub.metrics = OrchestratorMetrics(requested=1)
    stub.enricher = MagicMock()
    stub.discovery_engine = MagicMock()
    stub.resolver = MagicMock()
    stub._is_job_cancelled = lambda: False
    return stub


def _make_mock_enr_res(email: str = "owner@testbiz.com") -> MagicMock:
    """Build a mock EnrichedWebsiteResult with a single crawled email."""
    mock = MagicMock()
    mock.contacts.emails = [{"email": email, "source_page": "https://testbiz.com"}]
    mock.contacts.phones = []
    mock.contacts.whatsapp_links = []
    mock.social_profiles = {}
    mock.seo.title = "Test Biz"
    mock.seo.h1_tags = []
    mock.business_info.business_name = "Test Biz"
    return mock


# ===========================================================================
# Change 1 — stage_2_enrich_and_verify gate removal
# ===========================================================================

class TestChange1GateRemoval:
    """Email crawling runs unconditionally regardless of enrichment_enabled flag."""

    def test_email_crawl_runs_when_enrichment_disabled(self):
        """
        CHANGE 1 — email_crawl_enabled=True even when job_state["enrichments"] is [].

        mock enrich_website to return a result with emails; confirm enr_res is not
        None and effective_email is the crawled address (not the phone in the input).
        """
        from backend.app.sources.base import NormalizedLeadRecord

        orchestrator = _build_minimal_orchestrator({"enrichments": []})

        CRAWLED_EMAIL = "owner@testbiz.com"
        orchestrator.enricher.enrich_website.return_value = _make_mock_enr_res(CRAWLED_EMAIL)

        candidate = NormalizedLeadRecord(
            source="google_maps",
            source_id="node/change1_gate_test",
            business_name="Test Biz",
            website="https://testbiz.com",
            phone="+1 905 334 0732",
            email="(905) 334-0732",   # phone number in email column
            address="1 Test St, Toronto, ON",
            city="Toronto",
            state="Ontario",
            country="Canada",
        )

        with patch("backend.app.orchestration.discovery_orchestrator.publish_job_progress"):
            results = orchestrator.stage_2_enrich_and_verify([candidate])

        assert len(results) == 1
        result = results[0]

        # enrich_website MUST have been called — even with enrichments=[]
        orchestrator.enricher.enrich_website.assert_called_once()

        # enr_res must be the crawled result
        assert result["enr_res"] is not None, (
            "enr_res should not be None — email crawl must run with enrichments=[]"
        )

        # effective_email must be the crawled email, not the phone number
        assert result["effective_email"] == CRAWLED_EMAIL, (
            f"Expected crawled email {CRAWLED_EMAIL!r}, got {result['effective_email']!r}. "
            "Email crawl gate was not removed correctly."
        )

    def test_no_email_crawl_without_website(self):
        """
        CHANGE 1 — when rec.website is None, enrich_website is never called.

        The email_crawl_enabled flag is True but has_website is False, so the
        Step 2b block is skipped entirely.
        """
        from backend.app.sources.base import NormalizedLeadRecord

        orchestrator = _build_minimal_orchestrator({"enrichments": []})

        candidate = NormalizedLeadRecord(
            source="google_maps",
            source_id="node/change1_nosite_test",
            business_name="No Website Biz",
            website=None,           # no website — crawl must be skipped
            phone="+1 416 555 0001",
            email="info@nowebsite.ca",
            address="2 Oak Ave, Toronto, ON",
            city="Toronto",
            state="Ontario",
            country="Canada",
        )

        with patch("backend.app.orchestration.discovery_orchestrator.publish_job_progress"):
            results = orchestrator.stage_2_enrich_and_verify([candidate])

        assert len(results) == 1

        # enrich_website must NOT have been called
        orchestrator.enricher.enrich_website.assert_not_called()

        # enr_res must be None
        assert results[0]["enr_res"] is None, (
            "enr_res should be None when rec.website is None."
        )

    def test_verification_still_gated_on_enrichment_enabled(self):
        """
        CHANGE 1 — VerificationAndEvidenceEngine.verify_candidate is NOT called
        when enrichments=[] (enrichment_enabled=False).

        Email crawling runs, but the verification engine remains gated.
        """
        from backend.app.sources.base import NormalizedLeadRecord
        from backend.app.verification.engine import OverallVerificationResult

        orchestrator = _build_minimal_orchestrator({"enrichments": []})
        orchestrator.enricher.enrich_website.return_value = _make_mock_enr_res()

        candidate = NormalizedLeadRecord(
            source="google_maps",
            source_id="node/change1_verify_gate",
            business_name="Verify Gate Biz",
            website="https://verifygatedtest.com",
            phone="+1 416 555 0002",
            email="test@verifygatedtest.com",
            address="3 Pine St, Toronto, ON",
            city="Toronto",
            state="Ontario",
            country="Canada",
        )

        with patch(
            "backend.app.orchestration.discovery_orchestrator.VerificationAndEvidenceEngine"
        ) as mock_vae, patch(
            "backend.app.orchestration.discovery_orchestrator.publish_job_progress"
        ):
            results = orchestrator.stage_2_enrich_and_verify([candidate])

        assert len(results) == 1

        # verify_candidate must NOT have been called
        mock_vae.verify_candidate.assert_not_called()

        # v_res must be the baseline passthrough result
        v_res = results[0]["v_res"]
        assert isinstance(v_res, OverallVerificationResult), (
            f"Expected OverallVerificationResult, got {type(v_res)}"
        )
        assert v_res.decision == "ACCEPT", (
            f"Baseline v_res.decision should be 'ACCEPT', got {v_res.decision!r}"
        )
        assert v_res.composite_confidence == 0.5, (
            f"Baseline composite_confidence should be 0.5, got {v_res.composite_confidence}"
        )


# ===========================================================================
# Change 2 — _discover_internal_links fallback + max_pages
# ===========================================================================

class TestChange2DiscoverLinksAndMaxPages:
    """Fallback generic links and raised max_pages default."""

    def test_fallback_returns_generic_links_when_no_keyword_pages(self):
        """
        CHANGE 2 — when no priority-keyword paths exist in the HTML, the fallback
        block returns any same-domain internal links.
        """
        from backend.app.enrichment.website_enricher import ProductionWebsiteEnricher

        enricher = ProductionWebsiteEnricher(max_pages=10)

        html_no_keywords = """
        <!DOCTYPE html>
        <html><body>
          <a href="/our-story">Our Story</a>
          <a href="/pricing">Pricing</a>
          <a href="/blog">Blog</a>
        </body></html>
        """

        links = enricher._discover_internal_links(
            base_url="https://fallback-test.com",
            html=html_no_keywords,
        )

        assert links, (
            "_discover_internal_links returned [] for a site with only non-keyword links. "
            "The generic-link fallback is not working."
        )

        # All returned links must be on the same domain
        for link in links:
            assert "fallback-test.com" in link, (
                f"Fallback returned an external link: {link!r}"
            )

    def test_keyword_pages_precede_generic_fallback_links(self):
        """
        CHANGE 2 — when both a keyword page (/contact) and a non-keyword page
        (/our-story) exist in HTML, /contact must appear before /our-story.
        """
        from backend.app.enrichment.website_enricher import ProductionWebsiteEnricher

        enricher = ProductionWebsiteEnricher(max_pages=10)

        html_mixed = """
        <!DOCTYPE html>
        <html><body>
          <a href="/our-story">Our Story</a>
          <a href="/pricing">Pricing</a>
          <a href="/contact">Contact</a>
          <a href="/blog">Blog</a>
        </body></html>
        """

        links = enricher._discover_internal_links(
            base_url="https://keyword-order-test.com",
            html=html_mixed,
        )

        contact_links = [l for l in links if "contact" in l]
        ourstory_links = [l for l in links if "our-story" in l]

        assert contact_links, (
            "/contact is a priority keyword — it must always be returned."
        )

        if ourstory_links:
            contact_idx = links.index(contact_links[0])
            ourstory_idx = links.index(ourstory_links[0])
            assert contact_idx < ourstory_idx, (
                f"/contact (index {contact_idx}) must appear before /our-story "
                f"(index {ourstory_idx}). Keyword prioritisation is broken."
            )

    def test_max_pages_default_is_10(self):
        """
        CHANGE 2 — ProductionWebsiteEnricher() instantiated without arguments
        must have max_pages == 10 (raised from the original 5).
        """
        from backend.app.enrichment.website_enricher import ProductionWebsiteEnricher

        enricher = ProductionWebsiteEnricher()

        assert enricher.max_pages == 10, (
            f"Default max_pages should be 10, got {enricher.max_pages}. "
            "The shallow-crawl fix requires raising the default from 5 to 10."
        )

    def test_fallback_excludes_external_and_anchor_links(self):
        """
        CHANGE 2 — anchor (#), javascript:, and cross-domain links must never
        appear in fallback results.
        """
        from backend.app.enrichment.website_enricher import ProductionWebsiteEnricher

        enricher = ProductionWebsiteEnricher(max_pages=10)

        html_with_junk = """
        <!DOCTYPE html>
        <html><body>
          <a href="#section-1">Jump to section</a>
          <a href="javascript:void(0)">Click me</a>
          <a href="https://otherdomain.com/page">External</a>
          <a href="/our-story">Our Story</a>
        </body></html>
        """

        links = enricher._discover_internal_links(
            base_url="https://clean-test.com",
            html=html_with_junk,
        )

        for link in links:
            assert not link.startswith("#"), f"Anchor link leaked into results: {link!r}"
            assert "javascript:" not in link, f"javascript: link leaked into results: {link!r}"
            assert "otherdomain.com" not in link, f"External domain link leaked into results: {link!r}"


# ===========================================================================
# Change 3 — scrape_facebook_about method
# ===========================================================================

class TestChange3ScrapesFacebookAbout:
    """scrape_facebook_about extracts emails from the Facebook /about page."""

    def test_scrape_facebook_about_extracts_email(self):
        """
        CHANGE 3 — when _fetch_page returns HTML containing an email address,
        scrape_facebook_about must return a list containing that email.

        Note: example.com is in the telemetry-ignore list inside
        _extract_contacts_from_html, so we use a realistic fictional domain.
        """
        from backend.app.enrichment.website_enricher import PageFetchResult, ProductionWebsiteEnricher

        enricher = ProductionWebsiteEnricher()

        with patch.object(
            enricher,
            "_fetch_page",
            return_value=PageFetchResult(
                url="https://www.facebook.com/sunrisedental/about",
                status_code=200,
                html="<html><body><p>Contact: owner@sunrisedental.ca for bookings.</p></body></html>",
                response_time_ms=40.0,
                content_type="text/html",
            ),
        ):
            result = enricher.scrape_facebook_about("https://www.facebook.com/sunrisedental")

        assert isinstance(result, list), (
            f"scrape_facebook_about must return a list, got {type(result)}"
        )
        emails_found = [entry.get("email") for entry in result]
        assert "owner@sunrisedental.ca" in emails_found, (
            f"Expected 'owner@sunrisedental.ca' in extracted emails, got {emails_found!r}"
        )

    def test_scrape_facebook_about_normalises_url_to_about_path(self):
        """
        CHANGE 3 — the URL passed to _fetch_page must end with '/about', even when
        the input URL has a trailing slash or no path suffix.
        """
        from backend.app.enrichment.website_enricher import PageFetchResult, ProductionWebsiteEnricher

        enricher = ProductionWebsiteEnricher()
        captured_urls: list[str] = []

        def _capture_url(url: str) -> PageFetchResult:
            captured_urls.append(url)
            return PageFetchResult(
                url=url,
                status_code=200,
                html="<html><body>No email here.</body></html>",
                response_time_ms=20.0,
                content_type="text/html",
            )

        with patch.object(enricher, "_fetch_page", side_effect=_capture_url):
            enricher.scrape_facebook_about("https://www.facebook.com/sunrisedental/")

        assert captured_urls, "_fetch_page was never called"
        assert captured_urls[0].endswith("/about"), (
            f"URL passed to _fetch_page should end with '/about', got {captured_urls[0]!r}"
        )

    def test_scrape_facebook_about_returns_empty_on_fetch_error(self):
        """
        CHANGE 3 — when _fetch_page raises an Exception, scrape_facebook_about
        must return [] without propagating the exception.
        """
        from backend.app.enrichment.website_enricher import ProductionWebsiteEnricher

        enricher = ProductionWebsiteEnricher()

        with patch.object(
            enricher,
            "_fetch_page",
            side_effect=Exception("Connection refused"),
        ):
            # Must not raise
            result = enricher.scrape_facebook_about("https://www.facebook.com/failbiz")

        assert result == [], (
            f"Expected [] on fetch error, got {result!r}"
        )

    def test_scrape_facebook_about_returns_empty_on_empty_html(self):
        """
        CHANGE 3 — when _fetch_page returns a page with html="" (empty body),
        scrape_facebook_about must return [].
        """
        from backend.app.enrichment.website_enricher import PageFetchResult, ProductionWebsiteEnricher

        enricher = ProductionWebsiteEnricher()

        with patch.object(
            enricher,
            "_fetch_page",
            return_value=PageFetchResult(
                url="https://www.facebook.com/emptybiz/about",
                status_code=200,
                html="",            # empty body
                response_time_ms=15.0,
                content_type="text/html",
            ),
        ):
            result = enricher.scrape_facebook_about("https://www.facebook.com/emptybiz")

        assert result == [], (
            f"Expected [] for empty HTML, got {result!r}"
        )


# ===========================================================================
# Change 4 — POST /scrape-jobs/{job_id}/re-enrich-emails endpoint
# ===========================================================================

class TestChange4ReEnrichEmailsEndpoint:
    """
    Tests for the re-enrichment endpoint.

    Tests 13-15 mock the database layer so no real DB is required.
    The endpoint is at POST /api/v1/scrape-jobs/{job_id}/re-enrich-emails.
    """

    # ------------------------------------------------------------------
    # Test 12 — HTTP 400 for invalid job_id
    # ------------------------------------------------------------------

    def test_re_enrich_returns_400_for_invalid_job_id(self):
        """
        CHANGE 4 — a non-UUID job_id must return HTTP 400.
        """
        from backend.app.main import app
        from fastapi.testclient import TestClient

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post("/api/v1/scrape-jobs/not-a-uuid/re-enrich-emails")

        assert response.status_code == 400, (
            f"Expected HTTP 400 for non-UUID job_id, got {response.status_code}"
        )

    # ------------------------------------------------------------------
    # Test 13 — unknown job returns HTTP 200 with zero counts
    # ------------------------------------------------------------------

    def test_re_enrich_returns_200_with_zero_counts_for_unknown_job(self):
        """
        CHANGE 4 — when the job UUID is not found in the DB, the endpoint returns
        HTTP 200 with {"updated": 0, "skipped": 0, "failed": 0} (safe-to-call design).
        """
        from backend.app.main import app
        from fastapi.testclient import TestClient

        sentinel_job_id = str(uuid.uuid4())

        # Patch SessionLocal so no real DB hit occurs; scalar() returns None
        mock_db = MagicMock()
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_db.scalar.return_value = None   # job not found

        with patch("backend.app.api_services.SessionLocal", return_value=mock_db):
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.post(f"/api/v1/scrape-jobs/{sentinel_job_id}/re-enrich-emails")

        assert response.status_code == 200, (
            f"Expected HTTP 200 for unknown job, got {response.status_code}"
        )
        body = response.json()
        assert body.get("updated") == 0
        assert body.get("skipped") == 0
        assert body.get("failed") == 0

    # ------------------------------------------------------------------
    # Test 14 — leads with valid emails are skipped
    # ------------------------------------------------------------------

    def test_re_enrich_skips_leads_with_valid_emails(self):
        """
        CHANGE 4 — a lead with email="info@abc.com" (a valid, non-phone email)
        must be skipped. updated=0, skipped=1.
        """
        from backend.app.main import app
        from fastapi.testclient import TestClient

        job_id = str(uuid.uuid4())

        # Build a stub lead with a valid email
        stub_lead = MagicMock()
        stub_lead.email = "info@abc.com"
        stub_lead.website = "https://abc.com"
        stub_lead.id = uuid.uuid4()

        # Stub RawLeadSheet (found) and its leads
        stub_sheet = MagicMock()

        # We need two separate SessionLocal contexts:
        #  1st context: looks up sheet, queries leads
        #  2nd context (per-lead update): not reached since lead is skipped
        mock_db = MagicMock()
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_db.scalar.return_value = stub_sheet

        mock_scalars_result = MagicMock()
        mock_scalars_result.all.return_value = [stub_lead]
        mock_db.scalars.return_value = mock_scalars_result

        with patch("backend.app.api_services.SessionLocal", return_value=mock_db):
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.post(f"/api/v1/scrape-jobs/{job_id}/re-enrich-emails")

        assert response.status_code == 200
        body = response.json()
        assert body.get("updated") == 0, f"Expected updated=0, got {body.get('updated')}"
        assert body.get("skipped") == 1, f"Expected skipped=1, got {body.get('skipped')}"

    # ------------------------------------------------------------------
    # Test 15 — idempotency: second call skips already-valid email
    # ------------------------------------------------------------------

    def test_re_enrich_is_idempotent(self):
        """
        CHANGE 4 — calling the endpoint twice for the same lead:
          - First call: lead.email is None → updated=1
          - Second call: lead.email is now a valid address → skipped=1, updated=0
        """
        from backend.app.main import app
        from fastapi.testclient import TestClient

        job_id = str(uuid.uuid4())
        stub_sheet = MagicMock()

        # --- First call: lead email is None → needs enrichment ---
        stub_lead_first = MagicMock()
        stub_lead_first.email = None
        stub_lead_first.website = "https://freshbiz.com"
        stub_lead_first.id = uuid.uuid4()

        mock_db_first = MagicMock()
        mock_db_first.__enter__ = MagicMock(return_value=mock_db_first)
        mock_db_first.__exit__ = MagicMock(return_value=False)
        mock_db_first.scalar.return_value = stub_sheet
        mock_scalars_first = MagicMock()
        mock_scalars_first.all.return_value = [stub_lead_first]
        mock_db_first.scalars.return_value = mock_scalars_first

        # Mock the per-lead update session and the db2.get() call
        stub_updated_lead = MagicMock()
        stub_updated_lead.email = None
        mock_db2 = MagicMock()
        mock_db2.__enter__ = MagicMock(return_value=mock_db2)
        mock_db2.__exit__ = MagicMock(return_value=False)
        mock_db2.get.return_value = stub_updated_lead

        # Mock enrich_website to return a found email
        mock_enr_res = MagicMock()
        mock_enr_res.contacts.emails = [{"email": "owner@freshbiz.com"}]

        call_count = {"n": 0}

        def _session_factory_first():
            call_count["n"] += 1
            if call_count["n"] == 1:
                return mock_db_first
            return mock_db2

        with patch("backend.app.api_services.SessionLocal", side_effect=_session_factory_first):
            with patch(
                "backend.app.enrichment.website_enricher.ProductionWebsiteEnricher.enrich_website",
                return_value=mock_enr_res,
            ):
                with TestClient(app, raise_server_exceptions=False) as client:
                    resp1 = client.post(f"/api/v1/scrape-jobs/{job_id}/re-enrich-emails")

        assert resp1.status_code == 200
        body1 = resp1.json()
        assert body1.get("updated") == 1, (
            f"First call should have updated=1, got {body1.get('updated')}"
        )

        # --- Second call: lead now has a valid email → should be skipped ---
        stub_lead_second = MagicMock()
        stub_lead_second.email = "owner@freshbiz.com"  # valid after first call
        stub_lead_second.website = "https://freshbiz.com"
        stub_lead_second.id = stub_lead_first.id

        mock_db_second = MagicMock()
        mock_db_second.__enter__ = MagicMock(return_value=mock_db_second)
        mock_db_second.__exit__ = MagicMock(return_value=False)
        mock_db_second.scalar.return_value = stub_sheet
        mock_scalars_second = MagicMock()
        mock_scalars_second.all.return_value = [stub_lead_second]
        mock_db_second.scalars.return_value = mock_scalars_second

        with patch("backend.app.api_services.SessionLocal", return_value=mock_db_second):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp2 = client.post(f"/api/v1/scrape-jobs/{job_id}/re-enrich-emails")

        assert resp2.status_code == 200
        body2 = resp2.json()
        assert body2.get("updated") == 0, (
            f"Second call (valid email) should have updated=0, got {body2.get('updated')}"
        )
        assert body2.get("skipped") == 1, (
            f"Second call should have skipped=1, got {body2.get('skipped')}"
        )
