import time
import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.enrichment.email_verifier import EmailVerificationResult, EmailVerifier
from backend.app.enrichment.website_enricher import (
    EnrichedWebsiteResult,
    ExtractedBusinessInfo,
    ExtractedContacts,
    ExtractedSEOInfo,
    PageFetchResult,
    ProductionWebsiteEnricher,
    WebsiteHealth,
)
from backend.app.models import Lead, RawLead, RawLeadSheet, ScrapeJob
from backend.app.orchestration.discovery_orchestrator import (
    DiscoveryAction,
    DiscoveryOrchestrator,
    OrchestratorMetrics,
)
import socket
from backend.app.sources.base import NormalizedLeadRecord, SourceConnector


def make_enrich_result(emails=None, target_url="https://example.com"):
    return EnrichedWebsiteResult(
        domain="example.com",
        target_url=target_url,
        health=WebsiteHealth(is_reachable=True, http_status=200),
        contacts=ExtractedContacts(emails=emails or []),
        business_info=ExtractedBusinessInfo(),
        seo=ExtractedSEOInfo(),
    )


# In-memory SQLite fixture for orchestrated job tests
@pytest.fixture
def test_db():
    import backend.app.models_phase2 as mp2
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    mp2.Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session, TestingSessionLocal
    finally:
        session.close()


def _create_mock_job(session, target=10, require_verified_email=True):
    job_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    job = ScrapeJob(
        id=job_id,
        workspace_id=workspace_id,
        niche="Web Design",
        country="United Kingdom",
        region="London",
        state="London",
        target_lead_count=target,
        status="RUNNING",
        enrichments={"require_verified_email": require_verified_email},
        sources=["osm_overpass"],
        service=None,
        leads_scraped=0,
        progress_percent=0.0,
        discovered_count=0,
        valid_count=0,
    )
    session.add(job)
    session.commit()
    return job


# ---------------------------------------------------------------------------
# Test 1: Published email on homepage is extracted instead of generated address
# ---------------------------------------------------------------------------
def test_01_published_email_on_homepage_extracted():
    enricher = ProductionWebsiteEnricher(max_pages=3)
    homepage_html = """
    <html>
        <body>
            <h1>Apex Digital Agency</h1>
            <p>Welcome! Email us at: <a href="mailto:hello@apexdigital.co.uk">hello@apexdigital.co.uk</a></p>
        </body>
    </html>
    """
    contacts = enricher._extract_contacts_from_html(
        homepage_html,
        page_url="https://apexdigital.co.uk",
    )
    emails = [e["email"] for e in contacts.emails]
    assert "hello@apexdigital.co.uk" in emails
    # Ensure it's not a synthetic/hallucinated address
    selected = contacts.emails[0]
    assert selected["email"] == "hello@apexdigital.co.uk"
    assert selected["source_url"] == "https://apexdigital.co.uk"


# ---------------------------------------------------------------------------
# Test 2: Email on About/Contact is discovered when absent from homepage
# ---------------------------------------------------------------------------
def test_02_email_on_subpage_discovered_when_absent_from_homepage():
    enricher = ProductionWebsiteEnricher(max_pages=3)
    homepage_html = "<html><body><h1>Apex Agency</h1><a href='/contact'>Contact Us</a></body></html>"
    contact_html = "<html><body><p>Reach our support team: support@apexdigital.co.uk</p></body></html>"

    with patch.object(enricher, "_fetch_page") as mock_fetch:
        from backend.app.enrichment.website_enricher import PageFetchResult

        def side_effect(url):
            if "contact" in url:
                return PageFetchResult(url=url, status_code=200, html=contact_html, response_time_ms=50.0, content_type="text/html")
            return PageFetchResult(url=url, status_code=200, html=homepage_html, response_time_ms=50.0, content_type="text/html")

        mock_fetch.side_effect = side_effect
        enrich_res = enricher.enrich_website("https://apexdigital.co.uk")

        extracted_emails = [e["email"] for e in enrich_res.contacts.emails]
        assert "support@apexdigital.co.uk" in extracted_emails
        assert any("contact" in e["source_url"] for e in enrich_res.contacts.emails)


