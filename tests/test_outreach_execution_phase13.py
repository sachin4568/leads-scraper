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
def phase13_setup(db_session: Session):
    """Seed test workspace and leads across pipeline stages."""
    workspace = Workspace(name="Phase 13 Execution & Response Workspace")
    db_session.add(workspace)
    db_session.commit()
    db_session.refresh(workspace)

    # Lead 1: WhatsApp outreach lead -> Meeting Booked -> Qualified
    lead1 = Lead(
        workspace_id=workspace.id,
        business_name="Apex Dental Hospital",
        phone="+91 98200 11111",
        email="info@apexdental.com",
        website="https://apexdental.com",
        genuineness_score=0.95,
        workflow_status="NEW",
    )
    # Lead 2: Phone call outreach -> Converted
    lead2 = Lead(
        workspace_id=workspace.id,
        business_name="Smile Care Centre",
        phone="+91 98200 22222",
        email="care@smilecare.in",
        website="http://smilecare.in",
        genuineness_score=0.88,
        workflow_status="NEW",
    )
    # Lead 3: Email outreach -> Lost
    lead3 = Lead(
        workspace_id=workspace.id,
        business_name="Dental Spa Express",
        phone=None,
        email="contact@dentalspa.in",
        website="https://dentalspa.in",
        genuineness_score=0.85,
        workflow_status="NEW",
    )
    # Lead 4: No direct channel -> Uncontacted
    lead4 = Lead(
        workspace_id=workspace.id,
        business_name="Uncontactable Facility",
        phone=None,
        email=None,
        website=None,
        genuineness_score=0.60,
        workflow_status="NEW",
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
            field_name="website",
            status="ACCEPT",
            confidence_score=98,
            source="ZERO_BUDGET_VERIFIED",
            details={"verified_url": "https://apexdental.com"},
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
            details={"overall_opportunity_score": 85, "opportunity_category": "VERY_HIGH", "top_reasons": ["WhatsApp channel active"]},
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
            details={"overall_opportunity_score": 75, "opportunity_category": "HIGH", "top_reasons": ["Unencrypted HTTP"]},
        )
    )

    db_session.commit()
    return {"workspace": workspace, "leads": [lead1, lead2, lead3, lead4]}


def test_execution_links_generation(db_session: Session, phase13_setup: dict):
    """Verifies that direct execution links (tel, mailto, wa.me, website) are generated correctly."""
    workspace = phase13_setup["workspace"]
    lead1 = phase13_setup["leads"][0]

    app.dependency_overrides[current_workspace_id] = lambda: workspace.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    res = client.get(f"/api/operations/leads/{lead1.id}")
    assert res.status_code == 200
    data = res.json()

    exec_links = data["execution_links"]
    assert len(exec_links) >= 3

    channels = {l["channel"]: l["url"] for l in exec_links}
    assert "PHONE" in channels
    assert "tel:+919820011111" in channels["PHONE"]

    assert "WHATSAPP" in channels
    assert "wa.me" in channels["WHATSAPP"]

    assert "EMAIL" in channels
    assert "mailto:info@apexdental.com" in channels["EMAIL"]

    assert "CONTACT_PAGE" in channels
    assert channels["CONTACT_PAGE"] == "https://apexdental.com"


def test_response_tracking_and_transitions(db_session: Session, phase13_setup: dict):
    """Verifies response logging and automated pipeline transitions across stages."""
    workspace = phase13_setup["workspace"]
    lead = phase13_setup["leads"][0]

    app.dependency_overrides[current_workspace_id] = lambda: workspace.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    # 1. Outreach Attempt -> CONTACTED
    res1 = client.post(
        f"/api/operations/leads/{lead.id}/actions",
        json={"channel": "WHATSAPP", "outcome": "CONTACTED", "notes": "Pitch message sent."},
    )
    assert res1.status_code == 201
    assert res1.json()["outcome"] == "CONTACTED"

    # 2. Customer Responds -> INTERESTED
    res2 = client.post(
        f"/api/operations/leads/{lead.id}/actions",
        json={"channel": "WHATSAPP", "outcome": "INTERESTED", "notes": "Doctor expressed interest."},
    )
    assert res2.status_code == 201

    # 3. Schedule Consultation -> MEETING_BOOKED -> QUALIFIED
    res3 = client.post(
        f"/api/operations/leads/{lead.id}/actions",
        json={"channel": "PHONE", "outcome": "MEETING_BOOKED", "notes": "Meeting booked for Monday."},
    )
    assert res3.status_code == 201

    # 4. Conversion -> CONVERTED
    res4 = client.post(
        f"/api/operations/leads/{lead.id}/actions",
        json={"channel": "PHONE", "outcome": "CONVERTED", "notes": "Signed web modernization contract."},
    )
    assert res4.status_code == 201

    # Check lead final state
    db_session.expire_all()
    reloaded = db_session.get(Lead, lead.id)
    assert reloaded.workflow_status == "CONVERTED"


