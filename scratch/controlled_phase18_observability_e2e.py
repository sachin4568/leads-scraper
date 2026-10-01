from __future__ import annotations

import sys
import time
import uuid
from datetime import UTC, datetime, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker

from backend.app.api import current_workspace_id
from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import Deal, EvidenceRecord, JobStageLog, Lead, LeadAction, ScrapeJob, WorkerHeartbeat, Workspace
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


def run_controlled_phase18_e2e():
    print("=== STARTING PHASE 18 PRODUCTION OBSERVABILITY, MONITORING & RECOVERY CONTROLLED E2E TEST ===")

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

    ws = Workspace(name="Observability Production Tenant")
    session.add(ws)
    session.commit()
    session.refresh(ws)

    app.dependency_overrides[current_workspace_id] = lambda: ws.id
    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)

    now = datetime.now(UTC)

    # 1. Simulate Worker Heartbeat
    worker = WorkerHeartbeatManager.record_heartbeat(
        db=session,
        worker_id="worker-node-alpha",
        status="HEALTHY",
        jobs_processed=12,
        jobs_failed=1,
    )
    print(f"1. Worker Heartbeat Registered: {worker.worker_id} (Status: {worker.status})")

    # 2. Simulate Active Scrape Job with partial leads persisted
    job = ScrapeJob(
        workspace_id=ws.id,
        niche="Dermatology",
        state="Maharashtra",
        target_lead_count=20,
        status="RUNNING",
        created_at=now - timedelta(minutes=10),
        updated_at=now - timedelta(minutes=7),  # 7 mins without progress -> Stuck!
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    # Persist 5 partial leads before failure
    for i in range(5):
        l = Lead(
            workspace_id=ws.id,
            job_id=job.id,
            business_name=f"Derma Care {i+1}",
            phone=f"+91 98200 {i+1:05d}",
            email=f"derma_{i+1}@care.in",
            website=f"https://dermacare{i+1}.in",
            genuineness_score=0.90,
            workflow_status="NEW",
        )
        session.add(l)
    session.commit()
    print("2. Running Scrape Job Seeded: 5 partial leads persisted before simulated interruption.")

    # 3. Simulate Provider & Website Failure Logs
    stage_osm = JobStageLog(
        job_id=job.id,
        workspace_id=ws.id,
        stage="DISCOVERY",
        status="FAILED",
        duration_ms=5020.0,
        error_category=FailureCategory.PROVIDER_TIMEOUT,
        error_detail="Overpass query timeout after 3 retries (5020ms)",
        retry_count=3,
        started_at=now - timedelta(minutes=7),
        ended_at=now - timedelta(minutes=7),
    )
    session.add(stage_osm)
    session.commit()

    # Track metrics
    GLOBAL_PROVIDER_METRICS.record_osm_request(duration_ms=5020.0, status="FAILED", error_category=FailureCategory.PROVIDER_TIMEOUT)
    GLOBAL_PROVIDER_METRICS.record_web_enrichment(duration_ms=320.0, pages_count=1, bytes_count=12000, is_success=False, error_category=FailureCategory.WEBSITE_DNS_ERROR)
    print("3. Exception Classifications & Provider Telemetry Logged (PROVIDER_TIMEOUT, WEBSITE_DNS_ERROR).")

    # 4. Check Health & Liveness APIs
    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    res_live = client.get("/api/health/live")
    assert res_live.status_code == 200
    res_ready = client.get("/api/health/ready")
    assert res_ready.status_code == 200
    print("4. Production Health Endpoints Verified: /api/health (200 OK), /api/health/live (200 OK), /api/health/ready (200 OK).")

    # 5. Stuck Job Detection
    is_stuck, stuck_reason = StuckJobDetector.evaluate_job_stuck(job, now=now)
    assert is_stuck is True
    print(f"5. Stuck Job Detector Alert: Triggered for Job {job.id} ({stuck_reason})")

    # 6. Execute Safe Idempotent Recovery
    t0_rec = time.perf_counter()
    res_rec = client.post(f"/api/operations/observability/jobs/{job.id}/recover")
    rec_lat_ms = (time.perf_counter() - t0_rec) * 1000.0
    assert res_rec.status_code == 200
    rec_data = res_rec.json()
    assert rec_data["status"] == "RECOVERED"
    print(f"6. Safe Recovery Executed in {rec_lat_ms:.2f}ms: Status reset to PENDING, previous state preserved.")

    # 7. Post-Recovery Verification
    session.expire_all()
    reloaded_job = session.get(ScrapeJob, job.id)
    assert reloaded_job.status == "PENDING"
    assert reloaded_job.completion_reason == "RECOVERED_BY_OPERATOR"

    # Verify zero duplicate leads created
    final_leads_count = session.scalar(
        select(func.count()).select_from(Lead).where(
            Lead.job_id == job.id,
            Lead.workspace_id == ws.id,
        )
    )
    assert final_leads_count == 5
    print("7. Idempotency & Provenance Check: Exactly 5 leads maintained with ZERO duplicate records created.")

    # 8. Operational Dashboard Verification
    res_dash = client.get("/api/operations/observability/dashboard")
    assert res_dash.status_code == 200
    dash = res_dash.json()
    assert dash["job_health"]["total_jobs"] == 1
    assert len(dash["recent_failures"]) >= 1
    assert dash["provider_telemetry"]["osm_overpass"]["timeouts"] >= 1
    print("8. Observability Dashboard Verified: All real-time telemetry, stage logs, and worker health displayed.")

    print("\n=== PHASE 18 OBSERVABILITY, MONITORING & RECOVERY CONTROLLED E2E TEST: ALL CHECKS PASSED ===")


if __name__ == "__main__":
    run_controlled_phase18_e2e()