# ---------------------------------------------------------------------------
# Test 3: Named decision-maker outranks generic inbox when both are available
# ---------------------------------------------------------------------------
def test_03_decision_maker_outranks_generic_inbox():
    enricher = ProductionWebsiteEnricher(max_pages=3)
    homepage_html = "<html><body><a href='mailto:info@agency.com'>info@agency.com</a><a href='/team'>Our Team</a></body></html>"
    team_html = "<html><body><h3>Founder & CEO</h3><p>Contact Jane Smith at <a href='mailto:jane.smith@agency.com'>jane.smith@agency.com</a></p></body></html>"

    with patch.object(enricher, "_fetch_page") as mock_fetch:
        from backend.app.enrichment.website_enricher import PageFetchResult

        def side_effect(url):
            if "team" in url:
                return PageFetchResult(url=url, status_code=200, html=team_html, response_time_ms=50.0, content_type="text/html")
            return PageFetchResult(url=url, status_code=200, html=homepage_html, response_time_ms=50.0, content_type="text/html")

        mock_fetch.side_effect = side_effect
        enrich_res = enricher.enrich_website("https://agency.com")

        # The emails list must rank the decision maker (priority 1) before the generic email (priority 3)
        assert len(enrich_res.contacts.emails) >= 2
        first_email = enrich_res.contacts.emails[0]
        assert first_email["email"] == "jane.smith@agency.com"
        assert first_email["priority"] == 1
        assert first_email["type"] == "decision_maker"
        assert first_email["source_backed"] is True

        second_email = enrich_res.contacts.emails[1]
        assert second_email["email"] == "info@agency.com"
        assert second_email["priority"] == 3
        assert second_email["type"] == "generic"


def test_role_inbox_is_not_misclassified_as_a_decision_maker():
    enricher = ProductionWebsiteEnricher(max_pages=1)
    contacts = enricher._extract_contacts_from_html(
        "<h2>Founder and CEO</h2><a href='mailto:ceo@agency.com'>CEO</a>",
        page_url="https://agency.com/leadership",
    )

    assert len(contacts.emails) == 1
    assert contacts.emails[0]["email"] == "ceo@agency.com"
    assert contacts.emails[0]["type"] == "generic"
    assert contacts.emails[0]["priority"] == 3


def test_placeholder_emails_are_rejected_but_published_emails_remain_eligible():
    enricher = ProductionWebsiteEnricher(max_pages=1)
    contacts = enricher._extract_contacts_from_html(
        """
        <a href='mailto:yourname@yourcompany.com'>Placeholder</a>
        <a href='mailto:name@domain.com'>Template</a>
        <a href='mailto:contact@northsideplumbing.co.uk'>Contact</a>
        """,
        page_url="https://northsideplumbing.co.uk/contact",
    )

    assert [contact["email"] for contact in contacts.emails] == [
        "contact@northsideplumbing.co.uk"
    ]
    assert EmailVerifier.is_placeholder_email("yourname@yourcompany.com")
    with patch("backend.app.enrichment.email_verifier.socket.getaddrinfo", return_value=[(None, None, None, None, None)]):
        assert EmailVerifier().verify("contact@northsideplumbing.co.uk").is_valid


# ---------------------------------------------------------------------------
# Test 4: Generic inbox is considered when no higher-priority contact is found
# ---------------------------------------------------------------------------
def test_04_generic_inbox_considered_when_no_higher_priority():
    enricher = ProductionWebsiteEnricher(max_pages=2)
    homepage_html = "<html><body><p>Questions? Contact us: contact@company.org</p></body></html>"

    with patch.object(enricher, "_fetch_page") as mock_fetch:
        from backend.app.enrichment.website_enricher import PageFetchResult
        mock_fetch.return_value = PageFetchResult(
            url="https://company.org", status_code=200, html=homepage_html, response_time_ms=50.0, content_type="text/html"
        )
        enrich_res = enricher.enrich_website("https://company.org")

        assert len(enrich_res.contacts.emails) == 1
        assert enrich_res.contacts.emails[0]["email"] == "contact@company.org"
        assert enrich_res.contacts.emails[0]["priority"] == 3
        assert enrich_res.contacts.emails[0]["type"] == "generic"


# ---------------------------------------------------------------------------
# Test 5: Fabricated email without source evidence is rejected
# ---------------------------------------------------------------------------
def test_05_fabricated_email_rejected():
    verifier = EmailVerifier()
    # Address marked as having no source evidence
    res = verifier.verify("john.doe@company.com", source_backed=False)
    assert not res.is_valid
    assert not res.source_backed
    assert res.error_message is not None


# ---------------------------------------------------------------------------
# Test 6: Malformed email is rejected
# ---------------------------------------------------------------------------
def test_06_malformed_email_rejected():
    verifier = EmailVerifier()
    malformed_candidates = [
        "not-an-email",
        "user@@domain.com",
        "user@domain..com",
        "user@.com",
        "@domain.com",
        "user@domain_without_tld",
    ]
    for cand in malformed_candidates:
        res = verifier.verify(cand)
        assert not res.is_valid, f"Expected {cand!r} to be rejected"
        assert res.deliverability_status == "INVALID"
        assert res.error_message is not None


