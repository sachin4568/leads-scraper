"""
Preservation Property Tests — Email Enrichment Deep Scrape Fix
==============================================================

These tests MUST PASS on UNFIXED code. They document the baseline correct
behaviors that the fix must leave unchanged (regression prevention).

Six unit tests + two property-based tests cover all preservation requirements
from bugfix.md sections 3.1–3.7 and design.md "Preservation Requirements".

  1. Cache preservation       — second call returns cached result, no new HTTP fetch
  2. Conflict recording       — provider_email vs crawled email populates conflicts dict
  3. Phone validation independence — phone REJECTED nullifies effective_phone only
  4. No-website skip          — enrich_website never called when rec.website is None
  5. Keyword pages prioritised — /contact before /our-story in _discover_internal_links
  6. Enrichment-off passthrough — VerificationAndEvidenceEngine NOT called when disabled

  PBT 7. enrichment_enabled=True never stores phone number in effective_email
  PBT 8. _discover_internal_links always returns keyword links before generic links

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7**
"""
from __future__ import annotations

import re
import uuid
from unittest.mock import MagicMock, call, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Constants shared across tests
# ---------------------------------------------------------------------------

PHONE_PATTERN = re.compile(r"^\(?\d{3}\)?[\s\-]\d{3}[\s\-]\d{4}$")

HOMEPAGE_HTML_WITH_CONTACT_AND_OURSTORY = """
<!DOCTYPE html>
<html>
<head><title>ABC Corp</title></head>
<body>
  <h1>ABC Corp</h1>
  <a href="/contact">Contact Us</a>
  <a href="/our-story">Our Story</a>
  <a href="/pricing">Pricing</a>
</body>
</html>
"""

CONTACT_PAGE_HTML_WITH_EMAIL = """
<!DOCTYPE html>
<html>
<body>
  <p>Reach us at info@abccorp.com or call our team.</p>
</body>
</html>
"""

OURSTORY_PAGE_HTML_WITH_EMAIL = """
<!DOCTYPE html>
<html>
<body>
  <p>Founded by owner@abccorp.com in 2005.</p>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Helper — build minimal orchestrator stub (same pattern as test_bug_exploration.py)
# ---------------------------------------------------------------------------

def _build_minimal_orchestrator(job_state_overrides: dict | None = None) -> object:
    """
    Returns a minimal stub that exposes only the attributes accessed by
    stage_2_enrich_and_verify, allowing us to call the real method without a DB.
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
        "enrichments": ["email"],   # enrichment_enabled=True by default
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


# ===========================================================================
# Test 1 — Cache preservation
# Req 3.6: global domain cache returns cached result without re-fetching
# ===========================================================================

