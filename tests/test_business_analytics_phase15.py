from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker

from backend.app.api import current_workspace_id
from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import Deal, EvidenceRecord, Lead, LeadAction, Workspace
from backend.app.models_phase2 import Base as Phase2Base
from backend.app.models_services import Base as ServicesBase


@pytest.fixture
def db_session():
    """Isolated in-memory SQLite database session."""
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


@pytest.fixture
def phase15_setup(db_session: Session):
    """Seed test workspace with diverse leads across quality tiers, sources, and CRM outcomes."""
    workspace = Workspace(name="Phase 15 Executive Analytics Workspace")
    db_session.add(workspace)
    db_session.commit()
    db_session.refresh(workspace)

    now = datetime.now(UTC)

    # Lead 1: VERY_HIGH tier, Discovered via OSM, Website verified, Won Deal ₹80,000
    lead1 = Lead(
        workspace_id=workspace.id,
        business_name="Imperial Dental Care",
        phone="+91 98200 11111",
        email="info@imperialdental.in",
        website="https://imperialdental.in",
        genuineness_score=0.98,
        workflow_status="CONVERTED",
        created_at=now - timedelta(days=2),
    )
    # Lead 2: HIGH tier, Discovered via OSM, Negotiation Deal ₹45,000 (prob 80%)
    lead2 = Lead(
        workspace_id=workspace.id,
        business_name="Sunrise Eye & Laser",
        phone="+91 98200 22222",
        email="contact@sunriselaser.com",
        website="http://sunriselaser.com",
        genuineness_score=0.88,
        workflow_status="QUALIFIED",
        created_at=now - timedelta(days=5),
    )
    # Lead 3: MEDIUM tier, Discovered via OSM, Contacted, Lost Deal ₹25,000
    lead3 = Lead(
        workspace_id=workspace.id,
        business_name="Metro Physiotherapy",
        phone="+91 98200 33333",
        email=None,
        website=None,
        genuineness_score=0.75,
        workflow_status="LOST",
        created_at=now - timedelta(days=10),
    )
    # Lead 4: LOW tier, Uncontactable, Created 45 days ago
    lead4 = Lead(
        workspace_id=workspace.id,
        business_name="Ghost Clinic",
        phone=None,
        email=None,
        website=None,
        genuineness_score=0.40,
        workflow_status="NEW",
        created_at=now - timedelta(days=45),
    )

    db_session.add_all([lead1, lead2, lead3, lead4])
    db_session.commit()
    for l in [lead1, lead2, lead3, lead4]:
        db_session.refresh(l)

    # Add evidence records
    db_session.add(
        EvidenceRecord(
            workspace_id=workspace.id,
            lead_id=lead1.id,
            field_name="lead_intelligence",
            status="VERY_HIGH",
            confidence_score=95,
            source="LEAD_INTELLIGENCE_ENGINE",
            details={"overall_opportunity_score": 92, "opportunity_category": "VERY_HIGH", "top_reasons": ["Web modernization pitch"]},
        )
    )
    db_session.add(
        EvidenceRecord(
            workspace_id=workspace.id,
            lead_id=lead1.id,
            field_name="website",
            status="ACCEPT",
            confidence_score=98,
            source="ZERO_BUDGET_VERIFIED",
            details={"verified_url": "https://imperialdental.in"},
        )
    )
    db_session.add(
        EvidenceRecord(
            workspace_id=workspace.id,
            lead_id=lead1.id,
            field_name="contacts",
            status="ACCEPT",
            confidence_score=95,
            source="WEBSITE_ENRICHMENT",
            details={"whatsapp_links": ["https://wa.me/919820011111"]},
        )
    )

    db_session.add(
        EvidenceRecord(
            workspace_id=workspace.id,
            lead_id=lead2.id,
            field_name="lead_intelligence",
            status="HIGH",
            confidence_score=85,
            source="LEAD_INTELLIGENCE_ENGINE",
            details={"overall_opportunity_score": 75, "opportunity_category": "HIGH", "top_reasons": ["SEO gap identified"]},
        )
    )

    db_session.add(
        EvidenceRecord(
            workspace_id=workspace.id,
            lead_id=lead3.id,
            field_name="lead_intelligence",
            status="MEDIUM",
            confidence_score=70,
            source="LEAD_INTELLIGENCE_ENGINE",
            details={"overall_opportunity_score": 55, "opportunity_category": "MEDIUM", "top_reasons": ["No web presence"]},
        )
    )

    db_session.add(
        EvidenceRecord(
            workspace_id=workspace.id,
            lead_id=lead4.id,
            field_name="lead_intelligence",
            status="LOW",
            confidence_score=40,
            source="LEAD_INTELLIGENCE_ENGINE",
            details={"overall_opportunity_score": 30, "opportunity_category": "LOW", "top_reasons": ["Minimal data"]},
        )
    )

    # Seed outreach actions
    db_session.add(
        LeadAction(
            workspace_id=workspace.id,
            lead_id=lead1.id,
            channel="WHATSAPP",
            outcome="CONVERTED",
            notes="Closed modernization agreement.",
            created_at=now - timedelta(days=1),
        )
    )
    db_session.add(
        LeadAction(
            workspace_id=workspace.id,
            lead_id=lead2.id,
            channel="PHONE",
            outcome="MEETING_BOOKED",
            notes="Consultation meeting scheduled.",
            created_at=now - timedelta(days=3),
        )
    )
    db_session.add(
        LeadAction(
            workspace_id=workspace.id,
            lead_id=lead3.id,
            channel="PHONE",
            outcome="NOT_INTERESTED",
            notes="Owner passed on services.",
            created_at=now - timedelta(days=8),
        )
    )

    # Seed deals
    db_session.add(
        Deal(
            workspace_id=workspace.id,
            lead_id=lead1.id,
            title="Imperial Dental - Modernization",
            service_type="WEBSITE_DEVELOPMENT",
            deal_value=80000.0,
            stage="WON",
            probability=1.0,
            created_at=now - timedelta(days=2),
            closed_at=now - timedelta(days=1),
        )
    )
    db_session.add(
        Deal(
            workspace_id=workspace.id,
            lead_id=lead2.id,
            title="Sunrise Eye - SEO Retainer",
            service_type="SEO",
            deal_value=45000.0,
            stage="NEGOTIATION",
            probability=0.80,
            created_at=now - timedelta(days=4),
        )
    )
    db_session.add(
        Deal(
            workspace_id=workspace.id,
            lead_id=lead3.id,
            title="Metro Physio - SMMA",
            service_type="SMMA",
            deal_value=25000.0,
            stage="LOST",
            probability=0.0,
            win_loss_reason="Budget constraint",
            created_at=now - timedelta(days=9),
            closed_at=now - timedelta(days=8),
        )
    )

    db_session.commit()
    return {"workspace": workspace, "leads": [lead1, lead2, lead3, lead4]}


