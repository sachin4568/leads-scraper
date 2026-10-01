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
from backend.app.models import EvidenceRecord, Lead, LeadAction, Workspace
from backend.app.models_phase2 import Base as Phase2Base
from backend.app.models_services import Base as ServicesBase


@pytest.fixture
def db_session():
    """Isolated in-memory SQLite session with multi-thread support for TestClient."""
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
def phase12_setup(db_session: Session):
    """Seed test workspace and leads with varying contactability and intelligence states."""
    workspace = Workspace(name="Phase 12 Outreach Workspace")
    db_session.add(workspace)
    db_session.commit()
    db_session.refresh(workspace)

    # Lead 1: WhatsApp Available -> Recommended WHATSAPP
    lead1 = Lead(
        workspace_id=workspace.id,
        business_name="Radiant Smile Clinic",
        phone="+91 98200 11111",
        email="info@radiantsmile.in",
        website="https://radiantsmile.in",
        genuineness_score=0.95,
        workflow_status="NEW",
    )
    # Lead 2: Email Only -> Recommended EMAIL
    lead2 = Lead(
        workspace_id=workspace.id,
        business_name="Metro Orthodontics",
        phone=None,
        email="contact@metroortho.com",
        website="http://metroortho.com",
        genuineness_score=0.88,
        workflow_status="NEW",
    )
    # Lead 3: Phone Only -> Recommended PHONE
    lead3 = Lead(
        workspace_id=workspace.id,
        business_name="Suburban Care Clinic",
        phone="+91 98200 33333",
        email=None,
        website=None,
        genuineness_score=0.90,
        workflow_status="NEW",
    )
    # Lead 4: Social Only -> Recommended SOCIAL_DM
    lead4 = Lead(
        workspace_id=workspace.id,
        business_name="Boutique Dental Spa",
        phone=None,
        email=None,
        website=None,
        genuineness_score=0.82,
        workflow_status="NEW",
    )
    # Lead 5: No Channel -> Recommended NONE
    lead5 = Lead(
        workspace_id=workspace.id,
        business_name="Ghost Dental Facility",
        phone=None,
        email=None,
        website=None,
        genuineness_score=0.60,
        workflow_status="NEW",
    )

    db_session.add_all([lead1, lead2, lead3, lead4, lead5])
    db_session.commit()
    for l in [lead1, lead2, lead3, lead4, lead5]:
        db_session.refresh(l)

    # Add evidence records
    # Lead 1: High opp with WhatsApp link
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
            lead_id=lead1.id,
            field_name="lead_intelligence",
            status="VERY_HIGH",
            confidence_score=90,
            source="LEAD_INTELLIGENCE_ENGINE",
            details={"overall_opportunity_score": 85, "opportunity_category": "VERY_HIGH", "top_reasons": ["WhatsApp available"]},
        )
    )

    # Lead 2: High opp with email
    db_session.add(
        EvidenceRecord(
            workspace_id=workspace.id,
            lead_id=lead2.id,
            field_name="lead_intelligence",
            status="HIGH",
            confidence_score=85,
            source="LEAD_INTELLIGENCE_ENGINE",
            details={"overall_opportunity_score": 75, "opportunity_category": "HIGH", "top_reasons": ["Unencrypted HTTP"]},
        )
    )

    # Lead 3: High opp no website, phone available
    db_session.add(
        EvidenceRecord(
            workspace_id=workspace.id,
            lead_id=lead3.id,
            field_name="lead_intelligence",
            status="VERY_HIGH",
            confidence_score=95,
            source="LEAD_INTELLIGENCE_ENGINE",
            details={"overall_opportunity_score": 90, "opportunity_category": "VERY_HIGH", "top_reasons": ["No website"]},
        )
    )

    # Lead 4: Social only
    db_session.add(
        EvidenceRecord(
            workspace_id=workspace.id,
            lead_id=lead4.id,
            field_name="social_profiles",
            status="ACCEPT",
            confidence_score=80,
            source="WEBSITE_ENRICHMENT",
            details={"profiles": {"instagram": "https://instagram.com/boutiquedental"}},
        )
    )
    db_session.add(
        EvidenceRecord(
            workspace_id=workspace.id,
            lead_id=lead4.id,
            field_name="lead_intelligence",
            status="MEDIUM",
            confidence_score=75,
            source="LEAD_INTELLIGENCE_ENGINE",
            details={"overall_opportunity_score": 55, "opportunity_category": "MEDIUM", "top_reasons": ["Instagram profile active"]},
        )
    )

    db_session.commit()
    return {"workspace": workspace, "leads": [lead1, lead2, lead3, lead4, lead5]}


