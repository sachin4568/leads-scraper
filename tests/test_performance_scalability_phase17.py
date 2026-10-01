from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker

from backend.app.api import current_workspace_id
from backend.app.database import Base, get_db
from backend.app.enrichment.website_enricher import (
    EnrichedWebsiteResult,
    ProductionWebsiteEnricher,
    WebsiteHealth,
)
from backend.app.main import app
from backend.app.models import Deal, EvidenceRecord, Lead, LeadAction, ScrapeJob, Workspace
from backend.app.models_phase2 import Base as Phase2Base
from backend.app.models_services import Base as ServicesBase


@pytest.fixture
def db_session():
    """Isolated in-memory SQLite database session for performance and scalability tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    Phase2Base.metadata.create_all(bind=engine)
    ServicesBase.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_composite_indexes_present_and_optimized():
    """Verifies that composite indexes are properly configured on core tables."""
    lead_indexes = {idx.name for idx in Lead.__table__.indexes}
    assert "ix_leads_ws_deleted_created" in lead_indexes
    assert "ix_leads_ws_status" in lead_indexes

    evidence_indexes = {idx.name for idx in EvidenceRecord.__table__.indexes}
    assert "ix_evidence_ws_lead_field" in evidence_indexes

    action_indexes = {idx.name for idx in LeadAction.__table__.indexes}
    assert "ix_actions_ws_lead_created" in action_indexes

    deal_indexes = {idx.name for idx in Deal.__table__.indexes}
    assert "ix_deals_ws_stage" in deal_indexes
    assert "ix_deals_ws_lead" in deal_indexes

    job_indexes = {idx.name for idx in ScrapeJob.__table__.indexes}
    assert "ix_scrape_jobs_ws_status" in job_indexes


def test_large_scale_pagination_latency(db_session: Session):
    """Benchmarks paginated lead listing over 1,000 records."""
    ws = Workspace(name="Scale Benchmark Workspace")
    db_session.add(ws)
    db_session.commit()
    db_session.refresh(ws)

    now = datetime.now(UTC)
    batch_leads = [
        Lead(
            workspace_id=ws.id,
            business_name=f"Scale Clinic {i}",
            phone=f"+91 98000 {i:05d}",
            email=f"clinic_{i}@benchmark.com",
            website=f"https://clinic{i}.com" if i % 2 == 0 else None,
            genuineness_score=0.85,
            workflow_status="QUALIFIED" if i % 3 == 0 else "NEW",
            created_at=now - timedelta(minutes=i),
        )
        for i in range(1000)
    ]
    db_session.bulk_save_objects(batch_leads)
    db_session.commit()

    app.dependency_overrides[current_workspace_id] = lambda: ws.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    # Warmup request
    _ = client.get("/api/operations/leads?page=1&page_size=1")

    # Page 1 fetch
    t0 = time.perf_counter()
    res1 = client.get("/api/operations/leads?page=1&page_size=50")
    lat1_ms = (time.perf_counter() - t0) * 1000.0
    assert res1.status_code == 200
    assert res1.json()["total"] == 1000
    assert len(res1.json()["results"]) == 50
    assert lat1_ms < 500.0  # sub-500ms in SQLite in-memory test under full suite load

    # Page 10 fetch
    t0 = time.perf_counter()
    res10 = client.get("/api/operations/leads?page=10&page_size=50")
    lat10_ms = (time.perf_counter() - t0) * 1000.0
    assert res10.status_code == 200
    assert len(res10.json()["results"]) == 50
    assert lat10_ms < 500.0


def test_analytics_aggregation_at_scale(db_session: Session):
    """Benchmarks executive analytics computation over 500 leads with evidence, actions, and deals."""
    ws = Workspace(name="Analytics Scale Workspace")
    db_session.add(ws)
    db_session.commit()
    db_session.refresh(ws)

    now = datetime.now(UTC)
    leads = []
    for i in range(500):
        l = Lead(
            workspace_id=ws.id,
            business_name=f"Hospital Scale {i}",
            phone=f"+91 99000 {i:05d}",
            email=f"hosp_{i}@scale.in",
            website=f"https://hospital{i}.in" if i % 2 == 0 else None,
            genuineness_score=0.90,
            workflow_status="CONVERTED" if i % 10 == 0 else ("QUALIFIED" if i % 5 == 0 else "NEW"),
            created_at=now - timedelta(days=i % 30),
        )
        leads.append(l)

    db_session.add_all(leads)
    db_session.commit()

    # Seed deals
    deals = []
    for i in range(0, 500, 10):
        d = Deal(
            workspace_id=ws.id,
            lead_id=leads[i].id,
            title=f"Deal Scale {i}",
            service_type="WEBSITE_DEVELOPMENT" if i % 20 == 0 else "SEO",
            deal_value=60000.0,
            stage="WON" if i % 20 == 0 else "PROPOSAL",
            probability=1.0 if i % 20 == 0 else 0.6,
        )
        deals.append(d)

    db_session.add_all(deals)
    db_session.commit()

    app.dependency_overrides[current_workspace_id] = lambda: ws.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    # Warmup
    _ = client.get("/api/analytics/overview?timeframe=all_time")

    t0 = time.perf_counter()
    res = client.get("/api/analytics/overview?timeframe=30d")
    lat_ms = (time.perf_counter() - t0) * 1000.0
    assert res.status_code == 200
    data = res.json()

    assert data["kpis"]["total_leads"] == 500
    assert data["kpis"]["won_revenue"] > 0
    assert lat_ms < 250.0


def test_domain_cache_hit_performance():
    """Verifies that ProductionWebsiteEnricher caching avoids redundant fetches and resolves instantly."""
    from backend.app.enrichment.website_enricher import (
        ExtractedBusinessInfo,
        ExtractedContacts,
        ExtractedSEOInfo,
    )

    enricher = ProductionWebsiteEnricher()
    mock_domain = "fastclinic-scale-benchmark.com"

    mock_result = EnrichedWebsiteResult(
        domain=mock_domain,
        target_url=f"https://{mock_domain}",
        health=WebsiteHealth(is_reachable=True, http_status=200, is_https=True, final_url=f"https://{mock_domain}"),
        contacts=ExtractedContacts(),
        business_info=ExtractedBusinessInfo(),
        seo=ExtractedSEOInfo(),
    )

    # Populate cache
    enricher._cache[mock_domain] = mock_result

    t0 = time.perf_counter()
    res = enricher.enrich_website(f"https://{mock_domain}")
    lat_us = (time.perf_counter() - t0) * 1_000_000.0

    assert res.domain == mock_domain
    assert lat_us < 1000.0  # Sub-1 millisecond memory lookup
