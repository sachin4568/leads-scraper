from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.enrichment.website_enricher import (
    PageFetchResult,
    ProductionWebsiteEnricher,
)
from backend.app.models import EvidenceRecord, Lead, ScrapeJob, Workspace
from backend.app.models_phase2 import Base as Phase2Base, CanonicalLead
from backend.app.sources.base import NormalizedLeadRecord
from backend.app.worker import execute_single_query_plan, finalize_job_status


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Phase2Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    ws = Workspace(name="Test Enrichment Workspace")
    session.add(ws)
    session.commit()
    session.refresh(ws)
    yield session, ws
    session.close()


def test_homepage_and_contact_page_extraction():
    """Verifies multi-page extraction of contacts, SEO, social, and WhatsApp links."""
    enricher = ProductionWebsiteEnricher()

    homepage_html = """
    <!DOCTYPE html>
    <html>
      <head>
        <title>Gourmet Bistro - Best Fine Dining</title>
        <meta name="description" content="Welcome to Gourmet Bistro in downtown with Michelin experience.">
        <link rel="canonical" href="https://gourmetbistro.com/">
        <meta property="og:title" content="Gourmet Bistro Official">
        <meta property="og:image" content="https://gourmetbistro.com/banner.jpg">
      </head>
      <body>
        <h1>Gourmet Bistro Experience</h1>
        <h2>Our Story</h2>
        <a href="/contact">Contact Us</a>
        <a href="https://instagram.com/gourmetbistro">Instagram</a>
        <a href="https://facebook.com/gourmetbistroo">Facebook</a>
      </body>
    </html>
    """

    contact_page_html = """
    <html>
      <body>
        <h1>Get in Touch</h1>
        <p>Email: <a href="mailto:info@gourmetbistro.com">info@gourmetbistro.com</a></p>
        <p>Call us: <a href="tel:+919820112233">+91 9820112233</a></p>
        <p>Chat on <a href="https://wa.me/919820112233">WhatsApp Direct</a></p>
        <div class="address">123 Culinary Road, Mumbai 400001, India</div>
      </body>
    </html>
    """

    def mock_fetch(url: str):
        if "/contact" in url:
            return PageFetchResult(
                url=url, status_code=200, html=contact_page_html,
                response_time_ms=120.0, content_type="text/html"
            )
        return PageFetchResult(
            url=url, status_code=200, html=homepage_html,
            response_time_ms=150.0, content_type="text/html"
        )

    with patch.object(enricher, "_fetch_page", side_effect=mock_fetch):
        res = enricher.enrich_website("https://gourmetbistro.com")

        # Health
        assert res.health.is_reachable is True
        assert res.health.http_status == 200
        assert res.health.is_https is True
        assert res.health.pages_fetched_count == 2

        # SEO
        assert res.seo.title == "Gourmet Bistro - Best Fine Dining"
        assert res.seo.canonical_url == "https://gourmetbistro.com/"
        assert res.seo.og_title == "Gourmet Bistro Official"
        assert "Gourmet Bistro Experience" in res.seo.h1_tags

        # Contacts
        assert any(e["email"] == "info@gourmetbistro.com" for e in res.contacts.emails)
        assert any("+919820112233" in p["phone"] for p in res.contacts.phones)
        assert any("wa.me" in w for w in res.contacts.whatsapp_links)

        # Social
        assert "instagram" in res.social_profiles
        assert "facebook" in res.social_profiles