def test_recommended_channel_derivation(db_session: Session, phase12_setup: dict):
    """Verifies deterministic outreach channel recommendations based on contactability."""
    workspace = phase12_setup["workspace"]
    leads = phase12_setup["leads"]

    app.dependency_overrides[current_workspace_id] = lambda: workspace.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    res = client.get("/api/operations/leads")
    assert res.status_code == 200
    data = res.json()["results"]

    by_name = {l["business_name"]: l for l in data}

    # Lead 1: WhatsApp link present -> WHATSAPP
    assert by_name["Radiant Smile Clinic"]["recommended_channel"]["channel"] == "WHATSAPP"
    assert by_name["Radiant Smile Clinic"]["recommended_channel"]["label"] == "WhatsApp Direct"

    # Lead 2: Email present -> EMAIL
    assert by_name["Metro Orthodontics"]["recommended_channel"]["channel"] == "EMAIL"

    # Lead 3: Phone present -> PHONE
    assert by_name["Suburban Care Clinic"]["recommended_channel"]["channel"] == "PHONE"

    # Lead 4: Social only -> SOCIAL_DM
    assert by_name["Boutique Dental Spa"]["recommended_channel"]["channel"] == "SOCIAL_DM"

    # Lead 5: No channel -> NONE
    assert by_name["Ghost Dental Facility"]["recommended_channel"]["channel"] == "NONE"


def test_outreach_action_logging_and_append_only_history(db_session: Session, phase12_setup: dict):
    """Verifies action recording, chronological history, and workflow state transitions."""
    workspace = phase12_setup["workspace"]
    lead = phase12_setup["leads"][0]  # Radiant Smile Clinic

    app.dependency_overrides[current_workspace_id] = lambda: workspace.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    # 1. Log First Attempt: Phone Call (No Response)
    res1 = client.post(
        f"/api/operations/leads/{lead.id}/actions",
        json={
            "channel": "PHONE",
            "outcome": "NO_RESPONSE",
            "notes": "Left voicemail regarding website redesign.",
            "follow_up_date": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
        },
    )
    assert res1.status_code == 201
    act1 = res1.json()
    assert act1["channel"] == "PHONE"
    assert act1["outcome"] == "NO_RESPONSE"

    # 2. Log Second Attempt: WhatsApp Message (Interested)
    res2 = client.post(
        f"/api/operations/leads/{lead.id}/actions",
        json={
            "channel": "WHATSAPP",
            "outcome": "INTERESTED",
            "notes": "Owner replied asking for portfolio and pricing.",
            "follow_up_date": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        },
    )
    assert res2.status_code == 201
    act2 = res2.json()
    assert act2["channel"] == "WHATSAPP"
    assert act2["outcome"] == "INTERESTED"

    # 3. Retrieve Chronological History via GET /actions
    res_hist = client.get(f"/api/operations/leads/{lead.id}/actions")
    assert res_hist.status_code == 200
    history = res_hist.json()
    assert len(history) == 2
    # Latest action is first
    assert history[0]["channel"] == "WHATSAPP"
    assert history[1]["channel"] == "PHONE"

    # 4. Check Lead Detail contains complete action history
    res_det = client.get(f"/api/operations/leads/{lead.id}")
    assert res_det.status_code == 200
    det_data = res_det.json()
    assert det_data["actions_count"] == 2
    assert len(det_data["action_history"]) == 2
    assert det_data["latest_action"]["channel"] == "WHATSAPP"
    assert det_data["workflow_status"] == "CONTACTED"