def test_analytics_overview_kpis_and_funnel(db_session: Session, phase15_setup: dict):
    """Verifies executive KPI cards and complete funnel stages."""
    workspace = phase15_setup["workspace"]

    app.dependency_overrides[current_workspace_id] = lambda: workspace.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    res = client.get("/api/analytics/overview?timeframe=all_time")
    assert res.status_code == 200
    data = res.json()

    kpis = data["kpis"]
    assert kpis["total_leads"] == 4
    assert kpis["contactable_leads"] == 3
    assert kpis["qualified_leads"] == 3
    assert kpis["won_leads"] == 1
    assert kpis["won_revenue"] == 80000.0
    assert kpis["total_pipeline_value"] == 45000.0
    assert kpis["weighted_pipeline_value"] == 36000.0
    assert kpis["lost_value"] == 25000.0
    assert kpis["overall_conversion_rate"] == 25.0  # 1 won / 4 total
    assert kpis["win_rate"] == 50.0  # 1 won / 2 closed

    # Verify Funnel
    funnel = {f["stage"]: f["count"] for f in data["funnel"]}
    assert funnel["Leads Discovered"] == 4
    assert funnel["Contactable"] == 3
    assert funnel["Contacted"] == 3
    assert funnel["Qualified"] == 3
    assert funnel["Won"] == 1