class TestCachePreservation:
    """enrich_website must return the cached result on the second call for the same domain."""

    def test_second_call_returns_instance_cache_without_new_fetch(self):
        """
        PRESERVATION 1 — Cache Preservation (req 3.6)

        After calling enrich_website once, a second call for the same domain must
        be served from self._cache (instance cache) — _fetch_page must NOT be
        called a second time.

        Observing on unfixed code to confirm this already works correctly.
        """
        from backend.app.enrichment.website_enricher import PageFetchResult, ProductionWebsiteEnricher

        enricher = ProductionWebsiteEnricher(max_pages=5)
        fetch_call_count = 0

        def _mock_fetch(url: str) -> PageFetchResult:
            nonlocal fetch_call_count
            fetch_call_count += 1
            if "contact" in url:
                return PageFetchResult(
                    url=url,
                    status_code=200,
                    html=CONTACT_PAGE_HTML_WITH_EMAIL,
                    response_time_ms=15.0,
                    content_type="text/html",
                )
            return PageFetchResult(
                url="https://abccorp.com",
                status_code=200,
                html=HOMEPAGE_HTML_WITH_CONTACT_AND_OURSTORY,
                response_time_ms=10.0,
                content_type="text/html",
            )

        with patch.object(enricher, "_fetch_page", side_effect=_mock_fetch):
            result1 = enricher.enrich_website(target_url="https://abccorp.com")
            fetches_after_first_call = fetch_call_count

            result2 = enricher.enrich_website(target_url="https://abccorp.com")
            fetches_after_second_call = fetch_call_count

        # Second call must not have triggered any new HTTP fetches
        assert fetches_after_second_call == fetches_after_first_call, (
            f"PRESERVATION BROKEN: cache miss on second call — "
            f"{fetches_after_second_call - fetches_after_first_call} additional HTTP fetches made. "
            "The instance cache is not being respected."
        )

        # Both calls must return the same object
        assert result1 is result2, (
            "PRESERVATION BROKEN: second enrich_website call returned a different object. "
            "The cache should return the exact same EnrichedWebsiteResult instance."
        )

    def test_second_call_returns_global_cache_across_enricher_instances(self):
        """
        PRESERVATION 1b — Global Domain Cache (req 3.6)

        A second enricher *instance* for the same domain must also be served from
        _GLOBAL_DOMAIN_CACHE without making new HTTP fetches.
        """
        import backend.app.enrichment.website_enricher as enricher_module
        from backend.app.enrichment.website_enricher import (
            PageFetchResult,
            ProductionWebsiteEnricher,
            _GLOBAL_DOMAIN_CACHE,
        )

        # Clear global cache so this test is isolated
        _GLOBAL_DOMAIN_CACHE.clear()

        enricher_a = ProductionWebsiteEnricher(max_pages=5)
        fetch_count = 0

        def _mock_fetch(url: str) -> PageFetchResult:
            nonlocal fetch_count
            fetch_count += 1
            return PageFetchResult(
                url="https://cachedcorp.com",
                status_code=200,
                html="<html><body><a href='/contact'>contact</a><p>mail@cachedcorp.com</p></body></html>",
                response_time_ms=5.0,
                content_type="text/html",
            )

        with patch.object(enricher_a, "_fetch_page", side_effect=_mock_fetch):
            enricher_a.enrich_website(target_url="https://cachedcorp.com")

        fetches_by_first_enricher = fetch_count

        # New enricher instance — should still hit the global cache
        enricher_b = ProductionWebsiteEnricher(max_pages=5)
        with patch.object(enricher_b, "_fetch_page", side_effect=_mock_fetch):
            enricher_b.enrich_website(target_url="https://cachedcorp.com")

        # No new fetches should have been made by the second enricher
        assert fetch_count == fetches_by_first_enricher, (
            f"PRESERVATION BROKEN: global cache miss for second enricher instance — "
            f"{fetch_count - fetches_by_first_enricher} new HTTP fetches made. "
            "The _GLOBAL_DOMAIN_CACHE is not being respected across instances."
        )

        _GLOBAL_DOMAIN_CACHE.clear()


# ===========================================================================
# Test 2 — Conflict recording
# Req 3.3: when provider_email conflicts with crawled email, conflicts dict is populated
# ===========================================================================

