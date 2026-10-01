from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker

from backend.app.api import current_workspace_id
from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import Deal, Lead, LeadAction, Proposal, ProposalVersion, Workspace
from backend.app.models_phase2 import Base as Phase2Base
from backend.app.models_services import Base as ServicesBase


@pytest.fixture
def db_session():
    """Isolated in-memory SQLite database session for proposals tests."""
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
def test_setup(db_session: Session):
    """Sets up two multi-tenant workspaces with Leads and CRM Deals."""
    ws_a = Workspace(name="Proposals Workspace A")
    ws_b = Workspace(name="Proposals Workspace B")
    db_session.add_all([ws_a, ws_b])
    db_session.commit()
    db_session.refresh(ws_a)
    db_session.refresh(ws_b)

    # Lead & Deal in Workspace A
    lead_a = Lead(
        workspace_id=ws_a.id,
        business_name="Dr. Sharma Dental Clinic",
        phone="+91 98111 22222",
        email="drsharma@dental.com",
        genuineness_score=0.95,
        workflow_status="QUALIFIED",
    )
    db_session.add(lead_a)
    db_session.commit()
    db_session.refresh(lead_a)

    deal_a = Deal(
        workspace_id=ws_a.id,
        lead_id=lead_a.id,
        title="Dental Website Modernization & WhatsApp Bot",
        service_type="WEBSITE_DEVELOPMENT",
        deal_value=75000.0,
        stage="QUALIFIED",
        probability=0.5,
    )
    db_session.add(deal_a)
    db_session.commit()
    db_session.refresh(deal_a)

    # Lead & Deal in Workspace B
    lead_b = Lead(
        workspace_id=ws_b.id,
        business_name="Elite Orthodontics",
        phone="+91 98333 44444",
        email="contact@eliteortho.in",
        genuineness_score=0.90,
        workflow_status="QUALIFIED",
    )
    db_session.add(lead_b)
    db_session.commit()
    db_session.refresh(lead_b)

    deal_b = Deal(
        workspace_id=ws_b.id,
        lead_id=lead_b.id,
        title="SEO & SMMA Retainer",
        service_type="SEO",
        deal_value=50000.0,
        stage="QUALIFIED",
        probability=0.4,
    )
    db_session.add(deal_b)
    db_session.commit()
    db_session.refresh(deal_b)

    return {
        "ws_a": ws_a,
        "ws_b": ws_b,
        "lead_a": lead_a,
        "deal_a": deal_a,
        "lead_b": lead_b,
        "deal_b": deal_b,
    }


def test_proposal_creation_and_pricing_calculation(db_session: Session, test_setup: dict):
    """Verifies that creating a proposal calculates quoted price and initializes version 1."""
    ws_a = test_setup["ws_a"]
    deal_a = test_setup["deal_a"]

    app.dependency_overrides[current_workspace_id] = lambda: ws_a.id
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    # Create proposal: base 70000 + addons 10000 - discount 5000 = 75000
    res = client.post(
        f"/api/operations/deals/{deal_a.id}/proposals",
        json={
            "title": "Custom Website & SEO Bundle",
            "service_type": "WEBSITE_DEVELOPMENT",
            "base_price": 70000.0,
            "addons_total": 10000.0,
            "discount_amount": 5000.0,
            "timeline": "4 weeks",
            "deliverables": ["Responsive Website", "Appointment System", "On-page SEO"],
        },
    )
    assert res.status_code == 201
    data = res.json()

    assert data["quoted_amount"] == 75000.0
    assert data["current_version"] == 1
    assert data["status"] == "PROPOSAL_DRAFT"
    assert len(data["versions"]) == 1
    assert data["versions"][0]["version_number"] == 1
    assert data["versions"][0]["quoted_amount"] == 75000.0

    # Verify deal stage updated to PROPOSAL
    db_session.expire_all()
    reloaded_deal = db_session.get(Deal, deal_a.id)
    assert reloaded_deal.stage == "PROPOSAL"


def test_proposal_versioning_and_append_only_history(db_session: Session, test_setup: dict):
    """Verifies creating new versions preserves previous versions and updates proposal values."""
    ws_a = test_setup["ws_a"]
    deal_a = test_setup["deal_a"]

    app.dependency_overrides[current_workspace_id] = lambda: ws_a.id
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    # 1. Create v1
    res1 = client.post(
        f"/api/operations/deals/{deal_a.id}/proposals",
        json={"title": "Proposal v1", "base_price": 80000.0, "addons_total": 0.0, "discount_amount": 0.0},
    )
    prop_id = res1.json()["id"]

    # 2. Add v2 with discount: 80000 base, 10000 discount = 70000
    res2 = client.post(
        f"/api/operations/proposals/{prop_id}/versions",
        json={
            "base_price": 80000.0,
            "addons_total": 0.0,
            "discount_amount": 10000.0,
            "change_summary": "Discounted during negotiation call",
        },
    )
    assert res2.status_code == 200
    data2 = res2.json()

    assert data2["current_version"] == 2
    assert data2["quoted_amount"] == 70000.0
    assert len(data2["versions"]) == 2
    assert data2["versions"][0]["version_number"] == 1
    assert data2["versions"][0]["quoted_amount"] == 80000.0
    assert data2["versions"][1]["version_number"] == 2
    assert data2["versions"][1]["quoted_amount"] == 70000.0


