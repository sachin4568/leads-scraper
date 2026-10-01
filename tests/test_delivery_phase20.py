from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker

from backend.app.api import current_workspace_id
from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import Customer, Deal, DeliveryProject, Lead, LeadAction, ProjectDeliverable, Proposal, Workspace
from backend.app.models_phase2 import Base as Phase2Base
from backend.app.models_services import Base as ServicesBase


@pytest.fixture
def db_session():
    """Isolated in-memory SQLite database session for delivery tests."""
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
    """Sets up dual workspaces with Won Deals and Proposals."""
    ws_a = Workspace(name="Delivery Agency A")
    ws_b = Workspace(name="Delivery Agency B")
    db_session.add_all([ws_a, ws_b])
    db_session.commit()
    db_session.refresh(ws_a)
    db_session.refresh(ws_b)

    lead_a = Lead(
        workspace_id=ws_a.id,
        business_name="Apex Dental Care",
        phone="+91 98111 55555",
        email="contact@apexdental.com",
        genuineness_score=0.98,
        workflow_status="WON",
    )
    db_session.add(lead_a)
    db_session.commit()
    db_session.refresh(lead_a)

    deal_a = Deal(
        workspace_id=ws_a.id,
        lead_id=lead_a.id,
        title="Apex Dental — Website Modernization",
        service_type="WEBSITE_DEVELOPMENT",
        deal_value=68000.0,
        stage="WON",
        probability=1.0,
    )
    db_session.add(deal_a)
    db_session.commit()
    db_session.refresh(deal_a)

    # Lead & Deal in Workspace B
    lead_b = Lead(
        workspace_id=ws_b.id,
        business_name="Radiant Skin Clinic",
        phone="+91 98222 66666",
        email="info@radiantskin.in",
        genuineness_score=0.92,
        workflow_status="WON",
    )
    db_session.add(lead_b)
    db_session.commit()
    db_session.refresh(lead_b)

    deal_b = Deal(
        workspace_id=ws_b.id,
        lead_id=lead_b.id,
        title="SEO Expansion",
        service_type="SEO",
        deal_value=45000.0,
        stage="WON",
        probability=1.0,
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


def test_won_deal_conversion_to_customer_and_project(db_session: Session, test_setup: dict):
    """Verifies that converting a WON deal creates a Customer, DeliveryProject, and initial deliverables."""
    ws_a = test_setup["ws_a"]
    deal_a = test_setup["deal_a"]
    lead_a = test_setup["lead_a"]

    app.dependency_overrides[current_workspace_id] = lambda: ws_a.id
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    res = client.post(f"/api/operations/deals/{deal_a.id}/convert-to-customer")
    assert res.status_code == 201
    data = res.json()

    assert data["contract_value"] == 68000.0
    assert data["status"] == "ONBOARDING"
    assert data["customer_name"] == "Apex Dental Care"
    assert len(data["deliverables"]) > 0

    # Verify Customer record exists in DB
    db_session.expire_all()
    cust = db_session.scalar(select(Customer).where(Customer.lead_id == lead_a.id))
    assert cust is not None
    assert cust.company_name == "Apex Dental Care"
    assert cust.lifetime_value == 68000.0

    # Verify Lead timeline milestone logged
    actions = db_session.scalars(select(LeadAction).where(LeadAction.lead_id == lead_a.id)).all()
    assert any("Customer Onboarding Initiated" in (a.notes or "") for a in actions)


def test_deliverable_tracking_and_dynamic_progress_calculation(db_session: Session, test_setup: dict):
    """Verifies deliverable updates dynamically recalculate overall project progress %."""
    ws_a = test_setup["ws_a"]
    deal_a = test_setup["deal_a"]

    app.dependency_overrides[current_workspace_id] = lambda: ws_a.id
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    conv_res = client.post(f"/api/operations/deals/{deal_a.id}/convert-to-customer")
    proj_id = conv_res.json()["id"]
    deliverables = conv_res.json()["deliverables"]
    assert len(deliverables) == 6

    # Complete 3 out of 6 deliverables (50% progress)
    for d in deliverables[:3]:
        client.patch(
            f"/api/operations/delivery/deliverables/{d['id']}",
            json={"status": "COMPLETED"},
        )

    # Check updated project progress
    res_proj = client.get(f"/api/operations/delivery/projects/{proj_id}")
    assert res_proj.status_code == 200
    assert res_proj.json()["progress_percent"] == 50.0

    # Complete remaining 3 deliverables (100% progress)
    for d in deliverables[3:]:
        client.patch(
            f"/api/operations/delivery/deliverables/{d['id']}",
            json={"status": "COMPLETED"},
        )

    res_proj_100 = client.get(f"/api/operations/delivery/projects/{proj_id}")
    assert res_proj_100.json()["progress_percent"] == 100.0


def test_project_delivery_stage_transitions(db_session: Session, test_setup: dict):
    """Verifies project stage progression to COMPLETED and sets actual completion date."""
    ws_a = test_setup["ws_a"]
    deal_a = test_setup["deal_a"]

    app.dependency_overrides[current_workspace_id] = lambda: ws_a.id
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    conv_res = client.post(f"/api/operations/deals/{deal_a.id}/convert-to-customer")
    proj_id = conv_res.json()["id"]

    # 1. Move to IN_PROGRESS
    res_inp = client.patch(
        f"/api/operations/delivery/projects/{proj_id}/status",
        json={"status": "IN_PROGRESS"},
    )
    assert res_inp.status_code == 200
    assert res_inp.json()["status"] == "IN_PROGRESS"

    # 2. Move to COMPLETED
    res_comp = client.patch(
        f"/api/operations/delivery/projects/{proj_id}/status",
        json={"status": "COMPLETED"},
    )
    assert res_comp.status_code == 200
    assert res_comp.json()["status"] == "COMPLETED"
    assert res_comp.json()["actual_completion_date"] is not None
    assert res_comp.json()["progress_percent"] == 100.0


def test_revenue_realization_and_delivery_metrics(db_session: Session, test_setup: dict):
    """Verifies distinction between active in-delivery revenue and realized completed revenue."""
    ws_a = test_setup["ws_a"]
    deal_a = test_setup["deal_a"]

    app.dependency_overrides[current_workspace_id] = lambda: ws_a.id
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    # 1. Convert deal -> In-delivery project (₹68,000)
    conv_res = client.post(f"/api/operations/deals/{deal_a.id}/convert-to-customer")
    proj_id = conv_res.json()["id"]

    res_m1 = client.get("/api/operations/delivery/metrics")
    assert res_m1.status_code == 200
    m1 = res_m1.json()
    assert m1["active_projects"] == 1
    assert m1["in_delivery_revenue"] == 68000.0
    assert m1["realized_completed_revenue"] == 0.0

    # 2. Mark project as COMPLETED
    client.patch(f"/api/operations/delivery/projects/{proj_id}/status", json={"status": "COMPLETED"})

    res_m2 = client.get("/api/operations/delivery/metrics")
    assert res_m2.status_code == 200
    m2 = res_m2.json()
    assert m2["active_projects"] == 0
    assert m2["completed_projects"] == 1
    assert m2["in_delivery_revenue"] == 0.0
    assert m2["realized_completed_revenue"] == 68000.0


def test_cross_workspace_delivery_isolation(db_session: Session, test_setup: dict):
    """Verifies that Tenant A cannot access or mutate Tenant B's customers, projects, or deliverables."""
    ws_a = test_setup["ws_a"]
    ws_b = test_setup["ws_b"]
    deal_b = test_setup["deal_b"]

    # Convert in Workspace B
    app.dependency_overrides[current_workspace_id] = lambda: ws_b.id
    app.dependency_overrides[get_db] = lambda: db_session
    client_b = TestClient(app)

    conv_b = client_b.post(f"/api/operations/deals/{deal_b.id}/convert-to-customer")
    proj_b_id = conv_b.json()["id"]
    deliv_b_id = conv_b.json()["deliverables"][0]["id"]

    # Switch to Workspace A
    app.dependency_overrides[current_workspace_id] = lambda: ws_a.id
    client_a = TestClient(app)

    # 1. Project Detail IDOR
    assert client_a.get(f"/api/operations/delivery/projects/{proj_b_id}").status_code == 404

    # 2. Stage Mutation IDOR
    assert client_a.patch(
        f"/api/operations/delivery/projects/{proj_b_id}/status",
        json={"status": "COMPLETED"},
    ).status_code == 404

    # 3. Deliverable Mutation IDOR
    assert client_a.patch(
        f"/api/operations/delivery/deliverables/{deliv_b_id}",
        json={"status": "COMPLETED"},
    ).status_code == 404
