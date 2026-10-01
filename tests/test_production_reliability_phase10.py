from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.enrichment.website_discovery import (
    CandidateURL,
    DiscoveryProvenance,
    VerificationDecision,
    VerificationResult,
)
from backend.app.enrichment.website_enricher import PageFetchResult
from backend.app.models import EvidenceRecord, Lead, ScrapeJob, SourceRecord, Workspace
from backend.app.models_phase2 import Base as Phase2Base, CanonicalLead
from backend.app.models_services import Base as ServicesBase, ServiceOpportunity
from backend.app.sources.base import NormalizedLeadRecord
from backend.app.worker import execute_single_query_plan, finalize_job_status


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Phase2Base.metadata.create_all(bind=engine)
    ServicesBase.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    ws = Workspace(name="Phase 10 Hardening Workspace")
    session.add(ws)
    session.commit()
    session.refresh(ws)
    yield session, ws
    session.close()


def test_idempotency_on_repeated_execution(test_db):
    """Verifies that running the same scrape job / lead batch twice creates ZERO duplicate entities."""
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

    records = [
        NormalizedLeadRecord(
            source="osm_overpass",
            source_id="node/idem_1",
            business_name="Idempotent Diner",
            website="https://idempotentdiner.com",
            phone="+91 9820112233",
            category="restaurant",
            address="Goregaon, Mumbai",
            raw_data={"tags": {"name": "Idempotent Diner", "website": "https://idempotentdiner.com"}},
        )
    ]

    mock_connector = MagicMock()
    mock_connector.search_leads.return_value = records
    mock_connector.supports_category.return_value = True

    plan = {"source": "osm_overpass", "query": "restaurant", "reason": "test", "location": "Mumbai"}

    with patch("backend.app.worker.get_connectors", return_value={"osm_overpass": mock_connector}), \
         patch("backend.app.enrichment.website_enricher.ProductionWebsiteEnricher._fetch_page", return_value=PageFetchResult(
             url="https://idempotentdiner.com", status_code=200, html="<html><head><title>Idempotent Diner</title></head><body>Welcome</body></html>",
             response_time_ms=100.0, content_type="text/html"
         )):

        # First Execution
        execute_single_query_plan(session, job, plan)
        finalize_job_status(session, job, str(job.id))

        # Second Execution (Exact Same Records)
        execute_single_query_plan(session, job, plan)
        finalize_job_status(session, job, str(job.id))

    # Assert Entity Counts: ZERO Duplicates
    leads = session.scalars(select(Lead)).all()
    canonical_leads = session.scalars(select(CanonicalLead)).all()
    source_records = session.scalars(select(SourceRecord)).all()
    evidence_records = session.scalars(select(EvidenceRecord)).all()

    assert len(leads) == 1
    assert len(canonical_leads) == 1
    assert len(source_records) == 1
    # Evidence records should be updated in-place (contacts, seo, lead_intelligence)
    assert len(evidence_records) <= 4