# ---------------------------------------------------------------------------
# Test 7: Email with legitimate provider or digits is not rejected solely for those characteristics
# ---------------------------------------------------------------------------
def test_07_legitimate_provider_and_digits_accepted():
    verifier = EmailVerifier()
    # Patch socket.getaddrinfo so DNS never hits the network
    with patch("backend.app.enrichment.email_verifier.socket.getaddrinfo", return_value=[(None, None, None, None, None)]):
        # legitimate provider with digits in local part
        res1 = verifier.verify("studio42design@gmail.com", require_business_domain=False)
        assert res1.is_valid
        assert res1.is_generic_provider

        # business domain with digits — will be valid once DNS mock allows it
        res2 = verifier.verify("contact@agency101.co.uk", require_business_domain=False)
        assert res2.is_valid


# ---------------------------------------------------------------------------
# Test 8: Duplicate businesses do not inflate the qualified count
# ---------------------------------------------------------------------------
def test_08_duplicates_do_not_inflate_qualified_count():
    metrics = OrchestratorMetrics(requested=10)
    seen_keys = set()
    rec1 = NormalizedLeadRecord(
        source="osm_overpass",
        source_id="123",
        business_name="Unique Plumbing Ltd",
        website="https://uniqueplumbing.co.uk",
        phone="02079460000",
        email="info@uniqueplumbing.co.uk",
        address="10 High St, London",
        city="London",
    )
    rec2 = NormalizedLeadRecord(
        source="osm_overpass",
        source_id="123",  # same source_id
        business_name="Unique Plumbing Ltd",
        website="https://uniqueplumbing.co.uk",
        phone="02079460000",
        email="info@uniqueplumbing.co.uk",
        address="10 High St, London",
        city="London",
    )
    for r in [rec1, rec2]:
        key = r.get_idempotency_key()
        if key in seen_keys:
            metrics.duplicate_count += 1
            continue
        seen_keys.add(key)
        metrics.saved_count += 1

    assert metrics.saved_count == 1
    assert metrics.duplicate_count == 1


# ---------------------------------------------------------------------------
# Test 9: Discovery loop continues when a batch contains too few qualified leads
# ---------------------------------------------------------------------------
def test_09_discovery_loop_continues_on_under_yield(test_db):
    session, TestingSessionLocal = test_db
    job = _create_mock_job(session, target=3)

    # Mock connector returning 2 leads on page 1, 2 leads on page 2
    mock_connector = MagicMock()
    mock_connector.is_circuit_open.return_value = False
    mock_connector.source_name = "osm_overpass"

    batch1 = [
        NormalizedLeadRecord(source="osm_overpass", source_id="1", business_name="Business 1", website="https://b1.com", phone="01"),
        NormalizedLeadRecord(source="osm_overpass", source_id="2", business_name="Business 2", website="https://b2.com", phone="02"),
    ]
    batch2 = [
        NormalizedLeadRecord(source="osm_overpass", source_id="3", business_name="Business 3", website="https://b3.com", phone="03"),
        NormalizedLeadRecord(source="osm_overpass", source_id="4", business_name="Business 4", website="https://b4.com", phone="04"),
    ]

    call_count = {"n": 0}

    def mock_search(**kwargs):
        call_count["n"] += 1
        return batch1 if call_count["n"] == 1 else batch2

    mock_connector.search_leads.side_effect = mock_search
    mock_connector.acquire_rate_limit.return_value = True
    mock_connector.record_success = MagicMock()
    mock_connector.record_failure = MagicMock()

    with patch("backend.app.orchestration.discovery_orchestrator.SessionLocal", side_effect=TestingSessionLocal):
        orchestrator = DiscoveryOrchestrator(
            job=job,
            connectors={"osm_overpass": mock_connector},
            max_request_budget=10,
        )
        # Mock enricher: only business 1, 3, and 4 have emails
        def mock_enrich(target_url, **kwargs):
            if "b2.com" in target_url:
                return make_enrich_result(emails=[], target_url=target_url)
            domain = target_url.split("//")[-1].replace("/", "")
            return make_enrich_result(
                emails=[{"email": f"contact@{domain}", "priority": 3, "type": "generic", "source_url": target_url}],
                target_url=target_url,
            )

        orchestrator.enricher.enrich_website = MagicMock(side_effect=mock_enrich)
        with patch.object(orchestrator.email_verifier, "verify", return_value=EmailVerificationResult(is_valid=True, email="x@x.com", deliverability_status="DELIVERABILITY_VERIFIED")):
            orchestrator.run_discovery()

        assert orchestrator.metrics.saved_count >= 3
        assert orchestrator.job_state["status"] == "COMPLETED"
        assert orchestrator.job_state["completion_reason"] == "TARGET_REACHED"