def test_schema_org_json_ld_extraction():
    """Verifies structured extraction from Schema.org LocalBusiness / Restaurant JSON-LD."""
    enricher = ProductionWebsiteEnricher()

    schema_html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Restaurant",
          "name": "Spice Pavilion",
          "description": "Authentic Mughlai and North Indian cuisine.",
          "servesCuisine": "Indian, Mughlai",
          "telephone": "+91 22 2673 4455",
          "openingHours": ["Mo-Su 12:00-23:30"],
          "address": {
            "@type": "PostalAddress",
            "streetAddress": "Plot 42, Link Road",
            "addressLocality": "Andheri West",
            "addressRegion": "Mumbai",
            "postalCode": "400053",
            "addressCountry": "India"
          }
        }
        </script>
      </head>
      <body>
        <h1>Spice Pavilion</h1>
      </body>
    </html>
    """

    with patch.object(enricher, "_fetch_page", return_value=PageFetchResult(
        url="https://spicepavilion.in", status_code=200, html=schema_html,
        response_time_ms=100.0, content_type="text/html"
    )):
        res = enricher.enrich_website("https://spicepavilion.in")
        assert "Restaurant" in res.business_info.schema_types
        assert res.business_info.business_name == "Spice Pavilion"
        assert res.business_info.category == "Indian, Mughlai"
        assert "Mo-Su 12:00-23:30" in res.business_info.opening_hours
        assert any("Plot 42, Link Road" in a["address"] for a in res.contacts.addresses)


def test_technology_detection():
    """Verifies deterministic technology detection for CMS, analytics, pixels, and frameworks."""
    enricher = ProductionWebsiteEnricher()

    tech_html = """
    <html>
      <head>
        <meta name="generator" content="WordPress 6.4.2" />
        <script src="https://www.googletagmanager.com/gtm.js?id=GTM-XXXX"></script>
        <script>
          !function(f,b,e,v,n,t,s)
          {if(f.fbq)return;n=f.fbq=function(){n.callMethod?
          n.callMethod.apply(n,arguments):n.queue.push(arguments)};
          if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
          n.queue=[];t=b.createElement(e);t.async=!0;
          t.src=v;s=b.getElementsByTagName(e)[0];
          s.parentNode.insertBefore(t,s)}(window, document,'script',
          'https://connect.facebook.net/en_US/fbevents.js');
          fbq('init', '1234567890');
        </script>
      </head>
      <body>
        <div class="woocommerce-products">Products</div>
      </body>
    </html>
    """

    with patch.object(enricher, "_fetch_page", return_value=PageFetchResult(
        url="https://wpshop.com", status_code=200, html=tech_html,
        response_time_ms=90.0, content_type="text/html"
    )):
        res = enricher.enrich_website("https://wpshop.com")
        assert "WordPress" in res.technologies
        assert "WooCommerce" in res.technologies
        assert "Google Tag Manager" in res.technologies
        assert "Meta Pixel" in res.technologies


def test_conflict_preservation_without_overwriting_provider_data():
    """Verifies that conflicts between provider ground truth and website are recorded as evidence."""
    enricher = ProductionWebsiteEnricher()

    conflict_html = """
    <html>
      <body>
        <a href="tel:+918888888888">+91 8888888888</a>
        <a href="mailto:newcontact@restaurant.com">newcontact@restaurant.com</a>
      </body>
    </html>
    """

    with patch.object(enricher, "_fetch_page", return_value=PageFetchResult(
        url="https://restaurant.com", status_code=200, html=conflict_html,
        response_time_ms=80.0, content_type="text/html"
    )):
        res = enricher.enrich_website(
            target_url="https://restaurant.com",
            provider_phone="+91 9999999999",  # OSM Phone
            provider_email="oldosm@restaurant.com",  # OSM Email
        )

        assert "phone" in res.conflicts
        assert res.conflicts["phone"]["provider_value"] == "+91 9999999999"
        assert "+918888888888" in res.conflicts["phone"]["website_values"]

        assert "email" in res.conflicts
        assert res.conflicts["email"]["provider_value"] == "oldosm@restaurant.com"
        assert "newcontact@restaurant.com" in res.conflicts["email"]["website_values"]


def test_idempotency_and_caching():
    """Verifies that enrichment caching prevents duplicate fetches for the same domain."""
    enricher = ProductionWebsiteEnricher()

    mock_fetch = MagicMock(return_value=PageFetchResult(
        url="https://cachedsite.com", status_code=200, html="<html><title>Cached</title></html>",
        response_time_ms=50.0, content_type="text/html"
    ))

    with patch.object(enricher, "_fetch_page", mock_fetch):
        res1 = enricher.enrich_website("https://cachedsite.com")
        res2 = enricher.enrich_website("https://cachedsite.com")

        # Fetched exactly once
        assert mock_fetch.call_count == 1
        assert res1.domain == res2.domain


def test_website_failures_isolated(test_db):
    """Verifies that HTTP 403, 404, 500, or timeout during enrichment never invalidates the core lead."""
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
            source_id="node/err_500_lead",
            business_name="500 Server Error Cafe",
            website="https://error500cafe.com",
            phone="+91 9820001122",
            category="cafe",
            address="Mumbai",
            raw_data={"tags": {"name": "500 Server Error Cafe", "website": "https://error500cafe.com"}},
        )
    ]

    mock_connector = MagicMock()
    mock_connector.search_leads.return_value = fake_records
    mock_connector.supports_category.return_value = True

    plan = {"source": "osm_overpass", "query": "cafe", "reason": "test", "location": "Mumbai"}

    with patch("backend.app.worker.get_connectors", return_value={"osm_overpass": mock_connector}), \
         patch("backend.app.enrichment.website_enricher.ProductionWebsiteEnricher._fetch_page", return_value=PageFetchResult(
             url="https://error500cafe.com", status_code=500, html="", response_time_ms=300.0,
             content_type="text/html", error="Internal Server Error"
         )):

        execute_single_query_plan(session, job, plan)
        finalize_job_status(session, job, str(job.id))

    # Core lead MUST remain persisted and intact
    lead = session.scalars(select(Lead).where(Lead.job_id == job.id)).first()
    assert lead is not None
    assert lead.business_name == "500 Server Error Cafe"
    assert lead.website == "https://error500cafe.com"
    assert job.leads_scraped == 1
    assert job.status in ("COMPLETED", "REGION_EXHAUSTED")


def test_ssrf_blocked_in_enrichment():
    """Verifies that internal network IP addresses are rejected before outbound request."""
    enricher = ProductionWebsiteEnricher()
    for bad_url in ["http://127.0.0.1:8080", "http://169.254.169.254/latest/meta-data", "http://10.0.0.1"]:
        res = enricher._fetch_page(bad_url)
        assert res.status_code is None
        assert "SSRF blocked" in str(res.error)


def test_enrichment_off_contract(test_db):
    """Verifies that when enrichments = [], zero website fetches take place."""
    session, ws = test_db

    job = ScrapeJob(
        workspace_id=ws.id,
        niche="restaurant",
        country="India",
        state="Mumbai",
        target_lead_count=5,
        sources=["osm_overpass"],
        enrichments=[],  # ENRICHMENT OFF
        status="RUNNING",
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    fake_records = [
        NormalizedLeadRecord(
            source="osm_overpass",
            source_id="node/off_lead",
            business_name="Enrichment Off Cafe",
            website="https://enrichmentoff.com",
            phone="+91 9820000000",
            category="cafe",
            address="Mumbai",
            raw_data={"tags": {"name": "Enrichment Off Cafe", "website": "https://enrichmentoff.com"}},
        )
    ]

    mock_connector = MagicMock()
    mock_connector.search_leads.return_value = fake_records
    mock_connector.supports_category.return_value = True

    plan = {"source": "osm_overpass", "query": "cafe", "reason": "test", "location": "Mumbai"}

    with patch("backend.app.worker.get_connectors", return_value={"osm_overpass": mock_connector}), \
         patch("backend.app.enrichment.website_enricher.ProductionWebsiteEnricher.enrich_website") as mock_enrich:

        execute_single_query_plan(session, job, plan)
        finalize_job_status(session, job, str(job.id))

    # Enricher MUST NOT be invoked
    assert mock_enrich.call_count == 0
    lead = session.scalars(select(Lead).where(Lead.job_id == job.id)).first()
    assert lead.website == "https://enrichmentoff.com"