def test_priority_queue_and_follow_up_management(db_session: Session, phase12_setup: dict):
    """Verifies priority queue classification: CONTACT_NOW, FOLLOW_UP_OVERDUE, and NO_CONTACT_CHANNEL."""
    workspace = phase12_setup["workspace"]
    lead1 = phase12_setup["leads"][0]  # Very High with WhatsApp -> CONTACT_NOW
    lead3 = phase12_setup["leads"][2]  # Very High with Phone -> CONTACT_NOW
    lead5 = phase12_setup["leads"][4]  # No channel -> NO_CONTACT_CHANNEL

    app.dependency_overrides[current_workspace_id] = lambda: workspace.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    # 1. Check CONTACT_NOW Queue
    res_cn = client.get("/api/operations/leads?priority_queue=CONTACT_NOW")
    assert res_cn.status_code == 200
    cn_data = res_cn.json()
    assert cn_data["total"] >= 2
    assert {l["business_name"] for l in cn_data["results"]}.issuperset(
        {"Radiant Smile Clinic", "Suburban Care Clinic"}
    )

    # 2. Check NO_CONTACT_CHANNEL Queue
    res_nc = client.get("/api/operations/leads?priority_queue=NO_CONTACT_CHANNEL")
    assert res_nc.status_code == 200
    assert res_nc.json()["total"] == 1
    assert res_nc.json()["results"][0]["business_name"] == "Ghost Dental Facility"

    # 3. Schedule Overdue Follow-up on Lead 3
    client.post(
        f"/api/operations/leads/{lead3.id}/actions",
        json={
            "channel": "PHONE",
            "outcome": "FOLLOW_UP_SCHEDULED",
            "notes": "Requested call back yesterday.",
            "follow_up_date": (datetime.now(UTC) - timedelta(hours=5)).isoformat(),
        },
    )

    # 4. Filter by FOLLOW_UP_OVERDUE
    res_od = client.get("/api/operations/leads?priority_queue=FOLLOW_UP_OVERDUE")
    assert res_od.status_code == 200
    assert res_od.json()["total"] == 1
    assert res_od.json()["results"][0]["business_name"] == "Suburban Care Clinic"


def test_outreach_dashboard_metrics(db_session: Session, phase12_setup: dict):
    """Verifies workspace-wide outreach dashboard summary metrics."""
    workspace = phase12_setup["workspace"]

    app.dependency_overrides[current_workspace_id] = lambda: workspace.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    res = client.get("/api/operations/outreach/dashboard")
    assert res.status_code == 200
    data = res.json()

    assert data["total_leads"] == 5
    assert data["ready_to_contact"] >= 2
    assert "whatsapp" in data["channels_breakdown"]
    assert "email" in data["channels_breakdown"]


def test_source_evidence_immutability_on_actions(db_session: Session, phase12_setup: dict):
    """Verifies that recording outreach attempts does NOT mutate raw OSM or Evidence records."""
    workspace = phase12_setup["workspace"]
    lead = phase12_setup["leads"][0]

    app.dependency_overrides[current_workspace_id] = lambda: workspace.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    # Log action
    client.post(
        f"/api/operations/leads/{lead.id}/actions",
        json={
            "channel": "EMAIL",
            "outcome": "MEETING_BOOKED",
            "notes": "Demo scheduled for Friday 10 AM.",
        },
    )

    db_session.expire_all()
    reloaded_lead = db_session.get(Lead, lead.id)

    # Source data and ground truth remain intact
    assert reloaded_lead.business_name == "Radiant Smile Clinic"
    assert reloaded_lead.phone == "+91 98200 11111"
    assert reloaded_lead.email == "info@radiantsmile.in"
    assert reloaded_lead.website == "https://radiantsmile.in"
    assert reloaded_lead.workflow_status == "QUALIFIED"

    # Evidence records remain intact
    evs = db_session.query(EvidenceRecord).filter(EvidenceRecord.lead_id == lead.id).all()
    assert len(evs) == 2
    assert any(e.field_name == "contacts" for e in evs)