class TestConflictRecording:
    """enrich_website must record email conflicts in the result.conflicts dict."""

    def test_provider_email_different_from_crawled_email_populates_conflicts(self):
        """
        PRESERVATION 2 — Conflict Recording (req 3.3)

        When provider_email differs from the email found by crawling, the result's
        conflicts dict must have an "email" key with conflict=True. It must NOT
        silently overwrite either value.

        Observing on unfixed code to confirm this already works correctly.
        """
        from backend.app.enrichment.website_enricher import PageFetchResult, ProductionWebsiteEnricher

        enricher = ProductionWebsiteEnricher(max_pages=5)

        PROVIDER_EMAIL = "old-record@abccorp.com"
        CRAWLED_EMAIL = "owner@abccorp.com"

        # Homepage with contact link; contact page has the crawled email
        def _mock_fetch(url: str) -> PageFetchResult:
            if "contact" in url:
                return PageFetchResult(
                    url=url,
                    status_code=200,
                    html=f"<html><body><p>Reach us at {CRAWLED_EMAIL}</p></body></html>",
                    response_time_ms=10.0,
                    content_type="text/html",
                )
            return PageFetchResult(
                url="https://abccorp.com",
                status_code=200,
                html="<html><body><a href='/contact'>Contact</a></body></html>",
                response_time_ms=8.0,
                content_type="text/html",
            )

        with patch.object(enricher, "_fetch_page", side_effect=_mock_fetch):
            result = enricher.enrich_website(
                target_url="https://abccorp.com",
                provider_email=PROVIDER_EMAIL,
            )

        assert "email" in result.conflicts, (
            "PRESERVATION BROKEN: conflicts dict has no 'email' key. "
            f"provider_email={PROVIDER_EMAIL!r} differs from crawled {CRAWLED_EMAIL!r} "
            "but no conflict was recorded."
        )
        assert result.conflicts["email"].get("conflict") is True, (
            "PRESERVATION BROKEN: conflicts['email']['conflict'] is not True. "
            "The conflict was not correctly flagged."
        )
        assert result.conflicts["email"].get("provider_value") == PROVIDER_EMAIL, (
            "PRESERVATION BROKEN: conflicts['email']['provider_value'] does not match "
            f"the supplied provider email {PROVIDER_EMAIL!r}."
        )


# ===========================================================================
# Test 3 — Phone validation independence
# Req 3.7: phone REJECTED nullifies effective_phone but does NOT affect effective_email
# ===========================================================================

class TestPhoneValidationIndependence:
    """When phone is REJECTED, effective_phone is None but effective_email is unchanged."""

    def test_phone_rejection_nullifies_effective_phone_not_email(self):
        """
        PRESERVATION 3 — Phone Validation Independence (req 3.7)

        When VerificationAndEvidenceEngine rejects a phone number, effective_phone
        must be set to None. The effective_email field must remain unchanged.

        Uses a real NANP-invalid phone (area code 000) to trigger REJECTED status.
        Observing on unfixed code to confirm this already works correctly.
        """
        from backend.app.sources.base import NormalizedLeadRecord
        from backend.app.verification.engine import VerificationStatus

        orchestrator = _build_minimal_orchestrator({"enrichments": ["email", "phone"]})

        EXPECTED_EMAIL = "owner@testbusiness.com"
        INVALID_PHONE = "000-555-1234"  # area code 000 is invalid — triggers REJECTED

        candidate = NormalizedLeadRecord(
            source="google_maps",
            source_id="node/phone_rejection_test_001",
            business_name="Test Business Corp",
            website="https://testbusiness.com",
            phone=INVALID_PHONE,
            email=EXPECTED_EMAIL,
            address="456 Oak Ave, Toronto, ON",
            city="Toronto",
            state="Ontario",
            country="Canada",
        )

        # Mock enricher: return the same email, keep the invalid phone in result
        mock_enr_res = MagicMock()
        mock_enr_res.contacts.emails = [{"email": EXPECTED_EMAIL, "source": "crawled"}]
        mock_enr_res.contacts.phones = []
        mock_enr_res.contacts.whatsapp_links = []
        mock_enr_res.social_profiles = {}
        mock_enr_res.seo.title = "Test Business"
        mock_enr_res.seo.h1_tags = []
        mock_enr_res.business_info.business_name = "Test Business Corp"
        orchestrator.enricher.enrich_website.return_value = mock_enr_res

        with patch("backend.app.orchestration.discovery_orchestrator.publish_job_progress"):
            results = orchestrator.stage_2_enrich_and_verify([candidate])

        assert len(results) == 1
        result = results[0]

        # Phone must be nullified (REJECTED area code 000)
        assert result["effective_phone"] is None, (
            f"PRESERVATION BROKEN: phone with area code 000 was not rejected. "
            f"effective_phone={result['effective_phone']!r}. "
            "Phone rejection logic is not working correctly."
        )

        # Email must NOT be affected by phone rejection
        assert result["effective_email"] == EXPECTED_EMAIL, (
            f"PRESERVATION BROKEN: phone rejection affected effective_email. "
            f"Expected {EXPECTED_EMAIL!r}, got {result['effective_email']!r}. "
            "Phone and email rejection must be independent."
        )