# ---------------------------------------------------------------------------
# Test 10: Timeout or failed request does not terminate entire job
# ---------------------------------------------------------------------------
def test_10_isolated_failure_does_not_abort_job(test_db):
    session, TestingSessionLocal = test_db
    job = _create_mock_job(session, target=1)

    failing_connector = MagicMock()
    failing_connector.is_circuit_open.return_value = False
    failing_connector.source_name = "osm_overpass"
    failing_connector.search_leads.side_effect = TimeoutError("Network timeout on external source")
    failing_connector.acquire_rate_limit.return_value = True
    failing_connector.record_failure = MagicMock()
    failing_connector.record_success = MagicMock()

    working_connector = MagicMock()
    working_connector.is_circuit_open.return_value = False
    working_connector.source_name = "google_maps"
    working_connector.search_leads.return_value = [
        NormalizedLeadRecord(source="google_maps", source_id="w1", business_name="Working Business", website="https://working.com", phone="0111")
    ]
    working_connector.acquire_rate_limit.return_value = True
    working_connector.record_failure = MagicMock()
    working_connector.record_success = MagicMock()

    with patch("backend.app.orchestration.discovery_orchestrator.SessionLocal", side_effect=TestingSessionLocal):
        orchestrator = DiscoveryOrchestrator(
            job=job,
            connectors={"osm_overpass": failing_connector, "google_maps": working_connector},
            max_request_budget=10,
        )
        orchestrator.enricher.enrich_website = MagicMock(return_value=make_enrich_result(
            emails=[{"email": "info@working.com", "priority": 3, "type": "generic", "source_url": "https://working.com"}],
            target_url="https://working.com",
        ))
        with patch.object(orchestrator.email_verifier, "verify", return_value=EmailVerificationResult(is_valid=True, email="info@working.com", deliverability_status="DELIVERABILITY_VERIFIED")):
            orchestrator.run_discovery()

        assert orchestrator.metrics.saved_count == 1
        assert orchestrator.job_state["status"] == "COMPLETED"


# ---------------------------------------------------------------------------
# Test 11: Job can resume from saved progress
# ---------------------------------------------------------------------------
def test_11_job_resumes_from_saved_progress(test_db):
    session, TestingSessionLocal = test_db
    job = _create_mock_job(session, target=5)
    # Pre-populate 2 leads already saved in previous run
    job.leads_scraped = 2
    session.commit()

    mock_connector = MagicMock()
    mock_connector.is_circuit_open.return_value = False
    mock_connector.source_name = "osm_overpass"
    mock_connector.search_leads.return_value = [
        NormalizedLeadRecord(source="osm_overpass", source_id="res3", business_name="Resumed 3", website="https://r3.com", phone="03"),
        NormalizedLeadRecord(source="osm_overpass", source_id="res4", business_name="Resumed 4", website="https://r4.com", phone="04"),
        NormalizedLeadRecord(source="osm_overpass", source_id="res5", business_name="Resumed 5", website="https://r5.com", phone="05"),
    ]
    mock_connector.acquire_rate_limit.return_value = True
    mock_connector.record_success = MagicMock()
    mock_connector.record_failure = MagicMock()

    with patch("backend.app.orchestration.discovery_orchestrator.SessionLocal", side_effect=TestingSessionLocal):
        orchestrator = DiscoveryOrchestrator(
            job=job,
            connectors={"osm_overpass": mock_connector},
            max_request_budget=10,
        )
        orchestrator.metrics.saved_count = job.leads_scraped

        orchestrator.enricher.enrich_website = MagicMock(return_value=make_enrich_result(
            emails=[{"email": "contact@resumed.com", "priority": 3, "type": "generic", "source_url": "https://r.com"}],
            target_url="https://r.com",
        ))
        with patch.object(orchestrator.email_verifier, "verify", return_value=EmailVerificationResult(is_valid=True, email="contact@resumed.com", deliverability_status="DELIVERABILITY_VERIFIED")):
            orchestrator.run_discovery()

        assert orchestrator.metrics.saved_count == 5
        assert orchestrator.job_state["status"] == "COMPLETED"


