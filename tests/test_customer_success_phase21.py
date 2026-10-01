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
from backend.app.models import (
    Customer,
    CustomerRetainer,
    Deal,
    DeliveryProject,
    Lead,
    LeadAction,
    UpsellOpportunity,
    Workspace,
)
from backend.app.models_phase2 import Base as Phase2Base
from backend.app.models_services import Base as ServicesBase


@pytest.fixture
def db_session():
    """Isolated in-memory SQLite database session for customer success tests."""
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
def workspace_a(db_session: Session) -> Workspace:
    ws = Workspace(name="Success WS A")
    db_session.add(ws)
    db_session.commit()
    db_session.refresh(ws)
    return ws


@pytest.fixture
def workspace_b(db_session: Session) -> Workspace:
    ws = Workspace(name="Success WS B")
    db_session.add(ws)
    db_session.commit()
    db_session.refresh(ws)
    return ws


def test_customer_retainer_creation_and_mrr_calculation(
    db_session: Session, workspace_a: Workspace
):
    """Tests creating monthly and quarterly retainers and deterministic MRR/ARR calculation."""
    app.dependency_overrides[current_workspace_id] = lambda: workspace_a.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    lead = Lead(
        workspace_id=workspace_a.id,
        business_name="Apex Dental Care",
        workflow_status="WON",
    )
    db_session.add(lead)
    db_session.commit()

    cust = Customer(
        workspace_id=workspace_a.id,
        lead_id=lead.id,
        company_name="Apex Dental Care",
        status="ACTIVE",
        lifetime_value=68000.0,
    )
    db_session.add(cust)
    db_session.commit()
    db_session.refresh(cust)

    # 1. Add Monthly Retainer (₹15,000/month)
    res1 = client.post(
        f"/api/operations/customers/{cust.id}/retainers",
        json={
            "service_type": "SEO_RETAINER",
            "billing_frequency": "MONTHLY",
            "billing_amount": 15000.0,
            "duration_months": 1,
            "auto_renew": True,
            "notes": "SEO Optimization & Local Google Maps Ranking",
        },
    )
    assert res1.status_code == 201
    ret1 = res1.json()
    assert ret1["monthly_mrr"] == 15000.0
    assert ret1["status"] == "ACTIVE"

    # 2. Add Quarterly Retainer (₹30,000/quarter -> ₹10,000/month MRR)
    res2 = client.post(
        f"/api/operations/customers/{cust.id}/retainers",
        json={
            "service_type": "HOSTING_MAINTENANCE",
            "billing_frequency": "QUARTERLY",
            "billing_amount": 30000.0,
            "duration_months": 1,
            "auto_renew": True,
            "notes": "Managed Cloud Hosting & Backups",
        },
    )
    assert res2.status_code == 201
    ret2 = res2.json()
    assert ret2["monthly_mrr"] == 10000.0

    # 3. Verify Customer MRR, ARR, and Lifetime Value
    db_session.refresh(cust)
    assert cust.mrr == 25000.0  # 15,000 + 10,000
    assert cust.arr == 300000.0  # 25,000 * 12
    assert cust.lifetime_value == 113000.0  # 68,000 + 15,000 + 30,000

    # 4. Verify Timeline continuity on linked lead
    actions = db_session.scalars(
        db_session.query(LeadAction).filter_by(lead_id=lead.id).statement
    ).all()
    assert len(actions) == 2
    assert any("Recurring Retainer Started" in a.notes for a in actions)


def test_retainer_renewal_flow_and_ltv_growth(
    db_session: Session, workspace_a: Workspace
):
    """Tests renewing a retainer, advancing renewal dates, and incrementing LTV."""
    app.dependency_overrides[current_workspace_id] = lambda: workspace_a.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    cust = Customer(
        workspace_id=workspace_a.id,
        company_name="Radiant Skin Clinic",
        status="ACTIVE",
        lifetime_value=50000.0,
    )
    db_session.add(cust)
    db_session.commit()

    now = datetime.now(UTC)
    retainer = CustomerRetainer(
        workspace_id=workspace_a.id,
        customer_id=cust.id,
        service_type="SMMA_RETAINER",
        billing_frequency="MONTHLY",
        billing_amount=20000.0,
        monthly_mrr=20000.0,
        status="ACTIVE",
        start_date=now - timedelta(days=30),
        renewal_date=now + timedelta(days=1),
        auto_renew=True,
    )
    db_session.add(retainer)
    db_session.commit()

    # Renew Retainer
    res = client.patch(f"/api/operations/retainers/{retainer.id}/renew")
    assert res.status_code == 200
    renewed = res.json()
    assert renewed["status"] == "ACTIVE"

    # LTV increased by ₹20,000
    db_session.refresh(cust)
    assert cust.lifetime_value == 70000.0


