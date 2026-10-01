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
from backend.app.models import Deal, EvidenceRecord, Lead, LeadAction, ScrapeJob, Workspace
from backend.app.models_phase2 import Base as Phase2Base
from backend.app.models_services import Base as ServicesBase
from backend.app.security import create_access_token, validate_outbound_url


@pytest.fixture
def db_session():
    """Isolated in-memory SQLite database session for security tests."""
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
def multi_tenant_setup(db_session: Session):
    """Sets up two strictly isolated workspaces: Workspace A (Tenant A) and Workspace B (Tenant B)."""
    ws_a = Workspace(name="Tenant A - Alpha Corp")
    ws_b = Workspace(name="Tenant B - Beta Ltd")
    db_session.add_all([ws_a, ws_b])
    db_session.commit()
    db_session.refresh(ws_a)
    db_session.refresh(ws_b)

    now = datetime.now(UTC)

    # Tenant A Lead & Deal
    lead_a = Lead(
        workspace_id=ws_a.id,
        business_name="Alpha Medical Center",
        phone="+91 98200 11111",
        email="info@alphamedical.in",
        website="https://alphamedical.in",
        genuineness_score=0.95,
        workflow_status="QUALIFIED",
        created_at=now - timedelta(days=2),
    )
    # Tenant B Lead & Deal
    lead_b = Lead(
        workspace_id=ws_b.id,
        business_name="Beta Dental Studio",
        phone="+91 98200 22222",
        email="contact@betadental.in",
        website="https://betadental.in",
        genuineness_score=0.90,
        workflow_status="CONVERTED",
        created_at=now - timedelta(days=3),
    )
    db_session.add_all([lead_a, lead_b])
    db_session.commit()
    db_session.refresh(lead_a)
    db_session.refresh(lead_b)

    # Evidence for A & B
    ev_a = EvidenceRecord(
        workspace_id=ws_a.id,
        lead_id=lead_a.id,
        field_name="lead_intelligence",
        status="HIGH",
        confidence_score=90,
        source="LEAD_INTELLIGENCE_ENGINE",
        details={"overall_opportunity_score": 85, "opportunity_category": "HIGH"},
    )
    ev_b = EvidenceRecord(
        workspace_id=ws_b.id,
        lead_id=lead_b.id,
        field_name="lead_intelligence",
        status="VERY_HIGH",
        confidence_score=95,
        source="LEAD_INTELLIGENCE_ENGINE",
        details={"overall_opportunity_score": 95, "opportunity_category": "VERY_HIGH"},
    )
    db_session.add_all([ev_a, ev_b])

    # Actions for A & B
    act_a = LeadAction(
        workspace_id=ws_a.id,
        lead_id=lead_a.id,
        channel="WHATSAPP",
        outcome="INTERESTED",
        notes="Tenant A action note.",
    )
    act_b = LeadAction(
        workspace_id=ws_b.id,
        lead_id=lead_b.id,
        channel="EMAIL",
        outcome="CONVERTED",
        notes="Tenant B action note.",
    )
    db_session.add_all([act_a, act_b])

    # Deals for A & B
    deal_a = Deal(
        workspace_id=ws_a.id,
        lead_id=lead_a.id,
        title="Alpha - SEO Retainer",
        service_type="SEO",
        deal_value=50000.0,
        stage="PROPOSAL",
        probability=0.60,
    )
    deal_b = Deal(
        workspace_id=ws_b.id,
        lead_id=lead_b.id,
        title="Beta - Web Modernization",
        service_type="WEBSITE_DEVELOPMENT",
        deal_value=120000.0,
        stage="WON",
        probability=1.00,
    )
    db_session.add_all([deal_a, deal_b])

    # ScrapeJob for A & B
    job_a = ScrapeJob(
        workspace_id=ws_a.id,
        niche="Clinics",
        state="Mumbai",
        target_lead_count=50,
        status="RUNNING",
    )
    job_b = ScrapeJob(
        workspace_id=ws_b.id,
        niche="Dentists",
        state="Delhi",
        target_lead_count=100,
        status="COMPLETED",
    )
    db_session.add_all([job_a, job_b])

    db_session.commit()
    db_session.refresh(deal_a)
    db_session.refresh(deal_b)
    db_session.refresh(job_a)
    db_session.refresh(job_b)

    return {
        "ws_a": ws_a,
        "ws_b": ws_b,
        "lead_a": lead_a,
        "lead_b": lead_b,
        "deal_a": deal_a,
        "deal_b": deal_b,
        "job_a": job_a,
        "job_b": job_b,
        "act_a": act_a,
        "act_b": act_b,
    }