def test_quality_tier_outcome_correlation(db_session: Session, phase15_setup: dict):
    """Verifies correlation between Phase 9 quality tiers and actual sales outcomes."""
    workspace = phase15_setup["workspace"]

    app.dependency_overrides[current_workspace_id] = lambda: workspace.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    res = client.get("/api/analytics/quality?timeframe=all_time")
    assert res.status_code == 200
    tiers = {t["tier"]: t for t in res.json()}

    assert "VERY_HIGH" in tiers
    assert tiers["VERY_HIGH"]["leads_count"] == 1
    assert tiers["VERY_HIGH"]["won_count"] == 1
    assert tiers["VERY_HIGH"]["won_pct"] == 100.0
    assert tiers["VERY_HIGH"]["won_revenue"] == 80000.0

    assert "HIGH" in tiers
    assert tiers["HIGH"]["qualified_pct"] == 100.0
    assert tiers["HIGH"]["won_count"] == 0

    assert "LOW" in tiers
    assert tiers["LOW"]["leads_count"] == 1
    assert tiers["LOW"]["contactable_pct"] == 0.0
    assert tiers["LOW"]["won_revenue"] == 0.0


def test_source_performance_attribution(db_session: Session, phase15_setup: dict):
    """Verifies revenue attribution and conversion across acquisition sources."""
    workspace = phase15_setup["workspace"]

    app.dependency_overrides[current_workspace_id] = lambda: workspace.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    res = client.get("/api/analytics/sources?timeframe=all_time")
    assert res.status_code == 200
    sources = {s["source"]: s for s in res.json()}

    assert "ZERO BUDGET VERIFIED" in sources
    assert sources["ZERO BUDGET VERIFIED"]["won_revenue"] == 80000.0
    assert sources["ZERO BUDGET VERIFIED"]["won_pct"] == 100.0

    assert "OSM DISCOVERY" in sources
    assert sources["OSM DISCOVERY"]["leads_count"] >= 2


def test_service_performance_breakdown(db_session: Session, phase15_setup: dict):
    """Verifies performance breakdown across service offerings."""
    workspace = phase15_setup["workspace"]

    app.dependency_overrides[current_workspace_id] = lambda: workspace.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    res = client.get("/api/analytics/services?timeframe=all_time")
    assert res.status_code == 200
    services = {s["service"]: s for s in res.json()}

    assert "WEBSITE DEVELOPMENT" in services
    assert services["WEBSITE DEVELOPMENT"]["won_revenue"] == 80000.0
    assert services["WEBSITE DEVELOPMENT"]["win_rate"] == 100.0

    assert "SEO" in services
    assert services["SEO"]["pipeline_value"] == 45000.0


def test_timeframe_date_filtering(db_session: Session, phase15_setup: dict):
    """Verifies that timeframe bounds filter metrics accurately."""
    workspace = phase15_setup["workspace"]

    app.dependency_overrides[current_workspace_id] = lambda: workspace.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    # 30-day window: includes leads 1, 2, 3 (not lead 4 which was 45 days ago)
    res_30d = client.get("/api/analytics/overview?timeframe=30d")
    assert res_30d.status_code == 200
    data_30d = res_30d.json()
    assert data_30d["kpis"]["total_leads"] == 3

    # All-time window: includes all 4 leads
    res_all = client.get("/api/analytics/overview?timeframe=all_time")
    assert res_all.status_code == 200
    assert res_all.json()["kpis"]["total_leads"] == 4


def test_zero_evidence_mutation_and_bounded_queries(db_session: Session, phase15_setup: dict):
    """Verifies analytics execution produces zero side effects and never mutates underlying records."""
    workspace = phase15_setup["workspace"]
    lead1 = phase15_setup["leads"][0]

    app.dependency_overrides[current_workspace_id] = lambda: workspace.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    client.get("/api/analytics/overview?timeframe=all_time")

    db_session.expire_all()
    reloaded = db_session.get(Lead, lead1.id)
    assert reloaded.business_name == "Imperial Dental Care"
    assert reloaded.phone == "+91 98200 11111"
    assert reloaded.email == "info@imperialdental.in"

    evs = db_session.query(EvidenceRecord).filter(EvidenceRecord.lead_id == lead1.id).all()
    assert len(evs) == 3