def test_deterministic_customer_health_scoring(
    db_session: Session, workspace_a: Workspace
):
    """Tests deterministic health states (HEALTHY, AT_RISK, CRITICAL, DORMANT)."""
    app.dependency_overrides[current_workspace_id] = lambda: workspace_a.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)
    now = datetime.now(UTC)

    # 1. Healthy Customer (Active Retainer)
    c_healthy = Customer(workspace_id=workspace_a.id, company_name="Healthy Clinic", status="ACTIVE")
    db_session.add(c_healthy)
    db_session.commit()
    r_healthy = CustomerRetainer(
        workspace_id=workspace_a.id,
        customer_id=c_healthy.id,
        service_type="SEO_RETAINER",
        billing_frequency="MONTHLY",
        billing_amount=10000.0,
        monthly_mrr=10000.0,
        status="ACTIVE",
        renewal_date=now + timedelta(days=25),
    )
    db_session.add(r_healthy)

    # 2. At-Risk Customer (Expiring within 14 days)
    c_at_risk = Customer(workspace_id=workspace_a.id, company_name="At Risk Clinic", status="ACTIVE")
    db_session.add(c_at_risk)
    db_session.commit()
    r_at_risk = CustomerRetainer(
        workspace_id=workspace_a.id,
        customer_id=c_at_risk.id,
        service_type="SMMA_RETAINER",
        billing_frequency="MONTHLY",
        billing_amount=15000.0,
        monthly_mrr=15000.0,
        status="ACTIVE",
        renewal_date=now + timedelta(days=5),
    )
    db_session.add(r_at_risk)

    # 3. Critical Customer (Cancelled Retainer, 0 Active)
    c_critical = Customer(workspace_id=workspace_a.id, company_name="Critical Clinic", status="ACTIVE")
    db_session.add(c_critical)
    db_session.commit()
    r_critical = CustomerRetainer(
        workspace_id=workspace_a.id,
        customer_id=c_critical.id,
        service_type="MAINTENANCE",
        billing_frequency="MONTHLY",
        billing_amount=5000.0,
        monthly_mrr=5000.0,
        status="CANCELLED",
        renewal_date=now - timedelta(days=10),
    )
    db_session.add(r_critical)

    # 4. Dormant Customer (Completed Delivery, 0 Retainers)
    c_dormant = Customer(workspace_id=workspace_a.id, company_name="Dormant Clinic", status="COMPLETED")
    db_session.add(c_dormant)
    db_session.commit()
    p_dormant = DeliveryProject(
        workspace_id=workspace_a.id,
        customer_id=c_dormant.id,
        project_name="Dormant Web Delivery",
        service_type="WEBSITE_DEVELOPMENT",
        status="COMPLETED",
    )
    db_session.add(p_dormant)
    db_session.commit()

    # Query health matrix endpoint
    res = client.get("/api/operations/success/health")
    assert res.status_code == 200
    matrix = {item["company_name"]: item for item in res.json()}

    assert matrix["Healthy Clinic"]["health_score"] == "HEALTHY"
    assert matrix["At Risk Clinic"]["health_score"] == "AT_RISK"
    assert matrix["Critical Clinic"]["health_score"] == "CRITICAL"
    assert matrix["Dormant Clinic"]["health_score"] == "DORMANT"