def test_mixed_state_production_batch(test_db):
    """Processes a 6-lead mixed-state batch ensuring complete isolation across diverse failure & success states."""
    session, ws = test_db

    job = ScrapeJob(
        workspace_id=ws.id,
        niche="mixed",
        country="India",
        state="Mumbai",
        target_lead_count=10,
        sources=["osm_overpass"],
        enrichments=["website"],
        status="RUNNING",
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    mixed_records = [
        # Lead A: OSM website present, reachable, good SEO, complete contact info
        NormalizedLeadRecord(
            source="osm_overpass", source_id="node/lead_a", business_name="Lead A Prime Bistro",
            website="https://leada.com", phone="+91 9820000001", category="bistro",
            address="Mumbai", raw_data={"tags": {"name": "Lead A Prime Bistro", "website": "https://leada.com"}},
        ),
        # Lead B: OSM website absent, website discovery finds nothing
        NormalizedLeadRecord(
            source="osm_overpass", source_id="node/lead_b", business_name="Lead B Street Stall",
            website=None, phone="+91 9820000002", category="street_food",
            address="Mumbai", raw_data={"tags": {"name": "Lead B Street Stall"}},
        ),
        # Lead C: OSM website present, HTTP 404
        NormalizedLeadRecord(
            source="osm_overpass", source_id="node/lead_c", business_name="Lead C Dead Site",
            website="https://deadsite404.com", phone="+91 9820000003", category="cafe",
            address="Mumbai", raw_data={"tags": {"name": "Lead C Dead Site", "website": "https://deadsite404.com"}},
        ),
        # Lead D: OSM website present, HTTP timeout
        NormalizedLeadRecord(
            source="osm_overpass", source_id="node/lead_d", business_name="Lead D Timeout Grill",
            website="https://timeoutgrill.com", phone="+91 9820000004", category="grill",
            address="Mumbai", raw_data={"tags": {"name": "Lead D Timeout Grill", "website": "https://timeoutgrill.com"}},
        ),
        # Lead E: OSM website present, reachable, website phone conflicts with OSM phone
        NormalizedLeadRecord(
            source="osm_overpass", source_id="node/lead_e", business_name="Lead E Conflict Lounge",
            website="https://conflictlounge.com", phone="+91 9820000005", category="lounge",
            address="Mumbai", raw_data={"tags": {"name": "Lead E Conflict Lounge", "website": "https://conflictlounge.com"}},
        ),
        # Lead F: Verified discovered website, successful enrichment
        NormalizedLeadRecord(
            source="osm_overpass", source_id="node/lead_f", business_name="Lead F Discovered Cafe",
            website=None, phone="+91 9820000006", category="cafe",
            address="Mumbai", raw_data={"tags": {"name": "Lead F Discovered Cafe", "phone": "+91 9820000006"}},
        ),
    ]

    mock_connector = MagicMock()
    mock_connector.search_leads.return_value = mixed_records
    mock_connector.supports_category.return_value = True

    def mock_fetch(url: str):
        if "leada.com" in url:
            return PageFetchResult(url=url, status_code=200, html="<html><head><title>Prime Bistro Mumbai</title><meta name='description' content='Best food in town'/></head><body><h1>Prime Bistro</h1><a href='mailto:info@leada.com'>Email</a></body></html>", response_time_ms=80.0, content_type="text/html")
        elif "deadsite404.com" in url:
            return PageFetchResult(url=url, status_code=404, html="", response_time_ms=150.0, content_type="text/html", error="Not Found")
        elif "timeoutgrill.com" in url:
            return PageFetchResult(url=url, status_code=None, html="", response_time_ms=5000.0, content_type="", error="Timeout")
        elif "conflictlounge.com" in url:
            return PageFetchResult(url=url, status_code=200, html="<html><body><a href='tel:+918888888888'>Call +91 8888888888</a></body></html>", response_time_ms=90.0, content_type="text/html")
        elif "discoveredcafe.com" in url:
            return PageFetchResult(url=url, status_code=200, html="<html><head><title>Lead F Discovered Cafe</title></head><body><h1>Welcome</h1><p>Call +91 9820000006</p></body></html>", response_time_ms=95.0, content_type="text/html")
        return PageFetchResult(url=url, status_code=404, html="", response_time_ms=100.0, content_type="text/html")

    def mock_disc_website(business_name, phone, email, address, city, raw_data_tags):
        if "Lead F" in business_name:
            return VerificationResult(
                decision=VerificationDecision.ACCEPT,
                confidence_score=0.90,
                verified_url="https://discoveredcafe.com",
                verified_domain="discoveredcafe.com",
                provenance=DiscoveryProvenance.ZERO_BUDGET_VERIFIED,
                matched_reasons=["Phone digit match"],
            )
        return VerificationResult(
            decision=VerificationDecision.REJECT,
            confidence_score=0.0,
            verified_url=None,
            verified_domain=None,
            provenance=DiscoveryProvenance.UNVERIFIED,
            matched_reasons=["No candidates"],
        )

    plan = {"source": "osm_overpass", "query": "mixed", "reason": "test", "location": "Mumbai"}

    with patch("backend.app.worker.get_connectors", return_value={"osm_overpass": mock_connector}), \
         patch("backend.app.enrichment.website_enricher.ProductionWebsiteEnricher._fetch_page", side_effect=mock_fetch), \
         patch("backend.app.enrichment.website_discovery.ZeroBudgetDiscoveryEngine.discover_and_verify_official_website", side_effect=mock_disc_website):

        execute_single_query_plan(session, job, plan)
        finalize_job_status(session, job, str(job.id))

    # All 6 leads MUST be persisted and valid
    leads = session.scalars(select(Lead)).all()
    assert len(leads) == 6
    assert job.leads_scraped == 6
    assert job.status in ("COMPLETED", "REGION_EXHAUSTED")

    # Lead A: Has website, enriched
    lead_a = session.scalars(select(Lead).where(Lead.business_name == "Lead A Prime Bistro")).first()
    assert lead_a.website == "https://leada.com"

    # Lead B: No website, remains valid
    lead_b = session.scalars(select(Lead).where(Lead.business_name == "Lead B Street Stall")).first()
    assert lead_b.website is None

    # Lead C: 404 site, remains persisted
    lead_c = session.scalars(select(Lead).where(Lead.business_name == "Lead C Dead Site")).first()
    assert lead_c.website == "https://deadsite404.com"

    # Lead D: Timeout site, remains persisted
    lead_d = session.scalars(select(Lead).where(Lead.business_name == "Lead D Timeout Grill")).first()
    assert lead_d.website == "https://timeoutgrill.com"

    # Lead E: Conflicting phone, OSM ground truth intact
    lead_e = session.scalars(select(Lead).where(Lead.business_name == "Lead E Conflict Lounge")).first()
    assert lead_e.phone == "+91 9820000005"  # OSM Ground Truth PRESERVED
    conf_ev = session.scalars(select(EvidenceRecord).where(EvidenceRecord.lead_id == lead_e.id, EvidenceRecord.field_name == "conflicts")).first()
    assert conf_ev is not None

    # Lead F: Discovered website assigned
    lead_f = session.scalars(select(Lead).where(Lead.business_name == "Lead F Discovered Cafe")).first()
    assert lead_f.website == "https://discoveredcafe.com"


def test_early_stopping_and_cancellation(test_db):
    """Verifies that reaching target_lead_count halts processing immediately without over-scraping."""
    session, ws = test_db

    job = ScrapeJob(
        workspace_id=ws.id,
        niche="cafe",
        country="India",
        state="Mumbai",
        target_lead_count=2,  # Target is 2
        sources=["osm_overpass"],
        enrichments=["website"],
        status="RUNNING",
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    records = [
        NormalizedLeadRecord(source="osm_overpass", source_id=f"node/stop_{i}", business_name=f"Stop Cafe {i}", website=None, phone=f"982000000{i}", category="cafe", address="Mumbai", raw_data={"tags": {"name": f"Stop Cafe {i}"}})
        for i in range(1, 10)  # 9 records available
    ]

    mock_connector = MagicMock()
    mock_connector.search_leads.return_value = records
    mock_connector.supports_category.return_value = True

    plan = {"source": "osm_overpass", "query": "cafe", "reason": "test", "location": "Mumbai"}

    with patch("backend.app.worker.get_connectors", return_value={"osm_overpass": mock_connector}):
        execute_single_query_plan(session, job, plan)
        finalize_job_status(session, job, str(job.id))

    assert job.status == "COMPLETED"
    assert job.completion_reason == "TARGET_REACHED"
    assert job.leads_scraped == 2
    leads = session.scalars(select(Lead)).all()
    assert len(leads) == 2


def test_lineage_and_provenance_distinction(test_db):
    """Verifies that PROVIDER_GROUND_TRUTH, ZERO_BUDGET_VERIFIED, and LEAD_INTELLIGENCE_ENGINE provenance remain distinct."""
    session, ws = test_db

    job = ScrapeJob(
        workspace_id=ws.id,
        niche="clinic",
        country="India",
        state="Mumbai",
        target_lead_count=2,
        sources=["osm_overpass"],
        enrichments=["website"],
        status="RUNNING",
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    records = [
        NormalizedLeadRecord(
            source="osm_overpass",
            source_id="node/lineage_1",
            business_name="Lineage Dental",
            website=None,
            phone="+91 9820111111",
            category="dentist",
            address="Mumbai",
            raw_data={"tags": {"name": "Lineage Dental", "phone": "+91 9820111111"}},
        )
    ]

    mock_connector = MagicMock()
    mock_connector.search_leads.return_value = records
    mock_connector.supports_category.return_value = True

    def mock_disc(business_name, phone, email, address, city, raw_data_tags):
        return VerificationResult(
            decision=VerificationDecision.ACCEPT,
            confidence_score=0.95,
            verified_url="https://lineagedental.com",
            verified_domain="lineagedental.com",
            provenance=DiscoveryProvenance.ZERO_BUDGET_VERIFIED,
            matched_reasons=["Phone match"],
        )

    plan = {"source": "osm_overpass", "query": "dentist", "reason": "test", "location": "Mumbai"}

    with patch("backend.app.worker.get_connectors", return_value={"osm_overpass": mock_connector}), \
         patch("backend.app.enrichment.website_discovery.ZeroBudgetDiscoveryEngine.discover_and_verify_official_website", side_effect=mock_disc), \
         patch("backend.app.enrichment.website_enricher.ProductionWebsiteEnricher._fetch_page", return_value=PageFetchResult(
             url="https://lineagedental.com", status_code=200, html="<html><head><title>Lineage Dental Clinic</title></head><body><h1>Welcome</h1></body></html>",
             response_time_ms=90.0, content_type="text/html"
         )):

        execute_single_query_plan(session, job, plan)
        finalize_job_status(session, job, str(job.id))

    # Check evidence records provenance distinction
    ev_website = session.scalars(select(EvidenceRecord).where(EvidenceRecord.field_name == "website")).first()
    ev_intel = session.scalars(select(EvidenceRecord).where(EvidenceRecord.field_name == "lead_intelligence")).first()
    ev_seo = session.scalars(select(EvidenceRecord).where(EvidenceRecord.field_name == "seo")).first()

    assert ev_website.source == "ZERO_BUDGET_VERIFIED"
    assert ev_intel.source == "LEAD_INTELLIGENCE_ENGINE"
    assert ev_seo.source == "WEBSITE_ENRICHMENT"


def test_provider_failure_completion_semantics(test_db):
    """Verifies that a job with 0 leads and total provider failure results in FAILED / PROVIDER_UNAVAILABLE."""
    session, ws = test_db

    job = ScrapeJob(
        workspace_id=ws.id,
        niche="clinic",
        country="India",
        state="Mumbai",
        target_lead_count=5,
        sources=["osm_overpass"],
        enrichments=[],
        status="RUNNING",
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    mock_connector = MagicMock()
    mock_connector.search_leads.side_effect = Exception("OSM Overpass Timeout / 504")
    mock_connector.supports_category.return_value = True

    plan = {"source": "osm_overpass", "query": "clinic", "reason": "test", "location": "Mumbai"}

    with patch("backend.app.worker.get_connectors", return_value={"osm_overpass": mock_connector}):
        execute_single_query_plan(session, job, plan)
        finalize_job_status(session, job, str(job.id))

    assert job.status == "FAILED"
    assert job.completion_reason == "PROVIDER_UNAVAILABLE"
    assert job.leads_scraped == 0
