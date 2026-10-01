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
def phase14_setup(db_session: Session):
    """Seed test workspace and leads for CRM pipeline testing."""
    workspace = Workspace(name="Phase 14 CRM Pipeline Workspace")
    db_session.add(workspace)
    db_session.commit()
    db_session.refresh(workspace)

    # Lead 1: Qualified lead for Web Development
    lead1 = Lead(
        workspace_id=workspace.id,
        business_name="Apex Dental Care",
        phone="+91 98200 11111",
        email="info@apexdental.in",
        website="https://apexdental.in",
        genuineness_score=0.95,
        workflow_status="QUALIFIED",
    )
    # Lead 2: Lead for SEO retainer
    lead2 = Lead(
        workspace_id=workspace.id,
        business_name="Radiant Smile Clinic",
        phone="+91 98200 22222",
        email="care@radiantsmile.in",
        website="http://radiantsmile.in",
        genuineness_score=0.90,
        workflow_status="QUALIFIED",
    )
    # Lead 3: Lead for Social Media Marketing
    lead3 = Lead(
        workspace_id=workspace.id,
        business_name="Metro Skin & Dental",
        phone="+91 98200 33333",
        email="contact@metroskin.in",
        website=None,
        genuineness_score=0.85,
        workflow_status="QUALIFIED",
    )

    db_session.add_all([lead1, lead2, lead3])
    db_session.commit()
    for l in [lead1, lead2, lead3]:
        db_session.refresh(l)

    # Seed evidence records
    db_session.add(
        EvidenceRecord(
            workspace_id=workspace.id,
            lead_id=lead1.id,
            field_name="lead_intelligence",
            status="VERY_HIGH",
            confidence_score=95,
            source="LEAD_INTELLIGENCE_ENGINE",
            details={"overall_opportunity_score": 88, "opportunity_category": "VERY_HIGH", "top_reasons": ["Ready for modernization"]},
        )
    )
    db_session.commit()

    return {"workspace": workspace, "leads": [lead1, lead2, lead3]}


def test_deal_creation_from_lead(db_session: Session, phase14_setup: dict):
    """Verifies creating a sales opportunity / deal attached to a lead with automated probability mapping."""
    workspace = phase14_setup["workspace"]
    lead = phase14_setup["leads"][0]

    app.dependency_overrides[current_workspace_id] = lambda: workspace.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    # 1. Create a Qualified Deal
    res = client.post(
        "/api/operations/deals",
        json={
            "lead_id": str(lead.id),
            "title": "Apex Dental - Web Modernization & Booking System",
            "service_type": "WEBSITE_DEVELOPMENT",
            "deal_value": 45000.0,
            "stage": "QUALIFIED",
            "notes": "Client requested full website rebuild with patient portal.",
        },
    )
    assert res.status_code == 201
    deal = res.json()
    assert deal["title"] == "Apex Dental - Web Modernization & Booking System"
    assert deal["deal_value"] == 45000.0
    assert deal["stage"] == "QUALIFIED"
    assert deal["probability"] == 0.40
    assert deal["weighted_value"] == 18000.0
    assert deal["business_name"] == "Apex Dental Care"


def test_deal_stage_transitions_and_win_loss(db_session: Session, phase14_setup: dict):
    """Verifies moving deal across stages (Proposal -> Negotiation -> Won/Lost) and syncing lead status."""
    workspace = phase14_setup["workspace"]
    lead = phase14_setup["leads"][0]

    app.dependency_overrides[current_workspace_id] = lambda: workspace.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    # 1. Create initial deal
    res1 = client.post(
        "/api/operations/deals",
        json={
            "lead_id": str(lead.id),
            "title": "Apex Dental - SEO Retainer",
            "service_type": "SEO",
            "deal_value": 25000.0,
            "stage": "PROPOSAL",
        },
    )
    assert res1.status_code == 201
    deal_id = res1.json()["id"]
    assert res1.json()["probability"] == 0.60
    assert res1.json()["weighted_value"] == 15000.0

    # 2. Advance to Negotiation (80%)
    res2 = client.patch(
        f"/api/operations/deals/{deal_id}",
        json={"stage": "NEGOTIATION"},
    )
    assert res2.status_code == 200
    assert res2.json()["stage"] == "NEGOTIATION"
    assert res2.json()["probability"] == 0.80
    assert res2.json()["weighted_value"] == 20000.0

    # 3. Mark Won (100%)
    res3 = client.patch(
        f"/api/operations/deals/{deal_id}",
        json={"stage": "WON", "win_loss_reason": "Contract signed and deposit received."},
    )
    assert res3.status_code == 200
    assert res3.json()["stage"] == "WON"
    assert res3.json()["probability"] == 1.00
    assert res3.json()["weighted_value"] == 25000.0
    assert res3.json()["closed_at"] is not None

    # Check lead converted automatically
    db_session.expire_all()
    reloaded_lead = db_session.get(Lead, lead.id)
    assert reloaded_lead.workflow_status == "CONVERTED"


