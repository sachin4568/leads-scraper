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
from backend.app.models import Deal, JobStageLog, Lead, LeadAction, ScrapeJob, WorkerHeartbeat, Workspace
from backend.app.models_phase2 import Base as Phase2Base
from backend.app.models_services import Base as ServicesBase
from backend.app.observability import (
    GLOBAL_PROVIDER_METRICS,
    FailureCategory,
    SafeJobRecoveryManager,
    StuckJobDetector,
    WorkerHeartbeatManager,
    classify_exception,
)


@pytest.fixture
def db_session():
    """Isolated in-memory SQLite database session for observability tests."""
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
    """Sets up two isolated workspaces with scrape jobs, leads, and workers."""
    ws_a = Workspace(name="Observability Tenant A")
    ws_b = Workspace(name="Observability Tenant B")
    db_session.add_all([ws_a, ws_b])
    db_session.commit()
    db_session.refresh(ws_a)
    db_session.refresh(ws_b)

    now = datetime.now(UTC)

    # Job A (Stuck running job)
    job_a = ScrapeJob(
        workspace_id=ws_a.id,
        niche="Clinics",
        state="Mumbai",
        target_lead_count=50,
        status="RUNNING",
        created_at=now - timedelta(minutes=15),
        updated_at=now - timedelta(minutes=10),  # > 5 minutes ago = stuck
    )
    # Job B (Completed job in Tenant B)
    job_b = ScrapeJob(
        workspace_id=ws_b.id,
        niche="Dentists",
        state="Delhi",
        target_lead_count=100,
        status="COMPLETED",
        created_at=now - timedelta(hours=1),
        updated_at=now - timedelta(minutes=50),
    )
    db_session.add_all([job_a, job_b])
    db_session.commit()
    db_session.refresh(job_a)
    db_session.refresh(job_b)

    # Leads for Job A
    lead_a = Lead(
        workspace_id=ws_a.id,
        job_id=job_a.id,
        business_name="City Heart Clinic",
        phone="+91 98000 11111",
        email="info@cityheart.in",
        genuineness_score=0.92,
        workflow_status="NEW",
    )
    db_session.add(lead_a)
    db_session.commit()
    db_session.refresh(lead_a)

    return {
        "ws_a": ws_a,
        "ws_b": ws_b,
        "job_a": job_a,
        "job_b": job_b,
        "lead_a": lead_a,
    }


def test_health_endpoint_healthy_state(db_session: Session):
    """Verifies that GET /health and GET /api/health return 200 with complete telemetry and no secrets."""
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "healthy"
    assert "version" in data
    assert "uptime_seconds" in data
    assert data["database"]["connected"] is True
    assert data["workers"]["status"] == "HEALTHY"
    # Ensure no secrets or connection strings are exposed
    assert "password" not in str(data).lower()
    assert "secret" not in str(data).lower()


def test_liveness_probe_independent_of_database():
    """Verifies that /api/health/live succeeds without touching the database."""
    client = TestClient(app)
    res = client.get("/api/health/live")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "live"
    assert "uptime_seconds" in data


def test_readiness_probe_success():
    """Verifies that /api/health/ready returns 200 when database connectivity is verified."""
    client = TestClient(app)
    res = client.get("/api/health/ready")
    assert res.status_code == 200
    assert res.json()["status"] == "ready"


def test_worker_heartbeat_creation_and_update(db_session: Session):
    """Verifies worker heartbeat registration and state updates via API."""
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    # 1. Post initial heartbeat
    res = client.post(
        "/api/operations/observability/heartbeat",
        json={
            "worker_id": "celery-worker-node-1",
            "status": "HEALTHY",
            "jobs_processed": 5,
            "jobs_failed": 0,
        },
    )
    assert res.status_code == 200
    assert res.json()["worker_id"] == "celery-worker-node-1"

    # 2. Verify worker in DB
    worker = db_session.scalar(
        select(WorkerHeartbeat).where(WorkerHeartbeat.worker_id == "celery-worker-node-1")
    )
    assert worker is not None
    assert worker.jobs_processed == 5
    assert worker.status == "HEALTHY"


def test_stale_worker_detection(db_session: Session):
    """Verifies that a worker whose heartbeat is older than 60 seconds is classified as STALE."""
    now = datetime.now(UTC)
    stale_worker = WorkerHeartbeat(
        worker_id="stale-worker-node-99",
        status="HEALTHY",
        last_heartbeat=now - timedelta(seconds=120),
        started_at=now - timedelta(hours=1),
    )
    db_session.add(stale_worker)
    db_session.commit()

    stale_list = WorkerHeartbeatManager.get_stale_workers(db_session, threshold_seconds=60)
    assert len(stale_list) >= 1
    assert any(w.worker_id == "stale-worker-node-99" for w in stale_list)