def test_deterministic_upsell_expansion_and_acceptance(
    db_session: Session, workspace_a: Workspace
):
    """Tests automatic generation of deterministic upsells and converting to active retainer on acceptance."""
    app.dependency_overrides[current_workspace_id] = lambda: workspace_a.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    cust = Customer(
        workspace_id=workspace_a.id,
        company_name="Apex Care Center",
        status="ACTIVE",
    )
    db_session.add(cust)
    db_session.commit()

    # Add completed Website Development project
    proj = DeliveryProject(
        workspace_id=workspace_a.id,
        customer_id=cust.id,
        project_name="Apex Modern Website",
        service_type="WEBSITE_DEVELOPMENT",
        status="COMPLETED",
    )
    db_session.add(proj)
    db_session.commit()

    # Trigger health check / upsell generation
    _ = client.get("/api/operations/success/health")

    # Verify upsell opportunities created
    res = client.get("/api/operations/success/upsells")
    assert res.status_code == 200
    upsells = res.json()
    assert len(upsells) >= 2
    service_types = {u["service_type"] for u in upsells}
    assert "SEO_RETAINER" in service_types
    assert "WEBSITE_MAINTENANCE" in service_types

    # Find the SEO Retainer upsell
    seo_upsell = next(u for u in upsells if u["service_type"] == "SEO_RETAINER")
    assert seo_upsell["status"] == "IDENTIFIED"
    assert seo_upsell["estimated_mrr"] == 15000.0

    # Accept the upsell
    res_accept = client.patch(
        f"/api/operations/success/upsells/{seo_upsell['id']}/status",
        json={"status": "ACCEPTED"},
    )
    assert res_accept.status_code == 200
    assert res_accept.json()["status"] == "ACCEPTED"

    # Verify that a new active recurring retainer was automatically generated!
    retainers = client.get(f"/api/operations/retainers?customer_id={cust.id}").json()
    assert len(retainers) == 1
    assert retainers[0]["service_type"] == "SEO_RETAINER"
    assert retainers[0]["monthly_mrr"] == 15000.0
    assert retainers[0]["status"] == "ACTIVE"


def test_customer_success_metrics_and_multi_tenant_isolation(
    db_session: Session, workspace_a: Workspace, workspace_b: Workspace
):
    """Tests success metrics aggregation and strict workspace isolation."""
    # Workspace A setup
    c_a = Customer(
        workspace_id=workspace_a.id,
        company_name="Workspace A Client",
        status="ACTIVE",
        lifetime_value=100000.0,
    )
    db_session.add(c_a)
    db_session.commit()

    r_a = CustomerRetainer(
        workspace_id=workspace_a.id,
        customer_id=c_a.id,
        service_type="SEO_RETAINER",
        billing_frequency="MONTHLY",
        billing_amount=25000.0,
        monthly_mrr=25000.0,
        status="ACTIVE",
        renewal_date=datetime.now(UTC) + timedelta(days=20),
    )
    db_session.add(r_a)
    db_session.commit()

    # Workspace B setup
    c_b = Customer(
        workspace_id=workspace_b.id,
        company_name="Workspace B Client",
        status="ACTIVE",
        lifetime_value=50000.0,
    )
    db_session.add(c_b)
    db_session.commit()

    r_b = CustomerRetainer(
        workspace_id=workspace_b.id,
        customer_id=c_b.id,
        service_type="SMMA_RETAINER",
        billing_frequency="MONTHLY",
        billing_amount=10000.0,
        monthly_mrr=10000.0,
        status="ACTIVE",
        renewal_date=datetime.now(UTC) + timedelta(days=10),
    )
    db_session.add(r_b)
    db_session.commit()

    # Authenticate as Workspace A
    app.dependency_overrides[current_workspace_id] = lambda: workspace_a.id
    app.dependency_overrides[get_db] = lambda: db_session
    client_a = TestClient(app)

    # 1. Verify metrics only aggregate Workspace A
    res_m = client_a.get("/api/operations/success/metrics")
    assert res_m.status_code == 200
    m_a = res_m.json()
    assert m_a["total_customers"] == 1
    assert m_a["total_mrr"] == 25000.0
    assert m_a["total_arr"] == 300000.0
    assert m_a["active_retainers_count"] == 1

    # 2. Verify Cross-Workspace Retainer Read Blocked
    res_ret_list = client_a.get("/api/operations/retainers")
    ret_ids = [r["id"] for r in res_ret_list.json()]
    assert str(r_a.id) in ret_ids
    assert str(r_b.id) not in ret_ids

    # 3. Verify Cross-Workspace Retainer Mutation Blocked (404 Not Found)
    res_b_renew = client_a.patch(f"/api/operations/retainers/{r_b.id}/renew")
    assert res_b_renew.status_code == 404