def test_pipeline_revenue_and_weighted_forecasting(db_session: Session, phase14_setup: dict):
    """Verifies pipeline dashboard revenue metrics, stage distributions, and win rate calculation."""
    workspace = phase14_setup["workspace"]
    lead1 = phase14_setup["leads"][0]
    lead2 = phase14_setup["leads"][1]
    lead3 = phase14_setup["leads"][2]

    app.dependency_overrides[current_workspace_id] = lambda: workspace.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    # Deal 1: Won ₹50,000
    client.post(
        "/api/operations/deals",
        json={"lead_id": str(lead1.id), "title": "Apex Rebuild", "service_type": "WEBSITE_DEVELOPMENT", "deal_value": 50000.0, "stage": "WON"},
    )
    # Deal 2: Negotiation ₹30,000 (80% -> ₹24,000 weighted)
    client.post(
        "/api/operations/deals",
        json={"lead_id": str(lead2.id), "title": "Radiant SEO", "service_type": "SEO", "deal_value": 30000.0, "stage": "NEGOTIATION"},
    )
    # Deal 3: Lost ₹20,000
    client.post(
        "/api/operations/deals",
        json={"lead_id": str(lead3.id), "title": "Metro SMMA", "service_type": "SMMA", "deal_value": 20000.0, "stage": "LOST", "win_loss_reason": "No budget"},
    )

    # Fetch CRM Pipeline Dashboard
    res = client.get("/api/operations/crm/pipeline")
    assert res.status_code == 200
    pipe = res.json()

    assert pipe["won_revenue"] == 50000.0
    assert pipe["total_pipeline_value"] == 30000.0
    assert pipe["weighted_pipeline_value"] == 24000.0
    assert pipe["lost_value"] == 20000.0
    assert pipe["total_deals"] == 3
    assert pipe["active_deals_count"] == 1
    assert pipe["won_deals_count"] == 1
    assert pipe["lost_deals_count"] == 1
    assert pipe["win_rate"] == 50.0  # 1 won / (1 won + 1 lost) = 50%

    # Check stages breakdown
    stage_counts = {s["stage"]: s for s in pipe["stages"]}
    assert stage_counts["WON"]["count"] == 1
    assert stage_counts["WON"]["total_value"] == 50000.0
    assert stage_counts["NEGOTIATION"]["count"] == 1
    assert stage_counts["NEGOTIATION"]["total_value"] == 30000.0
    assert stage_counts["LOST"]["count"] == 1


def test_timeline_integration_with_deals(db_session: Session, phase14_setup: dict):
    """Verifies that deal creation and winning/closing events appear in the unified activity timeline."""
    workspace = phase14_setup["workspace"]
    lead = phase14_setup["leads"][0]

    app.dependency_overrides[current_workspace_id] = lambda: workspace.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    res_d = client.post(
        "/api/operations/deals",
        json={"lead_id": str(lead.id), "title": "Dental Web Retainer", "service_type": "WEBSITE_DEVELOPMENT", "deal_value": 40000.0, "stage": "WON"},
    )
    assert res_d.status_code == 201

    res_tl = client.get(f"/api/operations/leads/{lead.id}/timeline")
    assert res_tl.status_code == 200
    timeline = res_tl.json()

    event_titles = [e["title"] for e in timeline["events"]]
    assert any("Deal Won: Dental Web Retainer" in t for t in event_titles)


def test_source_evidence_immutability(db_session: Session, phase14_setup: dict):
    """Verifies that creating and closing CRM deals never mutates raw OSM tags or EvidenceRecords."""
    workspace = phase14_setup["workspace"]
    lead = phase14_setup["leads"][0]

    app.dependency_overrides[current_workspace_id] = lambda: workspace.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    client.post(
        "/api/operations/deals",
        json={"lead_id": str(lead.id), "title": "Apex Retainer", "service_type": "SEO", "deal_value": 60000.0, "stage": "WON"},
    )

    db_session.expire_all()
    reloaded = db_session.get(Lead, lead.id)
    assert reloaded.business_name == "Apex Dental Care"
    assert reloaded.phone == "+91 98200 11111"
    assert reloaded.email == "info@apexdental.in"

    evs = db_session.query(EvidenceRecord).filter(EvidenceRecord.lead_id == lead.id).all()
    assert len(evs) == 1
    assert evs[0].field_name == "lead_intelligence"