# ===========================================================================
# Test 4 — No-website skip
# Req 3.5: when rec.website is None, enrich_website is never called
# ===========================================================================

class TestNoWebsiteSkip:
    """When rec.website is None, enrichment is skipped entirely."""

    def test_enrich_website_not_called_when_website_is_none(self):
        """
        PRESERVATION 4 — No-Website Skip (req 3.5)

        When a lead has no website URL, enrich_website must never be called and
        effective_email must remain equal to rec.email unchanged.

        Observing on unfixed code to confirm this already works correctly.
        """
        from backend.app.sources.base import NormalizedLeadRecord

        orchestrator = _build_minimal_orchestrator({"enrichments": ["email"]})

        ORIGINAL_EMAIL = "info@nowebsite.com"

        candidate = NormalizedLeadRecord(
            source="google_maps",
            source_id="node/no_website_test_001",
            business_name="No Website Business",
            website=None,  # no website URL
            phone="+1 416 555 9999",
            email=ORIGINAL_EMAIL,
            address="789 Elm St, Toronto, ON",
            city="Toronto",
            state="Ontario",
            country="Canada",
        )

        with patch("backend.app.orchestration.discovery_orchestrator.publish_job_progress"):
            results = orchestrator.stage_2_enrich_and_verify([candidate])

        assert len(results) == 1
        result = results[0]

        # enrich_website must have never been called
        orchestrator.enricher.enrich_website.assert_not_called()

        # effective_email must be the original unmodified email
        assert result["effective_email"] == ORIGINAL_EMAIL, (
            f"PRESERVATION BROKEN: effective_email was changed for a no-website lead. "
            f"Expected {ORIGINAL_EMAIL!r}, got {result['effective_email']!r}."
        )

        assert result["enr_res"] is None, (
            "PRESERVATION BROKEN: enr_res is not None for a no-website lead. "
            "enrich_website should not have been called."
        )


# ===========================================================================
# Test 5 — Keyword pages prioritised
# Req 3.4: keyword pages (e.g. /contact) appear before generic links (/our-story)
# ===========================================================================

