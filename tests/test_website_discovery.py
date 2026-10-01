from __future__ import annotations

import uuid
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.models import Workspace, ScrapeJob, Lead, SourceRecord, EvidenceRecord
from backend.app.models_phase2 import Base as Phase2Base, CanonicalLead, LeadObservation
from backend.app.sources.base import NormalizedLeadRecord
from backend.app.sources.osm_overpass import OSMOverpassConnector
from backend.app.enrichment.website_discovery import (
    CandidateFilter,
    CandidateURL,
    DiscoveryProvenance,
    VerificationDecision,
    WebsiteEntityVerifier,
    ZeroBudgetDiscoveryEngine,
)
from backend.app.worker import execute_single_query_plan, finalize_job_status


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Phase2Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    ws = Workspace(name="Test Workspace")
    session.add(ws)
    session.commit()
    session.refresh(ws)
    yield session, ws
    session.close()


def test_osm_website_priority_expansion():
    """Verifies that OSM Overpass parser strictly follows the 6-level website priority."""
    conn = OSMOverpassConnector()

    # 1. brand:website fallback
    f1 = {"id": 1, "type": "node", "lat": 19.0, "lon": 72.0, "tags": {"name": "Brand Cafe", "brand:website": "https://brand.com"}}
    r1 = conn._parse_element(f1)
    assert r1.website == "https://brand.com"

    # 2. operator:website prevails over brand:website
    f2 = {"id": 2, "type": "node", "lat": 19.0, "lon": 72.0, "tags": {"name": "Op Cafe", "operator:website": "https://operator.com", "brand:website": "https://brand.com"}}
    r2 = conn._parse_element(f2)
    assert r2.website == "https://operator.com"

    # 3. contact:url prevails over url
    f3 = {"id": 3, "type": "node", "lat": 19.0, "lon": 72.0, "tags": {"name": "Contact Url Cafe", "contact:url": "https://contacturl.com", "url": "https://url.com"}}
    r3 = conn._parse_element(f3)
    assert r3.website == "https://contacturl.com"

    # 4. website prevails over all
    f4 = {"id": 4, "type": "node", "lat": 19.0, "lon": 72.0, "tags": {"name": "Top Cafe", "website": "https://top.com", "contact:website": "https://cw.com", "contact:url": "https://cu.com"}}
    r4 = conn._parse_element(f4)
    assert r4.website == "https://top.com"