# ---------------------------------------------------------------------------
# Test 12: 20-minute deadline produces clean partial result rather than false success
# ---------------------------------------------------------------------------
def test_12_sla_timeout_produces_clean_partial_result(test_db):
    session, TestingSessionLocal = test_db
    job = _create_mock_job(session, target=50)

    mock_connector = MagicMock()
    mock_connector.is_circuit_open.return_value = False
    mock_connector.source_name = "osm_overpass"
    mock_connector.search_leads.return_value = [
        NormalizedLeadRecord(source="osm_overpass", source_id=f"id_{i}", business_name=f"Business {i}", website=f"https://b{i}.com", phone="01")
        for i in range(10)
    ]
    mock_connector.acquire_rate_limit.return_value = True
    mock_connector.record_success = MagicMock()
    mock_connector.record_failure = MagicMock()

    with patch("backend.app.orchestration.discovery_orchestrator.SessionLocal", side_effect=TestingSessionLocal):
        # Configure small SLA timeout of 0.05 seconds to test timeout handling
        orchestrator = DiscoveryOrchestrator(
            job=job,
            connectors={"osm_overpass": mock_connector},
            max_duration_seconds=0.05,
        )
        orchestrator.metrics.start_time = time.time() - 1.0  # Force timeout immediately

        orchestrator.finalize_discovery()

        assert orchestrator.job_state["status"] in ("PARTIAL", "FAILED")
        assert orchestrator.job_state["completion_reason"] == "TIME_BUDGET_EXPIRED"
        assert orchestrator.job_state["status"] != "COMPLETED"


# ---------------------------------------------------------------------------
# Test 13: Completed job reports correct qualified count
# ---------------------------------------------------------------------------
def test_13_completed_job_reports_correct_qualified_count(test_db):
    session, TestingSessionLocal = test_db
    job = _create_mock_job(session, target=2)

    mock_connector = MagicMock()
    mock_connector.is_circuit_open.return_value = False
    mock_connector.source_name = "osm_overpass"
    mock_connector.search_leads.return_value = [
        NormalizedLeadRecord(source="osm_overpass", source_id="c1", business_name="Company 1", website="https://c1.com", phone="01"),
        NormalizedLeadRecord(source="osm_overpass", source_id="c2", business_name="Company 2", website="https://c2.com", phone="02"),
    ]
    mock_connector.acquire_rate_limit.return_value = True
    mock_connector.record_success = MagicMock()
    mock_connector.record_failure = MagicMock()

    with patch("backend.app.orchestration.discovery_orchestrator.SessionLocal", side_effect=TestingSessionLocal):
        orchestrator = DiscoveryOrchestrator(
            job=job,
            connectors={"osm_overpass": mock_connector},
        )
        orchestrator.enricher.enrich_website = MagicMock(return_value=make_enrich_result(
            emails=[{"email": "info@c.com", "priority": 3, "type": "generic", "source_url": "https://c.com"}],
            target_url="https://c.com",
        ))
        with patch.object(orchestrator.email_verifier, "verify", return_value=EmailVerificationResult(is_valid=True, email="info@c.com", deliverability_status="DELIVERABILITY_VERIFIED")):
            orchestrator.run_discovery()

        assert orchestrator.metrics.saved_count == 2
        assert orchestrator.job_state["leads_scraped"] == 2
        assert orchestrator.job_state["status"] == "COMPLETED"
        assert orchestrator.job_state["completion_reason"] == "TARGET_REACHED"


# ---------------------------------------------------------------------------
# Test 14: Unmet target within time budget is reported honestly
# ---------------------------------------------------------------------------
def test_14_unmet_target_reported_honestly(test_db):
    session, TestingSessionLocal = test_db
    job = _create_mock_job(session, target=100)

    mock_connector = MagicMock()
    mock_connector.is_circuit_open.return_value = False
    mock_connector.source_name = "osm_overpass"
    # Only 5 leads exist in total
    mock_connector.search_leads.return_value = [
        NormalizedLeadRecord(source="osm_overpass", source_id=f"lim_{i}", business_name=f"Limited {i}", website=f"https://lim{i}.com", phone="01")
        for i in range(5)
    ]
    mock_connector.acquire_rate_limit.return_value = True
    mock_connector.record_success = MagicMock()
    mock_connector.record_failure = MagicMock()

    with patch("backend.app.orchestration.discovery_orchestrator.SessionLocal", side_effect=TestingSessionLocal):
        orchestrator = DiscoveryOrchestrator(
            job=job,
            connectors={"osm_overpass": mock_connector},
        )
        orchestrator.enricher.enrich_website = MagicMock(return_value=make_enrich_result(
            emails=[{"email": "info@lim.com", "priority": 3, "type": "generic", "source_url": "https://lim.com"}],
            target_url="https://lim.com",
        ))
        with patch.object(orchestrator.email_verifier, "verify", return_value=EmailVerificationResult(is_valid=True, email="info@lim.com", deliverability_status="DELIVERABILITY_VERIFIED")):
            orchestrator.run_discovery()

        assert orchestrator.metrics.saved_count == 5
        assert orchestrator.metrics.saved_count < 100
        # Must report PARTIAL honestly, NOT COMPLETED
        assert orchestrator.job_state["status"] == "PARTIAL"
        assert orchestrator.job_state["completion_reason"] in ("DISCOVERY_EXHAUSTED", "TIME_BUDGET_EXPIRED")