class TestKeywordPagesPrioritised:
    """_discover_internal_links must return keyword-matched paths before generic ones."""

    def test_contact_page_appears_before_ourstory_in_discovered_links(self):
        """
        PRESERVATION 5 — Keyword Priority (req 3.4)

        When homepage HTML contains both /contact (a priority keyword) and
        /our-story (no keyword match), _discover_internal_links must return
        /contact before /our-story.

        Note: on UNFIXED code, /our-story is NOT in the fallback results because
        no fallback exists yet. We assert /contact IS present and appears first
        among the returned URLs.

        Observing on unfixed code to confirm keyword prioritisation already works.
        """
        from backend.app.enrichment.website_enricher import ProductionWebsiteEnricher

        enricher = ProductionWebsiteEnricher(max_pages=5)

        # HTML with both a keyword URL and a non-keyword URL
        html_with_mixed_links = """
        <!DOCTYPE html>
        <html>
        <body>
          <a href="/our-story">Our Story</a>
          <a href="/pricing">Pricing</a>
          <a href="/contact">Contact</a>
          <a href="/blog">Blog</a>
        </body>
        </html>
        """

        links = enricher._discover_internal_links(
            base_url="https://mixedlinks.com",
            html=html_with_mixed_links,
        )

        # /contact must be present — it matches the "contact" keyword
        contact_links = [l for l in links if "contact" in l]
        assert contact_links, (
            "PRESERVATION BROKEN: /contact link is missing from _discover_internal_links "
            "result, but 'contact' is a priority keyword."
        )

        # /contact must appear before /our-story IF /our-story is in the results
        # (on unfixed code it won't be, but if it is, /contact must come first)
        ourstory_links = [l for l in links if "our-story" in l]
        if ourstory_links:
            contact_idx = links.index(contact_links[0])
            ourstory_idx = links.index(ourstory_links[0])
            assert contact_idx < ourstory_idx, (
                f"PRESERVATION BROKEN: /contact (index {contact_idx}) appears AFTER "
                f"/our-story (index {ourstory_idx}). Keyword links must be prioritised."
            )

    def test_multiple_keyword_pages_sorted_by_priority_rank(self):
        """
        PRESERVATION 5b — Multiple keywords keep their relative priority.

        'team' (rank 0) must appear before 'contact' (rank 12) in the results.
        """
        from backend.app.enrichment.website_enricher import ProductionWebsiteEnricher

        enricher = ProductionWebsiteEnricher(max_pages=5)

        html = """
        <html><body>
          <a href="/services">Services</a>
          <a href="/contact-us">Contact Us</a>
          <a href="/our-team">Our Team</a>
          <a href="/about-us">About Us</a>
        </body></html>
        """

        links = enricher._discover_internal_links(
            base_url="https://priority-test.com", html=html
        )

        team_links = [l for l in links if "team" in l]
        contact_links = [l for l in links if "contact" in l]

        assert team_links, "Expected /our-team to be in results (keyword: 'team')"
        assert contact_links, "Expected /contact-us to be in results (keyword: 'contact')"

        team_idx = links.index(team_links[0])
        contact_idx = links.index(contact_links[0])

        assert team_idx < contact_idx, (
            f"PRESERVATION BROKEN: 'team' keyword (rank 0) appeared at index {team_idx} "
            f"but 'contact' keyword appeared at index {contact_idx}. "
            "Higher-priority keywords must come first."
        )


# ===========================================================================
# Test 6 — Enrichment-off verification passthrough
# Req: when enrichment_enabled=False, VerificationAndEvidenceEngine is NOT called
# ===========================================================================