def test_cross_workspace_lead_read_blocked(db_session: Session, multi_tenant_setup: dict):
    """Verifies that Tenant A cannot read Tenant B's lead via operations or core endpoints."""
    ws_a = multi_tenant_setup["ws_a"]
    lead_b = multi_tenant_setup["lead_b"]

    app.dependency_overrides[current_workspace_id] = lambda: ws_a.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    # 1. Operations Lead Detail IDOR attempt
    res = client.get(f"/api/operations/leads/{lead_b.id}")
    assert res.status_code == 404
    assert res.json()["detail"] == "Lead not found"

    # 2. Core Lead Detail IDOR attempt
    res_core = client.get(f"/api/leads/{lead_b.id}/evidence")
    assert res_core.status_code == 404


def test_cross_workspace_lead_update_blocked(db_session: Session, multi_tenant_setup: dict):
    """Verifies that Tenant A cannot modify Tenant B's lead workflow status."""
    ws_a = multi_tenant_setup["ws_a"]
    lead_b = multi_tenant_setup["lead_b"]

    app.dependency_overrides[current_workspace_id] = lambda: ws_a.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    res = client.patch(
        f"/api/operations/leads/{lead_b.id}/workflow",
        json={"workflow_status": "LOST"},
    )
    assert res.status_code == 404

    # Confirm Tenant B lead unchanged
    db_session.expire_all()
    reloaded_b = db_session.get(Lead, lead_b.id)
    assert reloaded_b.workflow_status == "CONVERTED"


def test_cross_workspace_lead_action_blocked(db_session: Session, multi_tenant_setup: dict):
    """Verifies that Tenant A cannot record outreach actions against Tenant B's lead."""
    ws_a = multi_tenant_setup["ws_a"]
    lead_b = multi_tenant_setup["lead_b"]

    app.dependency_overrides[current_workspace_id] = lambda: ws_a.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    res = client.post(
        f"/api/operations/leads/{lead_b.id}/actions",
        json={"channel": "WHATSAPP", "outcome": "CONTACTED", "notes": "Unauthorized attempt"},
    )
    assert res.status_code == 404

    res_history = client.get(f"/api/operations/leads/{lead_b.id}/actions")
    assert res_history.status_code == 404


def test_cross_workspace_timeline_blocked(db_session: Session, multi_tenant_setup: dict):
    """Verifies that Tenant A cannot view Tenant B's activity timeline."""
    ws_a = multi_tenant_setup["ws_a"]
    lead_b = multi_tenant_setup["lead_b"]

    app.dependency_overrides[current_workspace_id] = lambda: ws_a.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    res = client.get(f"/api/operations/leads/{lead_b.id}/timeline")
    assert res.status_code == 404


def test_cross_workspace_deal_read_and_update_blocked(db_session: Session, multi_tenant_setup: dict):
    """Verifies that Tenant A cannot view or update Tenant B's CRM deals."""
    ws_a = multi_tenant_setup["ws_a"]
    deal_b = multi_tenant_setup["deal_b"]

    app.dependency_overrides[current_workspace_id] = lambda: ws_a.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    # 1. Read Deal
    res_get = client.get(f"/api/operations/deals/{deal_b.id}")
    assert res_get.status_code == 404

    # 2. Update Deal Stage / Value
    res_patch = client.patch(
        f"/api/operations/deals/{deal_b.id}",
        json={"stage": "LOST", "deal_value": 0.0, "win_loss_reason": "Malicious override attempt"},
    )
    assert res_patch.status_code == 404

    # Verify Deal B remains intact
    db_session.expire_all()
    reloaded_deal_b = db_session.get(Deal, deal_b.id)
    assert reloaded_deal_b.stage == "WON"
    assert reloaded_deal_b.deal_value == 120000.0


def test_cross_workspace_deal_creation_with_foreign_lead_blocked(db_session: Session, multi_tenant_setup: dict):
    """Verifies that Tenant A cannot create a deal attached to Tenant B's lead."""
    ws_a = multi_tenant_setup["ws_a"]
    lead_b = multi_tenant_setup["lead_b"]

    app.dependency_overrides[current_workspace_id] = lambda: ws_a.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    res = client.post(
        "/api/operations/deals",
        json={
            "lead_id": str(lead_b.id),
            "title": "Unauthorized Deal Attempt",
            "service_type": "WEBSITE_DEVELOPMENT",
            "deal_value": 75000.0,
            "stage": "QUALIFIED",
        },
    )
    assert res.status_code == 404


def test_cross_workspace_scrape_job_access_blocked(db_session: Session, multi_tenant_setup: dict):
    """Verifies that Tenant A cannot inspect or control Tenant B's scrape jobs."""
    ws_a = multi_tenant_setup["ws_a"]
    job_b = multi_tenant_setup["job_b"]

    app.dependency_overrides[current_workspace_id] = lambda: ws_a.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    # 1. Inspect Job
    res_get = client.get(f"/api/scrape-jobs/{job_b.id}")
    assert res_get.status_code == 404

    # 2. Cancel Job
    res_cancel = client.post(f"/api/scrape-jobs/{job_b.id}/cancel")
    assert res_cancel.status_code == 404

    # 3. Progress check
    res_prog = client.get(f"/api/scrape/progress/{job_b.id}")
    assert res_prog.status_code == 404