# ---------------------------------------------------------------------------
# Controlled Benchmark Test: 70%+ Qualified-Lead Yield within Budget
# ---------------------------------------------------------------------------
def test_controlled_benchmark_70_percent_yield(test_db):
    session, TestingSessionLocal = test_db
    # Target: 50 qualified leads. Benchmark expects >= 70% yield (i.e. >= 35 qualified leads)
    job = _create_mock_job(session, target=50)

    # Generate 50 businesses, 40 of which have valid emails (80% yield)
    mock_records = []
    for i in range(50):
        has_email = (i < 40)
        mock_records.append(
            NormalizedLeadRecord(
                source="osm_overpass",
                source_id=f"bench_{i}",
                business_name=f"Benchmark Studio {i}",
                website=f"https://benchmark{i}.co.uk",
                phone=f"0207000{i:04d}",
                email=f"ceo@benchmark{i}.co.uk" if has_email else None,
                address=f"{i} London Road, London",
                city="London",
            )
        )

    mock_connector = MagicMock()
    mock_connector.is_circuit_open.return_value = False
    mock_connector.source_name = "osm_overpass"
    mock_connector.search_leads.return_value = mock_records
    mock_connector.acquire_rate_limit.return_value = True
    mock_connector.record_success = MagicMock()
    mock_connector.record_failure = MagicMock()

    with patch("backend.app.orchestration.discovery_orchestrator.SessionLocal", side_effect=TestingSessionLocal):
        orchestrator = DiscoveryOrchestrator(
            job=job,
            connectors={"osm_overpass": mock_connector},
            max_duration_seconds=1200.0,
        )

        def mock_enrich_benchmark(target_url, **kwargs):
            idx_str = target_url.replace("https://benchmark", "").replace(".co.uk", "")
            idx_str = idx_str.strip("/")
            idx = int(idx_str) if idx_str.isdigit() else 0
            if idx < 40:
                # 20 decision makers, 20 generic
                if idx < 20:
                    emails = [{"email": f"founder@benchmark{idx}.co.uk", "priority": 1, "type": "decision_maker", "source_url": f"{target_url}/team"}]
                else:
                    emails = [{"email": f"contact@benchmark{idx}.co.uk", "priority": 3, "type": "generic", "source_url": target_url}]
                return make_enrich_result(emails=emails, target_url=target_url)
            return make_enrich_result(emails=[], target_url=target_url)

        orchestrator.enricher.enrich_website = MagicMock(side_effect=mock_enrich_benchmark)

        with patch.object(
            orchestrator.email_verifier,
            "verify",
            return_value=EmailVerificationResult(is_valid=True, email="x@x.com", deliverability_status="DELIVERABILITY_VERIFIED")
        ):
            orchestrator.run_discovery()

        researched = orchestrator.metrics.researched_count
        saved = orchestrator.metrics.saved_count
        yield_pct = orchestrator.metrics.qualified_yield

        # Performance targets:
        # 1. Yield must be at least 70% of researched businesses (here 40/50 = 80%)
        assert yield_pct >= 70.0, f"Yield was {yield_pct}%, expected >= 70%"
        assert saved >= 35, f"Saved {saved} leads, expected at least 35 for target 50 at 70% yield"
        # 2. Decision makers prioritized
        assert orchestrator.metrics.decision_maker_count >= 20
        # 3. Time elapsed within 20m SLA (1200s)
        assert orchestrator.metrics.elapsed_time < 1200.0