def test_failure_categorization():
    """Verifies that exception classifications return standard FailureCategory values."""
    assert classify_exception(Exception("HTTP 429 Too Many Requests")) == FailureCategory.PROVIDER_RATE_LIMIT
    assert classify_exception(Exception("Connection timed out")) == FailureCategory.PROVIDER_TIMEOUT
    assert classify_exception(Exception("SSRF blocked: private IP")) == FailureCategory.SSRF_BLOCKED
    assert classify_exception(Exception("getaddrinfo failed DNS name not found")) == FailureCategory.WEBSITE_DNS_ERROR
    assert classify_exception(Exception("SSL: CERTIFICATE_VERIFY_FAILED")) == FailureCategory.WEBSITE_SSL_ERROR


def test_stuck_job_detection(multi_tenant_setup: dict):
    """Verifies that a job inactive for > 5 minutes is marked as stuck with a descriptive reason."""
    job_a = multi_tenant_setup["job_a"]
    is_stuck, reason = StuckJobDetector.evaluate_job_stuck(job_a)

    assert is_stuck is True
    assert "No progress or telemetry heartbeat" in reason


def test_safe_job_recovery(db_session: Session, multi_tenant_setup: dict):
    """Verifies that recovering a stuck job transitions it to PENDING and preserves existing leads."""
    ws_a = multi_tenant_setup["ws_a"]
    job_a = multi_tenant_setup["job_a"]
    lead_a = multi_tenant_setup["lead_a"]

    app.dependency_overrides[current_workspace_id] = lambda: ws_a.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    res = client.post(f"/api/operations/observability/jobs/{job_a.id}/recover")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "RECOVERED"
    assert data["persisted_leads"] == 1

    # Verify job state in DB
    db_session.expire_all()
    reloaded_job = db_session.get(ScrapeJob, job_a.id)
    assert reloaded_job.status == "PENDING"
    assert reloaded_job.completion_reason == "RECOVERED_BY_OPERATOR"

    # Verify lead was preserved without duplication
    leads_count = db_session.scalar(
        select(func.count()).select_from(Lead).where(
            Lead.job_id == job_a.id,
            Lead.workspace_id == ws_a.id,
        )
    )
    assert leads_count == 1


def test_cross_workspace_job_diagnostics_and_recovery_protection(db_session: Session, multi_tenant_setup: dict):
    """Verifies that Tenant A cannot inspect or recover Tenant B's scrape jobs."""
    ws_a = multi_tenant_setup["ws_a"]
    job_b = multi_tenant_setup["job_b"]

    app.dependency_overrides[current_workspace_id] = lambda: ws_a.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    # 1. Diagnostics IDOR attempt
    res_diag = client.get(f"/api/operations/observability/jobs/{job_b.id}/diagnostics")
    assert res_diag.status_code == 404

    # 2. Recovery IDOR attempt
    res_rec = client.post(f"/api/operations/observability/jobs/{job_b.id}/recover")
    assert res_rec.status_code == 404


def test_observability_dashboard_metrics(db_session: Session, multi_tenant_setup: dict):
    """Verifies that the operational dashboard returns scoped telemetry and failure logs."""
    ws_a = multi_tenant_setup["ws_a"]
    job_a = multi_tenant_setup["job_a"]

    # Add a failure stage log for Tenant A
    stage_fail = JobStageLog(
        job_id=job_a.id,
        workspace_id=ws_a.id,
        stage="DISCOVERY",
        status="FAILED",
        error_category="PROVIDER_TIMEOUT",
        error_detail="Overpass endpoint timed out after 3 retries",
    )
    db_session.add(stage_fail)
    db_session.commit()

    # Record some global provider telemetry
    GLOBAL_PROVIDER_METRICS.record_osm_request(duration_ms=120.0, status="SUCCESS")
    GLOBAL_PROVIDER_METRICS.record_web_enrichment(duration_ms=250.0, pages_count=2, bytes_count=15000, is_success=True)

    app.dependency_overrides[current_workspace_id] = lambda: ws_a.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    res = client.get("/api/operations/observability/dashboard")
    assert res.status_code == 200
    data = res.json()

    assert data["job_health"]["total_jobs"] == 1
    assert data["job_health"]["stuck_count"] == 1
    assert len(data["recent_failures"]) >= 1
    assert data["recent_failures"][0]["error_category"] == "PROVIDER_TIMEOUT"
    assert data["provider_telemetry"]["osm_overpass"]["requests_total"] >= 1