def test_analytics_multi_tenant_isolation(db_session: Session, multi_tenant_setup: dict):
    """Verifies that Workspace A's analytics never leak Workspace B's metrics, revenue, or deals."""
    ws_a = multi_tenant_setup["ws_a"]
    ws_b = multi_tenant_setup["ws_b"]

    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    # Workspace A View
    app.dependency_overrides[current_workspace_id] = lambda: ws_a.id
    res_a = client.get("/api/analytics/overview?timeframe=all_time")
    assert res_a.status_code == 200
    data_a = res_a.json()

    assert data_a["kpis"]["total_leads"] == 1
    assert data_a["kpis"]["won_leads"] == 0
    assert data_a["kpis"]["won_revenue"] == 0.0
    assert data_a["kpis"]["total_pipeline_value"] == 50000.0
    assert data_a["kpis"]["weighted_pipeline_value"] == 30000.0

    # Workspace B View
    app.dependency_overrides[current_workspace_id] = lambda: ws_b.id
    res_b = client.get("/api/analytics/overview?timeframe=all_time")
    assert res_b.status_code == 200
    data_b = res_b.json()

    assert data_b["kpis"]["total_leads"] == 1
    assert data_b["kpis"]["won_leads"] == 1
    assert data_b["kpis"]["won_revenue"] == 120000.0
    assert data_b["kpis"]["total_pipeline_value"] == 0.0


def test_bulk_operation_cross_workspace_injection_blocked(db_session: Session, multi_tenant_setup: dict):
    """Verifies that a bulk workflow update containing foreign lead IDs is rejected with 403 Forbidden."""
    ws_a = multi_tenant_setup["ws_a"]
    lead_a = multi_tenant_setup["lead_a"]
    lead_b = multi_tenant_setup["lead_b"]

    app.dependency_overrides[current_workspace_id] = lambda: ws_a.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    # Attempt bulk update mixing Tenant A's lead with Tenant B's lead
    res = client.patch(
        "/api/operations/leads/bulk-workflow",
        json={
            "lead_ids": [str(lead_a.id), str(lead_b.id)],
            "workflow_status": "DISMISSED",
        },
    )
    assert res.status_code == 403
    assert "Cross-workspace operation forbidden" in res.json()["detail"]

    # Verify neither lead was mutated
    db_session.expire_all()
    assert db_session.get(Lead, lead_a.id).workflow_status == "QUALIFIED"
    assert db_session.get(Lead, lead_b.id).workflow_status == "CONVERTED"


def test_ssrf_protection_blocked_ranges():
    """Verifies SSRF guard blocks local, private, link-local, and cloud metadata addresses."""
    blocked_urls = [
        "http://127.0.0.1:8000/admin",
        "http://localhost:3000",
        "https://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/internal",
        "https://192.168.1.1/router",
        "http://172.16.0.5/api",
        "http://[::1]/status",
        "ftp://example.com/file",
        "file:///etc/passwd",
    ]

    for url in blocked_urls:
        with pytest.raises(ValueError):
            validate_outbound_url(url, allow_http=True)


def test_input_validation_deal_boundaries(db_session: Session, multi_tenant_setup: dict):
    """Verifies that invalid payload parameters (negative values, invalid stages) are rejected."""
    ws_a = multi_tenant_setup["ws_a"]
    lead_a = multi_tenant_setup["lead_a"]

    app.dependency_overrides[current_workspace_id] = lambda: ws_a.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    # 1. Negative deal value
    res_neg = client.post(
        "/api/operations/deals",
        json={
            "lead_id": str(lead_a.id),
            "title": "Negative Deal",
            "deal_value": -5000.0,
            "stage": "QUALIFIED",
        },
    )
    assert res_neg.status_code == 422

    # 2. Probability > 1.0
    res_prob = client.post(
        "/api/operations/deals",
        json={
            "lead_id": str(lead_a.id),
            "title": "Invalid Prob Deal",
            "deal_value": 50000.0,
            "probability": 1.5,
            "stage": "QUALIFIED",
        },
    )
    assert res_prob.status_code == 422

    # 3. Invalid stage enum
    res_stage = client.post(
        "/api/operations/deals",
        json={
            "lead_id": str(lead_a.id),
            "title": "Bad Stage Deal",
            "deal_value": 50000.0,
            "stage": "INVALID_STAGE_NAME",
        },
    )
    assert res_stage.status_code == 422