def test_proposal_status_transitions_and_deal_closing_won(db_session: Session, test_setup: dict):
    """Verifies lifecycle transitions and synchronizes Deal stage to WON with final revenue."""
    ws_a = test_setup["ws_a"]
    deal_a = test_setup["deal_a"]

    app.dependency_overrides[current_workspace_id] = lambda: ws_a.id
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    res1 = client.post(
        f"/api/operations/deals/{deal_a.id}/proposals",
        json={"title": "Dental Proposal", "base_price": 65000.0},
    )
    prop_id = res1.json()["id"]

    # 1. Send Proposal
    res_sent = client.patch(
        f"/api/operations/proposals/{prop_id}/status",
        json={"status": "PROPOSAL_SENT"},
    )
    assert res_sent.status_code == 200
    assert res_sent.json()["status"] == "PROPOSAL_SENT"
    assert res_sent.json()["sent_at"] is not None

    # 2. Negotiate
    res_neg = client.patch(
        f"/api/operations/proposals/{prop_id}/status",
        json={"status": "NEGOTIATION"},
    )
    assert res_neg.status_code == 200
    assert res_neg.json()["status"] == "NEGOTIATION"

    # 3. Accept Proposal (WON)
    res_acc = client.patch(
        f"/api/operations/proposals/{prop_id}/status",
        json={"status": "ACCEPTED"},
    )
    assert res_acc.status_code == 200
    assert res_acc.json()["status"] == "ACCEPTED"
    assert res_acc.json()["accepted_at"] is not None

    # Verify Deal is now WON with matching deal_value
    db_session.expire_all()
    reloaded_deal = db_session.get(Deal, deal_a.id)
    assert reloaded_deal.stage == "WON"
    assert reloaded_deal.deal_value == 65000.0
    assert reloaded_deal.closed_at is not None


def test_proposal_rejection_syncs_deal_lost(db_session: Session, test_setup: dict):
    """Verifies that rejecting a proposal marks the deal as LOST with reason."""
    ws_a = test_setup["ws_a"]
    deal_a = test_setup["deal_a"]

    app.dependency_overrides[current_workspace_id] = lambda: ws_a.id
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    res1 = client.post(
        f"/api/operations/deals/{deal_a.id}/proposals",
        json={"title": "Proposal to Decline", "base_price": 90000.0},
    )
    prop_id = res1.json()["id"]

    res_rej = client.patch(
        f"/api/operations/proposals/{prop_id}/status",
        json={"status": "REJECTED", "rejection_reason": "Budget limit exceeded"},
    )
    assert res_rej.status_code == 200
    assert res_rej.json()["status"] == "REJECTED"
    assert res_rej.json()["rejection_reason"] == "Budget limit exceeded"

    db_session.expire_all()
    reloaded_deal = db_session.get(Deal, deal_a.id)
    assert reloaded_deal.stage == "LOST"
    assert reloaded_deal.win_loss_reason == "Budget limit exceeded"


def test_closing_intelligence_metrics(db_session: Session, test_setup: dict):
    """Verifies aggregate closing KPIs, won revenue, win rate, and negotiation reduction."""
    ws_a = test_setup["ws_a"]
    deal_a = test_setup["deal_a"]

    app.dependency_overrides[current_workspace_id] = lambda: ws_a.id
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    # Proposal 1: v1 100k -> v2 80k -> ACCEPTED
    res1 = client.post(
        f"/api/operations/deals/{deal_a.id}/proposals",
        json={"title": "Large Package", "base_price": 100000.0},
    )
    p1_id = res1.json()["id"]
    client.post(
        f"/api/operations/proposals/{p1_id}/versions",
        json={"base_price": 100000.0, "discount_amount": 20000.0},
    )
    client.patch(f"/api/operations/proposals/{p1_id}/status", json={"status": "ACCEPTED"})

    # Fetch Metrics
    res_m = client.get("/api/operations/proposals/metrics")
    assert res_m.status_code == 200
    metrics = res_m.json()

    assert metrics["total_proposals"] == 1
    assert metrics["accepted_count"] == 1
    assert metrics["total_won_revenue"] == 80000.0
    assert metrics["proposal_to_win_rate"] == 100.0
    assert metrics["avg_negotiation_reduction"] == 20000.0


def test_cross_workspace_proposal_isolation(db_session: Session, test_setup: dict):
    """Verifies that Workspace A cannot view, version, or mutate Workspace B's proposals."""
    ws_a = test_setup["ws_a"]
    ws_b = test_setup["ws_b"]
    deal_b = test_setup["deal_b"]

    # Create proposal in Workspace B
    app.dependency_overrides[current_workspace_id] = lambda: ws_b.id
    app.dependency_overrides[get_db] = lambda: db_session
    client_b = TestClient(app)

    res_b = client_b.post(
        f"/api/operations/deals/{deal_b.id}/proposals",
        json={"title": "Tenant B Secret Proposal", "base_price": 50000.0},
    )
    prop_b_id = res_b.json()["id"]

    # Attempt cross-tenant access from Workspace A
    app.dependency_overrides[current_workspace_id] = lambda: ws_a.id
    client_a = TestClient(app)

    # 1. Detail IDOR
    assert client_a.get(f"/api/operations/proposals/{prop_b_id}").status_code == 404

    # 2. Version IDOR
    assert client_a.post(
        f"/api/operations/proposals/{prop_b_id}/versions",
        json={"base_price": 40000.0},
    ).status_code == 404

    # 3. Status IDOR
    assert client_a.patch(
        f"/api/operations/proposals/{prop_b_id}/status",
        json={"status": "ACCEPTED"},
    ).status_code == 404