class TestEnrichmentOffVerificationPassthrough:
    """With enrichment_enabled=False, the verification engine is not invoked."""

    def test_verify_candidate_not_called_when_enrichment_disabled(self):
        """
        PRESERVATION 6 — Enrichment-Off Verification Passthrough

        When job_state["enrichments"] is falsy (enrichment_enabled=False),
        VerificationAndEvidenceEngine.verify_candidate must NOT be called.
        The returned v_res must be a baseline OverallVerificationResult with
        decision="ACCEPT" and composite_confidence=0.5.

        This is the current early-return path on unfixed code.
        Observing to confirm this existing fast-path continues to work after the fix.
        """
        from backend.app.sources.base import NormalizedLeadRecord
        from backend.app.verification.engine import OverallVerificationResult

        orchestrator = _build_minimal_orchestrator({"enrichments": []})

        candidate = NormalizedLeadRecord(
            source="google_maps",
            source_id="node/enrichment_off_test_001",
            business_name="Enrichment Off Corp",
            website="https://enrichmentoff.com",
            phone="+1 416 555 8888",
            email="legit@enrichmentoff.com",
            address="321 Pine St, Toronto, ON",
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
        result = results[0]

        # VerificationAndEvidenceEngine must NOT have been called
        mock_vae.verify_candidate.assert_not_called()

        # v_res must be the baseline OverallVerificationResult
        v_res = result["v_res"]
        assert isinstance(v_res, OverallVerificationResult), (
            f"PRESERVATION BROKEN: v_res is not an OverallVerificationResult. "
            f"Got {type(v_res)}."
        )
        assert v_res.decision == "ACCEPT", (
            f"PRESERVATION BROKEN: baseline v_res.decision should be 'ACCEPT', "
            f"got {v_res.decision!r}."
        )
        assert v_res.composite_confidence == 0.5, (
            f"PRESERVATION BROKEN: baseline composite_confidence should be 0.5, "
            f"got {v_res.composite_confidence}."
        )
        assert v_res.is_verified_entity is False, (
            "PRESERVATION BROKEN: baseline v_res.is_verified_entity should be False."
        )


# ===========================================================================
# PBT 7 — Email crawl never stores phone number in effective_email
# Req 3.1, 3.2: for non-buggy inputs (enrichment_enabled=True, valid email already found)
# effective_email must never contain a phone number
# ===========================================================================

PHONE_STRINGS = st.one_of(
    # North American phone formats
    st.builds(
        lambda a, p, l: f"({a:03d}) {p:03d}-{l:04d}",
        a=st.integers(min_value=200, max_value=999),
        p=st.integers(min_value=200, max_value=999),
        l=st.integers(min_value=0, max_value=9999),
    ),
    st.builds(
        lambda a, p, l: f"{a:03d}-{p:03d}-{l:04d}",
        a=st.integers(min_value=200, max_value=999),
        p=st.integers(min_value=200, max_value=999),
        l=st.integers(min_value=0, max_value=9999),
    ),
)

VALID_ENRICHMENTS = st.one_of(
    st.just(["email"]),
    st.just(["email", "phone"]),
    st.just(["email", "website"]),
)


class TestPBTEmailNeverPhoneNumber:
    """PBT 7 — property: enrichment_enabled=True never stores phone in effective_email."""

    @given(
        phone_in_email=PHONE_STRINGS,
        enrichments=VALID_ENRICHMENTS,
        website=st.just("https://pbttest.com"),
    )
    @settings(max_examples=30, deadline=5000)
    def test_effective_email_never_contains_phone_when_enrichment_enabled(
        self, phone_in_email: str, enrichments: list[str], website: str
    ) -> None:
        """
        PBT 7 — PRESERVATION: for non-buggy inputs where enrichment_enabled=True,
        the fixed system must never store a phone number string in effective_email.

        We feed a lead whose rec.email is a phone number string. When enrichment is
        enabled and a valid email is found by crawling, effective_email must be the
        crawled email — never the phone number from rec.email.

        **Validates: Requirements 3.1, 3.2**
        """
        from backend.app.sources.base import NormalizedLeadRecord

        orchestrator = _build_minimal_orchestrator({"enrichments": enrichments})

        candidate = NormalizedLeadRecord(
            source="google_maps",
            source_id=f"node/pbt_email_{phone_in_email[:5]}",
            business_name="PBT Test Business",
            website=website,
            phone="+1 416 555 1234",
            email=phone_in_email,  # phone number in email column (the bug condition)
            address="1 PBT Ave, Toronto, ON",
            city="Toronto",
            state="Ontario",
            country="Canada",
        )

        CRAWLED_EMAIL = "owner@pbttest.com"

        mock_enr_res = MagicMock()
        mock_enr_res.contacts.emails = [{"email": CRAWLED_EMAIL, "source": "crawled"}]
        mock_enr_res.contacts.phones = []
        mock_enr_res.contacts.whatsapp_links = []
        mock_enr_res.social_profiles = {}
        mock_enr_res.seo.title = "PBT Test"
        mock_enr_res.seo.h1_tags = []
        mock_enr_res.business_info.business_name = "PBT Test Business"
        orchestrator.enricher.enrich_website.return_value = mock_enr_res

        with patch("backend.app.orchestration.discovery_orchestrator.publish_job_progress"):
            results = orchestrator.stage_2_enrich_and_verify([candidate])

        assert len(results) == 1
        effective_email = results[0]["effective_email"]

        # When enrichment is enabled and crawling returns an email, effective_email
        # must be the crawled email — never the phone number that was in rec.email
        if effective_email is not None:
            assert not PHONE_PATTERN.match(str(effective_email).strip()), (
                f"PBT 7 VIOLATION: effective_email is a phone number: {effective_email!r}. "
                f"phone_in_email={phone_in_email!r}, enrichments={enrichments!r}. "
                "When enrichment is enabled and crawling succeeds, the crawled email "
                "must replace the phone-number-in-email-column."
            )


# ===========================================================================
# PBT 8 — _discover_internal_links always prioritises keyword links
# Req 3.4: keyword pages must always appear before generic fallback pages
# ===========================================================================

# Strategy: generate a list of non-keyword paths
NON_KEYWORD_PATHS = st.lists(
    st.sampled_from([
        "/our-story", "/pricing", "/blog", "/gallery", "/portfolio",
        "/faq", "/menu", "/testimonials", "/events", "/news",
    ]),
    min_size=1,
    max_size=5,
    unique=True,
)

# Strategy: generate a list of keyword paths (always from the priority_keywords list)
KEYWORD_PATHS = st.lists(
    st.sampled_from([
        "/contact", "/about", "/about-us", "/contact-us",
        "/team", "/our-team", "/services", "/staff",
    ]),
    min_size=1,
    max_size=5,
    unique=True,
)


def _build_html_with_links(paths: list[str], base_domain: str = "https://kw-test.com") -> str:
    """Build an HTML page with anchor tags for each path."""
    anchors = "\n".join(f'  <a href="{p}">{p.strip("/").replace("-", " ").title()}</a>' for p in paths)
    return f"<html><body>\n{anchors}\n</body></html>"


class TestPBTKeywordLinksPrioritised:
    """PBT 8 — property: keyword-matched links always precede non-keyword links."""

    @given(
        keyword_paths=KEYWORD_PATHS,
        non_keyword_paths=NON_KEYWORD_PATHS,
    )
    @settings(max_examples=50, deadline=5000)
    def test_keyword_links_always_precede_generic_links(
        self, keyword_paths: list[str], non_keyword_paths: list[str]
    ) -> None:
        """
        PBT 8 — PRESERVATION: _discover_internal_links always returns keyword-matched
        URLs before non-keyword URLs when both types are present.

        On UNFIXED code, non-keyword links are never returned at all (no fallback),
        so this property holds trivially. After the fix adds a fallback, keyword links
        must still come first.

        **Validates: Requirements 3.4**
        """
        from backend.app.enrichment.website_enricher import ProductionWebsiteEnricher

        enricher = ProductionWebsiteEnricher(max_pages=5)

        # Interleave keyword and non-keyword paths to ensure ordering isn't incidental
        all_paths = []
        for kp, nkp in zip(keyword_paths, non_keyword_paths):
            all_paths.append(nkp)  # non-keyword first in HTML
            all_paths.append(kp)   # keyword second in HTML
        # Add any remaining paths
        all_paths.extend(keyword_paths[len(non_keyword_paths):])
        all_paths.extend(non_keyword_paths[len(keyword_paths):])

        html = _build_html_with_links(all_paths, base_domain="https://kw-test.com")
        links = enricher._discover_internal_links(
            base_url="https://kw-test.com", html=html
        )

        if not links:
            # No links returned is acceptable if HTML parsing found nothing
            return

        PRIORITY_KEYWORDS = [
            "team", "our-team", "staff", "leadership", "management", "founder", "owner",
            "people", "meet", "doctor", "doctors", "agents", "attorneys", "bio",
            "about", "about-us", "contact", "contact-us", "services",
        ]

        def is_keyword_link(url: str) -> bool:
            path = url.split("kw-test.com", 1)[-1].lower()
            return any(kw in path for kw in PRIORITY_KEYWORDS)

        keyword_indices = [i for i, url in enumerate(links) if is_keyword_link(url)]
        generic_indices = [i for i, url in enumerate(links) if not is_keyword_link(url)]

        if keyword_indices and generic_indices:
            max_keyword_idx = max(keyword_indices)
            min_generic_idx = min(generic_indices)
            assert max_keyword_idx < min_generic_idx, (
                f"PBT 8 VIOLATION: keyword link at index {max_keyword_idx} appears "
                f"AFTER a generic link at index {min_generic_idx}.\n"
                f"keyword_paths={keyword_paths!r}\n"
                f"non_keyword_paths={non_keyword_paths!r}\n"
                f"returned links={links!r}"
            )