def test_multi_niche_discovery_runs_end_to_end_with_mocked_websites(test_db):
    session, TestingSessionLocal = test_db
    job = _create_mock_job(session, target=2)
    job.niche = "Plumbing, Dentist"
    session.commit()
    records_by_query = {
        "plumbing": NormalizedLeadRecord(
            source="osm_overpass",
            source_id="multi-plumber",
            business_name="Northside Plumbing",
            category="Plumbing Contractor",
            website="https://northsideplumbing.co.uk",
            phone="+442079460001",
            address="1 High Street, London",
            city="London",
            state="London",
            country="United Kingdom",
            raw_data={"nationalPhoneNumber": "+442079460001", "business_status": "OPERATIONAL"},
        ),
        "dentist": NormalizedLeadRecord(
            source="osm_overpass",
            source_id="multi-dentist",
            business_name="Central Dental Studio",
            category="Dentist",
            website="https://centraldental.co.uk",
            phone="+442079460002",
            address="2 High Street, London",
            city="London",
            state="London",
            country="United Kingdom",
        ),
    }
    seen_queries = []

    def mock_search(query, location, limit, page, pagination_state):
        normalized_query = query.lower()
        seen_queries.append(normalized_query)
        return [records_by_query[normalized_query]] if page == 1 and normalized_query in records_by_query else []

    connector = MagicMock()
    connector.search_leads.side_effect = mock_search
    enricher = ProductionWebsiteEnricher(max_pages=1)
    mock_pages = {
        "northsideplumbing.co.uk": """
            <html><body><h2>Founder</h2>
            <p>Jane Smith <a href="mailto:jane.smith@northsideplumbing.co.uk">
            jane.smith@northsideplumbing.co.uk</a></p>
            <p>Template: email@yourdomain.com</p></body></html>
        """,
        "centraldental.co.uk": """
            <html><body><p>Contact us at
            <a href="mailto:info@centraldental.co.uk">info@centraldental.co.uk</a></p>
            <p>Template: name@domain.com</p></body></html>
        """,
    }

    def mock_website_fetch(url):
        html = next(content for domain, content in mock_pages.items() if domain in url)
        return PageFetchResult(
            url=url,
            status_code=200,
            html=html,
            response_time_ms=5.0,
            content_type="text/html",
        )

    with patch("backend.app.orchestration.discovery_orchestrator.SessionLocal", side_effect=TestingSessionLocal):
        orchestrator = DiscoveryOrchestrator(
            job=job,
            connectors={"osm_overpass": connector},
            max_request_budget=30,
            max_duration_seconds=1200.0,
        )
        orchestrator.enricher = enricher
        with patch.object(enricher, "_fetch_page", side_effect=mock_website_fetch):
            with patch.object(
                orchestrator.email_verifier,
                "verify",
                side_effect=lambda email, **kwargs: EmailVerificationResult(
                    is_valid=kwargs.get("source_backed", False),
                    email=email,
                    source_backed=kwargs.get("source_backed", False),
                    deliverability_status="DELIVERABILITY_VERIFIED",
                ),
            ):
                orchestrator.run_discovery()

    assert {"plumbing", "dentist"}.issubset(seen_queries)
    assert orchestrator.metrics.saved_count == 2
    assert orchestrator.metrics.researched_count == 2
    assert orchestrator.metrics.qualified_count == 2
    assert orchestrator.metrics.elapsed_time < 1200.0
    assert orchestrator.metrics.qualified_yield == 100.0
    assert orchestrator.job_state["completion_reason"] == "TARGET_REACHED"
    persisted_leads = session.query(Lead).filter(Lead.job_id == job.id).all()
    raw_leads = session.query(RawLead).filter(RawLead.sheet_id == job.id).all()
    assert len(persisted_leads) == len(raw_leads) == 2
    assert all(lead.email and lead.phone is None for lead in persisted_leads)
    assert all(lead.email and lead.phone is None for lead in raw_leads)
    assert all("nationalPhoneNumber" not in (lead.raw_data or {}) for lead in raw_leads)


def test_email_requirement_cannot_be_disabled_by_legacy_job_configuration(test_db):
    session, TestingSessionLocal = test_db
    job = _create_mock_job(session, target=1, require_verified_email=False)

    with patch("backend.app.orchestration.discovery_orchestrator.SessionLocal", side_effect=TestingSessionLocal):
        orchestrator = DiscoveryOrchestrator(job=job, connectors={})

    assert orchestrator.require_verified_email is True


