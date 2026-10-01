import uuid
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import select

from backend.app.database import SessionLocal
from backend.app.models import Workspace, ScrapeJob, Lead, EvidenceRecord, SourceRecord
from backend.app.models_phase2 import CanonicalLead
from backend.app.sources.base import NormalizedLeadRecord
from backend.app.worker import execute_single_query_plan, finalize_job_status
from backend.app.enrichment.website_discovery import (
    ZeroBudgetDiscoveryEngine,
    WebsiteEntityVerifier,
    CandidateURL,
    VerificationDecision,
)
from backend.app.enrichment.website_enricher import (
    ProductionWebsiteEnricher,
    PageFetchResult,
    ExtractedContacts,
    ExtractedSEOInfo,
    ExtractedBusinessInfo,
    WebsiteHealth,
)
from backend.app.intelligence.quality_gate import QualityGateEngine, QualityGateDecision
from backend.app.api_services import public_get_sheets, public_get_job_leads


@pytest.fixture
def clean_db():
    db = SessionLocal()
    yield db
    db.close()


def test_entity_verifier_accepts_business_without_osm_contact_data():
    """
    Verifies that when an OSM candidate lacks phone/email initially,
    strong title and domain name match enables official website acceptance.
    """
    verifier = WebsiteEntityVerifier()
    candidate = CandidateURL(
        url="https://twickenhamgreenplumbing.co.uk",
        domain="twickenhamgreenplumbing.co.uk",
        discovery_source="ZERO_BUDGET_SEARCH_DDG",
        rank=1,
    )
    
    mock_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Twickenham Green Plumbing & Heating - Trusted Local Engineers</title>
    </head>
    <body>
        <h1>Twickenham Green Plumbing & Heating</h1>
        <p>Serving Twickenham, Richmond, and Southwest London.</p>
        <a href="tel:02089393730">Call 020 8939 3730</a>
        <a href="mailto:info@twickenhamgreenplumbing.co.uk">Email Us</a>
    </body>
    </html>
    """
    
    with patch.object(verifier, "fetch_page_html", return_value=(200, "https://twickenhamgreenplumbing.co.uk", mock_html)):
        res = verifier.verify_candidate(
            candidate=candidate,
            business_name="Twickenham Green Plumbing & Heating",
            phone=None,
            email=None,
            city="Twickenham",
        )
        
        assert res.decision == VerificationDecision.ACCEPT
        assert res.verified_url == "https://twickenhamgreenplumbing.co.uk"
        assert res.signals.get("domain_token_matched") is True
        assert res.signals.get("title_matched") is True


def test_deep_crawler_extracts_contacts_from_subpages_and_links():
    """
    Verifies that the crawler discovers subpages (/contact-us) and parses
    tel:, mailto:, wa.me, social links, and Schema.org addresses.
    """
    enricher = ProductionWebsiteEnricher()
    
    hp_html = """
    <html>
    <head><title>Twickenham Green Plumbing & Heating</title></head>
    <body>
        <a href="/contact-us">Contact Us</a>
        <a href="https://instagram.com/twickenhamplumbing">Instagram</a>
        <a href="https://facebook.com/twickenhamplumbing">Facebook</a>
    </body>
    </html>
    """
    
    contact_html = """
    <html>
    <head><title>Contact Twickenham Green Plumbing</title></head>
    <body>
        <a href="tel:+442089393730">Call 020 8939 3730</a>
        <a href="mailto:info@twickenhamgreenplumbing.co.uk">info@twickenhamgreenplumbing.co.uk</a>
        <a href="https://wa.me/442089393730">WhatsApp Chat</a>
    </body>
    </html>
    """
    
    def mock_fetch(url: str):
        if "contact" in url:
            return PageFetchResult(url=url, status_code=200, html=contact_html, response_time_ms=50.0, content_type="text/html")
        return PageFetchResult(url=url, status_code=200, html=hp_html, response_time_ms=45.0, content_type="text/html")
        
    with patch.object(enricher, "_fetch_page", side_effect=mock_fetch):
        res = enricher.enrich_website("https://twickenhamgreenplumbing.co.uk")
        
        assert len(res.contacts.phones) >= 1
        assert "+442089393730" in [p["phone"] for p in res.contacts.phones]
        assert len(res.contacts.emails) >= 1
        assert "info@twickenhamgreenplumbing.co.uk" in [e["email"] for e in res.contacts.emails]
        assert len(res.contacts.whatsapp_links) >= 1
        assert "https://wa.me/442089393730" in res.contacts.whatsapp_links
        assert "instagram" in res.social_profiles
        assert "facebook" in res.social_profiles


def test_full_pipeline_real_business_end_to_end(clean_db):
    """
    Full End-to-End Test:
    Simulates raw candidate with name only -> website discovery -> deep crawling ->
    Quality Gate -> Lead promotion -> Evidence persistence -> API serialization.
    """
    ws = Workspace(id=uuid.uuid4(), name="Test Workspace")
    clean_db.add(ws)
    clean_db.commit()
    clean_db.refresh(ws)

    job = ScrapeJob(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        niche="Plumber",
        country="United Kingdom",
        state="London",
        region="Twickenham",
        target_lead_count=5,
        sources=["osm_overpass"],
        enrichments=["email", "website", "phone"],
        service="website_dev",
        status="RUNNING",
    )
    clean_db.add(job)
    clean_db.commit()
    clean_db.refresh(job)

    # Raw candidate from OSM has no website and no phone
    raw_cand = NormalizedLeadRecord(
        source="osm_overpass",
        source_id=f"node/twickenham_plumbing_{uuid.uuid4().hex[:8]}",
        business_name=f"Twickenham Green Plumbing & Heating {uuid.uuid4().hex[:4]}",
        category="plumber",
        address="10 Green St, Twickenham",
        city="Twickenham",
        state="London",
        country="United Kingdom",
        phone=None,
        website=None,
        email=None,
        raw_data={"tags": {"amenity": "plumber", "name": "Twickenham Green Plumbing & Heating"}},
    )

    mock_connector = MagicMock()
    mock_connector.search_leads.return_value = [raw_cand]
    mock_connector.supports_category.return_value = True

    # Mock zero-budget website discovery returning official domain
    mock_disc_cands = [
        CandidateURL(
            url="https://twickenhamgreenplumbing.co.uk",
            domain="twickenhamgreenplumbing.co.uk",
            discovery_source="ZERO_BUDGET_SEARCH_DDG",
            rank=1,
        )
    ]
    
    mock_hp_html = """
    <html>
    <head><title>Twickenham Green Plumbing & Heating</title></head>
    <body>
        <a href="/contact">Contact</a>
        <a href="https://instagram.com/twickenhamplumbing">Instagram</a>
    </body>
    </html>
    """
    mock_contact_html = """
    <html>
    <head><title>Contact Twickenham Green Plumbing</title></head>
    <body>
        <a href="tel:+442089393730">020 8939 3730</a>
        <a href="mailto:info@twickenhamgreenplumbing.co.uk">info@twickenhamgreenplumbing.co.uk</a>
        <a href="https://wa.me/442089393730">WhatsApp</a>
    </body>
    </html>
    """

    def mock_fetch(url: str):
        if "contact" in url:
            return PageFetchResult(url=url, status_code=200, html=mock_contact_html, response_time_ms=50.0, content_type="text/html")
        return PageFetchResult(url=url, status_code=200, html=mock_hp_html, response_time_ms=45.0, content_type="text/html")

    plan = {
        "source": "osm_overpass",
        "query": "plumber",
        "reason": "niche search",
        "location": "Twickenham, London, UK",
    }

    with patch("backend.app.worker.get_connectors", return_value={"osm_overpass": mock_connector}):
        with patch.object(ZeroBudgetDiscoveryEngine, "discover_from_zero_budget_search", return_value=mock_disc_cands):
            with patch.object(WebsiteEntityVerifier, "fetch_page_html", return_value=(200, "https://twickenhamgreenplumbing.co.uk", mock_hp_html)):
                with patch.object(ProductionWebsiteEnricher, "_fetch_page", side_effect=mock_fetch):
                    execute_single_query_plan(clean_db, job, plan)
                    finalize_job_status(clean_db, job, str(job.id))

    clean_db.refresh(job)
    assert job.leads_scraped == 1
    assert job.valid_count == 1

    # Verify persisted Lead in DB
    lead = clean_db.scalar(select(Lead).where(Lead.job_id == job.id))
    assert lead is not None
    assert lead.business_name.startswith("Twickenham Green Plumbing & Heating")
    assert lead.website == "https://twickenhamgreenplumbing.co.uk"
    assert lead.phone == "+442089393730"
    assert lead.email == "info@twickenhamgreenplumbing.co.uk"
    assert lead.verification_status == "VERIFIED"

    # Verify EvidenceRecords
    ev_records = clean_db.scalars(select(EvidenceRecord).where(EvidenceRecord.lead_id == lead.id)).all()
    ev_fields = {e.field_name for e in ev_records}
    assert "website" in ev_fields
    assert "contacts" in ev_fields
    assert "social_profiles" in ev_fields
    assert "lead_intelligence" in ev_fields

    # Verify API serialization
    api_leads = public_get_job_leads(str(job.id))
    assert len(api_leads) == 1
    serialized = api_leads[0]
    assert serialized["businessName"].startswith("Twickenham Green Plumbing & Heating")
    assert serialized["websiteUrl"] == "https://twickenhamgreenplumbing.co.uk"
    assert serialized["contactPhone"] == "+442089393730"
    assert serialized["contactEmail"] == "info@twickenhamgreenplumbing.co.uk"
    assert serialized["instagramHandle"] == "https://instagram.com/twickenhamplumbing"
    assert serialized["whatsappLink"] == "https://wa.me/442089393730"
    assert serialized["priorityScore"] is not None