def test_existing_website_preserved_no_discovery_triggered(test_db):
    """Verifies that leads with existing websites do not trigger candidate discovery search."""
    session, ws = test_db

    job = ScrapeJob(
        workspace_id=ws.id,
        niche="restaurant",
        country="India",
        state="Mumbai",
        target_lead_count=5,
        sources=["osm_overpass"],
        enrichments=["website"],
        status="RUNNING",
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    fake_records = [
        NormalizedLeadRecord(
            source="osm_overpass",
            source_id="node/existing_1",
            business_name="Existing Site Cafe",
            website="https://existingsite.com",
            phone="+91 9820112233",
            category="cafe",
            address="Goregaon, Mumbai",
            raw_data={"tags": {"name": "Existing Site Cafe", "website": "https://existingsite.com"}},
        )
    ]

    mock_connector = MagicMock()
    mock_connector.search_leads.return_value = fake_records
    mock_connector.supports_category.return_value = True

    plan = {"source": "osm_overpass", "query": "cafe", "reason": "test", "location": "Mumbai"}

    with patch("backend.app.worker.get_connectors", return_value={"osm_overpass": mock_connector}), \
         patch("backend.app.enrichment.website_discovery.ZeroBudgetDiscoveryEngine.discover_and_verify_official_website") as mock_disc:

        execute_single_query_plan(session, job, plan)
        finalize_job_status(session, job, str(job.id))

    # Candidate discovery should NOT be invoked
    assert mock_disc.call_count == 0
    lead = session.scalars(select(Lead).where(Lead.job_id == job.id)).first()
    assert lead.website == "https://existingsite.com"


def test_missing_website_verified_candidate_accepted(test_db):
    """Verifies that when website is missing, candidate is discovered, verified via phone match, and persisted."""
    session, ws = test_db

    job = ScrapeJob(
        workspace_id=ws.id,
        niche="restaurant",
        country="India",
        state="Mumbai",
        target_lead_count=5,
        sources=["osm_overpass"],
        enrichments=["website"],
        status="RUNNING",
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    fake_records = [
        NormalizedLeadRecord(
            source="osm_overpass",
            source_id="node/missing_1",
            business_name="Authentic Curry House",
            website=None,  # MISSING WEBSITE
            phone="+91 9820998877",
            category="restaurant",
            address="Goregaon West, Mumbai 400062",
            city="Mumbai",
            raw_data={"tags": {"name": "Authentic Curry House", "phone": "+91 9820998877"}},
        )
    ]

    mock_connector = MagicMock()
    mock_connector.search_leads.return_value = fake_records
    mock_connector.supports_category.return_value = True

    plan = {"source": "osm_overpass", "query": "restaurant", "reason": "test", "location": "Mumbai"}

    # Mock HTML response that contains exact phone number and title
    mock_html = """
    <html>
      <head><title>Authentic Curry House - Official Site</title></head>
      <body>
        <h1>Welcome to Authentic Curry House</h1>
        <p>Call us at +91 9820998877</p>
        <p>Located in Mumbai 400062</p>
      </body>
    </html>
    """

    mock_candidates = [
        CandidateURL(
            url="https://authenticcurryhouse.com",
            domain="authenticcurryhouse.com",
            discovery_source="ZERO_BUDGET_SEARCH_DDG",
            rank=1,
        )
    ]

    with patch("backend.app.worker.get_connectors", return_value={"osm_overpass": mock_connector}), \
         patch("backend.app.enrichment.website_discovery.ZeroBudgetDiscoveryEngine.discover_from_zero_budget_search", return_value=mock_candidates), \
         patch("backend.app.enrichment.website_discovery.WebsiteEntityVerifier.fetch_page_html", return_value=(200, "https://authenticcurryhouse.com", mock_html)):

        execute_single_query_plan(session, job, plan)
        finalize_job_status(session, job, str(job.id))

    lead = session.scalars(select(Lead).where(Lead.job_id == job.id)).first()
    assert lead.website == "https://authenticcurryhouse.com"
    ev = session.scalars(select(EvidenceRecord).where(EvidenceRecord.lead_id == lead.id)).first()
    assert ev is not None
    assert ev.status == "ACCEPT"
    assert ev.source == DiscoveryProvenance.ZERO_BUDGET_VERIFIED.value
    assert ev.confidence_score >= 80


def test_directory_candidate_rejected():
    """Verifies that directory and aggregator candidates are immediately rejected."""
    verifier = WebsiteEntityVerifier()
    for bad_domain in ["yelp.com", "tripadvisor.com", "justdial.com", "zomato.com", "facebook.com"]:
        candidate = CandidateURL(url=f"https://{bad_domain}/biz/curry-house", domain=bad_domain, discovery_source="SEARCH")
        res = verifier.verify_candidate(candidate=candidate, business_name="Curry House", phone="9820000000")
        assert res.decision == VerificationDecision.REJECT
        assert res.confidence_score == 0.0


def test_parked_domain_rejected():
    """Verifies that parked domain holding pages are immediately rejected."""
    verifier = WebsiteEntityVerifier()
    candidate = CandidateURL(url="https://curryhouseparked.com", domain="curryhouseparked.com", discovery_source="SEARCH")
    parked_html = "<html><body><h1>This domain is for sale! Buy now on GoDaddy Parking</h1></body></html>"

    with patch.object(verifier, "fetch_page_html", return_value=(200, "https://curryhouseparked.com", parked_html)):
        res = verifier.verify_candidate(candidate=candidate, business_name="Curry House", phone="9820000000")
        assert res.decision == VerificationDecision.REJECT
        assert "parked domain" in str(res.matched_reasons).lower()


def test_phone_and_address_mismatch_fails_verification():
    """Verifies that an unrelated business with matching name but wrong phone/location is rejected or marked review."""
    verifier = WebsiteEntityVerifier()
    candidate = CandidateURL(url="https://unrelatedcurry.com", domain="unrelatedcurry.com", discovery_source="SEARCH")
    # HTML from a different city with different phone number
    unrelated_html = "<html><head><title>Curry House London</title></head><body>Call +44 20 7946 0991 in London UK</body></html>"

    with patch.object(verifier, "fetch_page_html", return_value=(200, "https://unrelatedcurry.com", unrelated_html)):
        res = verifier.verify_candidate(
            candidate=candidate,
            business_name="Curry House",
            phone="+91 9820000000",
            city="Mumbai",
            address="Goregaon, Mumbai",
        )
        assert res.decision != VerificationDecision.ACCEPT


def test_ssrf_url_blocked():
    """Verifies that internal network and loopback URLs are blocked by SSRF guard."""
    verifier = WebsiteEntityVerifier()
    for bad_url in ["http://127.0.0.1:8000", "http://169.254.169.254/metadata", "http://192.168.1.1"]:
        status, final_url, html = verifier.fetch_page_html(bad_url)
        assert status is None
        assert html is None


def test_http_error_isolation_preserves_lead(test_db):
    """Verifies that HTTP 403 / 500 / timeout in website discovery does not fail lead persistence."""
    session, ws = test_db

    job = ScrapeJob(
        workspace_id=ws.id,
        niche="restaurant",
        country="India",
        state="Mumbai",
        target_lead_count=5,
        sources=["osm_overpass"],
        enrichments=["website"],
        status="RUNNING",
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    fake_records = [
        NormalizedLeadRecord(
            source="osm_overpass",
            source_id="node/err_lead_1",
            business_name="Crash Cafe",
            website=None,
            phone="+91 9820111111",
            category="cafe",
            address="Mumbai",
            raw_data={"tags": {"name": "Crash Cafe"}},
        )
    ]

    mock_connector = MagicMock()
    mock_connector.search_leads.return_value = fake_records
    mock_connector.supports_category.return_value = True

    plan = {"source": "osm_overpass", "query": "cafe", "reason": "test", "location": "Mumbai"}

    with patch("backend.app.worker.get_connectors", return_value={"osm_overpass": mock_connector}), \
         patch("backend.app.enrichment.website_discovery.ZeroBudgetDiscoveryEngine.discover_and_verify_official_website", side_effect=RuntimeError("Network Timeout")):

        execute_single_query_plan(session, job, plan)
        finalize_job_status(session, job, str(job.id))

    # Lead MUST remain persisted and valid
    lead = session.scalars(select(Lead).where(Lead.job_id == job.id)).first()
    assert lead is not None
    assert lead.business_name == "Crash Cafe"
    assert lead.website is None
    assert job.leads_scraped == 1
    assert job.status in ("COMPLETED", "REGION_EXHAUSTED")