def test_discovery_replenishes_query_queue_before_declaring_exhaustion(test_db):
    session, TestingSessionLocal = test_db
    job = _create_mock_job(session, target=1)
    job.niche = "Dentist"
    session.commit()
    searched_queries = []
    candidate = NormalizedLeadRecord(
        source="osm_overpass",
        source_id="expanded-dentist",
        business_name="Emergency Dental Care",
        category="Dentist",
        website="https://emergencydentist.co.uk",
        phone="+442079460003",
        address="3 High Street, London",
        city="London",
        state="London",
        country="United Kingdom",
    )

    def mock_search(query, **kwargs):
        searched_queries.append(query.lower())
        return [candidate] if query.lower() == "emergency dentist" else []

    connector = MagicMock()
    connector.search_leads.side_effect = mock_search
    with patch("backend.app.orchestration.discovery_orchestrator.SessionLocal", side_effect=TestingSessionLocal):
        orchestrator = DiscoveryOrchestrator(
            job=job,
            connectors={"osm_overpass": connector},
            max_request_budget=30,
        )
        orchestrator.enricher.enrich_website = MagicMock(
            return_value=make_enrich_result(
                emails=[{
                    "email": "info@emergencydentist.co.uk",
                    "priority": 3,
                    "type": "generic",
                    "source_url": "https://emergencydentist.co.uk",
                    "source_backed": True,
                }],
                target_url="https://emergencydentist.co.uk",
            )
        )
        with patch.object(
            orchestrator.email_verifier,
            "verify",
            side_effect=lambda email, **kwargs: EmailVerificationResult(
                is_valid=kwargs.get("source_backed", False),
                email=email,
                source_backed=kwargs.get("source_backed", False),
                deliverability_status="DELIVERABILITY_VERIFIED",
            ),
        ):
            orchestrator.run_discovery()

    assert "emergency dentist" in searched_queries
    assert orchestrator.metrics.saved_count == 1
    assert orchestrator.job_state["completion_reason"] == "TARGET_REACHED"


def test_discovery_paginates_and_retries_provider_actions_with_bounds(test_db):
    session, TestingSessionLocal = test_db
    job = _create_mock_job(session, target=5)
    first_page = NormalizedLeadRecord(
        source="osm_overpass",
        source_id="page-1",
        business_name="Page One Plumbing",
        website="https://pageone.co.uk",
        phone="+442079460004",
    )
    second_page = NormalizedLeadRecord(
        source="osm_overpass",
        source_id="page-2",
        business_name="Page Two Plumbing",
        website="https://pagetwo.co.uk",
        phone="+442079460005",
    )

    with patch("backend.app.orchestration.discovery_orchestrator.SessionLocal", side_effect=TestingSessionLocal):
        paginated_connector = MagicMock()

        def search_page(query, page, pagination_state, **kwargs):
            pagination_state["has_more"] = page == 1
            return [first_page] if page == 1 else [second_page]

        paginated_connector.search_leads.side_effect = search_page
        paginated = DiscoveryOrchestrator(job=job, connectors={"osm_overpass": paginated_connector})
        initial = DiscoveryAction(
            provider="osm_overpass",
            query="plumbing",
            query_reason="exact",
            location="London",
        )
        assert paginated.execute_discovery_action(initial) == [first_page]
        assert paginated.action_queue[0].page == 2
        assert paginated.execute_discovery_action(paginated.action_queue.pop(0)) == [second_page]
        assert not paginated.action_queue

        failing_connector = MagicMock()
        failing_connector.search_leads.side_effect = TimeoutError("transient timeout")
        retrying = DiscoveryOrchestrator(job=job, connectors={"osm_overpass": failing_connector})
        action = DiscoveryAction(
            provider="osm_overpass",
            query="plumbing",
            query_reason="exact",
            location="London",
        )
        for expected_retry in (1, 2):
            retrying.execute_discovery_action(action)
            action = retrying.action_queue.pop(0)
            assert action.retry_count == expected_retry
        retrying.execute_discovery_action(action)
        assert failing_connector.search_leads.call_count == 3
        assert not retrying.action_queue

        recovering_connector = MagicMock()
        recovering_connector.failure_count = 0

        def fail_once_then_recover(**kwargs):
            if recovering_connector.search_leads.call_count == 1:
                recovering_connector.failure_count += 1
                return []
            recovering_connector.failure_count = 0
            return [first_page]

        recovering_connector.search_leads.side_effect = fail_once_then_recover
        recovering = DiscoveryOrchestrator(job=job, connectors={"osm_overpass": recovering_connector})
        assert recovering.execute_discovery_action(
            DiscoveryAction(
                provider="osm_overpass",
                query="plumbing",
                query_reason="exact",
                location="London",
            )
        ) == []
        assert len(recovering.action_queue) == 1
        retry_action = recovering.action_queue.pop()
        assert recovering.execute_discovery_action(retry_action) == [first_page]
        assert "osm_overpass" not in recovering.metrics.sources_failed