def test_unified_activity_timeline(db_session: Session, phase13_setup: dict):
    """Verifies that unified activity timeline connects discovery, verification, enrichment, scoring, outreach, and conversion."""
    workspace = phase13_setup["workspace"]
    lead = phase13_setup["leads"][0]

    app.dependency_overrides[current_workspace_id] = lambda: workspace.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    # Log outreach events
    client.post(
        f"/api/operations/leads/{lead.id}/actions",
        json={"channel": "WHATSAPP", "outcome": "INTERESTED", "notes": "Interested in redesign."},
    )
    client.post(
        f"/api/operations/leads/{lead.id}/actions",
        json={"channel": "PHONE", "outcome": "MEETING_BOOKED", "notes": "Consultation scheduled."},
    )

    res = client.get(f"/api/operations/leads/{lead.id}/timeline")
    assert res.status_code == 200
    timeline = res.json()

    assert timeline["lead_id"] == str(lead.id)
    assert timeline["business_name"] == "Apex Dental Hospital"
    events = timeline["events"]
    assert len(events) >= 5

    event_types = [e["event_type"] for e in events]
    assert "DISCOVERY" in event_types
    assert "WEBSITE_VERIFICATION" in event_types
    assert "ENRICHMENT" in event_types
    assert "OPPORTUNITY_SCORING" in event_types
    assert "MEETING" in event_types


def test_outreach_analytics_funnel_and_channel_metrics(db_session: Session, phase13_setup: dict):
    """Verifies pipeline funnel calculations, step-by-step conversion drop-offs, and channel effectiveness."""
    workspace = phase13_setup["workspace"]
    lead1 = phase13_setup["leads"][0]
    lead2 = phase13_setup["leads"][1]
    lead3 = phase13_setup["leads"][2]

    app.dependency_overrides[current_workspace_id] = lambda: workspace.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    # Lead 1: WhatsApp -> Interested -> Meeting -> Converted
    client.post(f"/api/operations/leads/{lead1.id}/actions", json={"channel": "WHATSAPP", "outcome": "INTERESTED"})
    client.post(f"/api/operations/leads/{lead1.id}/actions", json={"channel": "WHATSAPP", "outcome": "MEETING_BOOKED"})
    client.post(f"/api/operations/leads/{lead1.id}/actions", json={"channel": "WHATSAPP", "outcome": "CONVERTED"})

    # Lead 2: Phone -> No Response
    client.post(f"/api/operations/leads/{lead2.id}/actions", json={"channel": "PHONE", "outcome": "NO_RESPONSE"})

    # Lead 3: Email -> Not Interested / Lost
    client.post(f"/api/operations/leads/{lead3.id}/actions", json={"channel": "EMAIL", "outcome": "LOST"})

    res = client.get("/api/operations/outreach/analytics")
    assert res.status_code == 200
    analytics = res.json()

    assert analytics["total_leads"] == 4
    assert analytics["contactable_leads"] == 3
    assert analytics["contacted_leads"] == 3
    assert analytics["responded_leads"] >= 2
    assert analytics["converted_leads"] == 1

    # Check Funnel
    funnel = {f["stage"]: f["count"] for f in analytics["funnel"]}
    assert funnel["Leads Discovered"] == 4
    assert funnel["Contactable"] == 3
    assert funnel["Contacted"] == 3
    assert funnel["Converted"] == 1

    # Check Channel Effectiveness
    ch_map = {c["channel"]: c for c in analytics["channel_effectiveness"]}
    assert ch_map["WHATSAPP"]["attempts"] == 3
    assert ch_map["WHATSAPP"]["conversions"] == 1
    assert ch_map["WHATSAPP"]["conversion_rate"] > 0
    assert ch_map["PHONE"]["attempts"] == 1
    assert ch_map["EMAIL"]["attempts"] == 1


def test_source_evidence_immutability(db_session: Session, phase13_setup: dict):
    """Verifies that executing outreach and recording responses does not mutate ground-truth OSM tags or EvidenceRecords."""
    workspace = phase13_setup["workspace"]
    lead = phase13_setup["leads"][0]

    app.dependency_overrides[current_workspace_id] = lambda: workspace.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    client.post(
        f"/api/operations/leads/{lead.id}/actions",
        json={"channel": "WHATSAPP", "outcome": "CONVERTED", "notes": "Signed agreement."},
    )

    db_session.expire_all()
    reloaded = db_session.get(Lead, lead.id)
    assert reloaded.business_name == "Apex Dental Hospital"
    assert reloaded.phone == "+91 98200 11111"
    assert reloaded.email == "info@apexdental.com"
    assert reloaded.website == "https://apexdental.com"

    evs = db_session.query(EvidenceRecord).filter(EvidenceRecord.lead_id == lead.id).all()
    assert len(evs) == 3
    assert any(e.field_name == "contacts" for e in evs)
    assert any(e.field_name == "website" for e in evs)
    assert any(e.field_name == "lead_intelligence" for e in evs)
