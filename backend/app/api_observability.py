from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select, text
from sqlalchemy.orm import Session

from backend.app.api import current_workspace_id
from backend.app.config import get_settings
from backend.app.database import engine, get_db
from backend.app.models import Deal, JobStageLog, Lead, LeadAction, ScrapeJob, WorkerHeartbeat
from backend.app.observability import (
    GLOBAL_PROVIDER_METRICS,
    FailureCategory,
    SafeJobRecoveryManager,
    StuckJobDetector,
    WorkerHeartbeatManager,
)

router = APIRouter(tags=["Production Observability & Recovery"])

_APP_START_TIME = time.time()


# ─── Health & Probe Schemas ──────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    app_env: str
    version: str = "2.0.0"
    uptime_seconds: float
    timestamp: datetime
    database: dict[str, Any]
    workers: dict[str, Any]


class HeartbeatPayload(BaseModel):
    worker_id: str
    status: str = "HEALTHY"
    current_job_id: uuid.UUID | None = None
    jobs_processed: int | None = None
    jobs_failed: int | None = None
    error_message: str | None = None
    details: dict | None = None


# ─── 1. Health Endpoints ─────────────────────────────────────────────────────

@router.get("/health")
def get_production_health(db: Session = Depends(get_db)) -> JSONResponse:
    """Production health check returning overall application, database, and worker status."""
    uptime = round(time.time() - _APP_START_TIME, 2)
    now = datetime.now(UTC)

    # Test DB connectivity
    db_ok = False
    db_latency_ms = 0.0
    try:
        t0 = time.perf_counter()
        db.execute(text("SELECT 1"))
        db_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        db_ok = True
    except Exception as err:
        db_ok = False

    # Check active workers
    active_workers_count = 0
    stale_workers_count = 0
    try:
        cutoff = now - timedelta(seconds=60)
        active_workers_count = db.scalar(
            select(func.count()).select_from(WorkerHeartbeat).where(WorkerHeartbeat.last_heartbeat >= cutoff)
        ) or 0
        stale_workers_count = db.scalar(
            select(func.count()).select_from(WorkerHeartbeat).where(
                WorkerHeartbeat.last_heartbeat < cutoff,
                WorkerHeartbeat.status.in_(["HEALTHY", "BUSY"]),
            )
        ) or 0
    except Exception:
        pass

    is_healthy = db_ok
    status_code = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    payload = {
        "status": "healthy" if is_healthy else "unhealthy",
        "app_env": get_settings().app_env,
        "version": "2.0.0",
        "uptime_seconds": uptime,
        "timestamp": now.isoformat(),
        "database": {
            "connected": db_ok,
            "latency_ms": db_latency_ms,
        },
        "workers": {
            "active_count": active_workers_count,
            "stale_count": stale_workers_count,
            "status": "HEALTHY" if stale_workers_count == 0 else "DEGRADED",
        },
    }
    return JSONResponse(content=payload, status_code=status_code)


@router.get("/health/live")
def get_liveness_probe() -> JSONResponse:
    """Liveness probe: returns 200 if the app process is running, independent of database state."""
    return JSONResponse(
        content={"status": "live", "uptime_seconds": round(time.time() - _APP_START_TIME, 2)},
        status_code=status.HTTP_200_OK,
    )


@router.get("/health/ready")
def get_readiness_probe() -> JSONResponse:
    """Readiness probe: validates critical dependencies (database) to accept production traffic."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return JSONResponse(
            content={"status": "ready", "database": "connected"},
            status_code=status.HTTP_200_OK,
        )
    except Exception as err:
        return JSONResponse(
            content={"status": "not_ready", "database": "disconnected"},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


# ─── 2. Operational Observability Dashboard ──────────────────────────────────

@router.get("/operations/observability/dashboard")
def get_observability_dashboard(
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Provides consolidated operational health, job diagnostics, worker heartbeats, and provider telemetry."""
    now = datetime.now(UTC)

    # 1. Job Health Breakdown
    jobs = db.scalars(
        select(ScrapeJob).where(ScrapeJob.workspace_id == workspace_id)
    ).all()

    running_jobs = 0
    completed_jobs = 0
    failed_jobs = 0
    partial_jobs = 0
    stuck_jobs = []

    for j in jobs:
        if j.status == "COMPLETED":
            completed_jobs += 1
        elif j.status == "FAILED":
            failed_jobs += 1
        elif j.status == "PARTIAL":
            partial_jobs += 1
        elif j.status in ["RUNNING", "PENDING"]:
            running_jobs += 1
            is_stuck, reason = StuckJobDetector.evaluate_job_stuck(j, now=now)
            if is_stuck:
                stuck_jobs.append({
                    "job_id": str(j.id),
                    "niche": j.niche,
                    "state": j.state,
                    "status": j.status,
                    "progress_percent": j.progress_percent,
                    "reason": reason,
                    "updated_at": j.updated_at.isoformat() if j.updated_at else None,
                })

    # 2. Worker Health
    workers_raw = db.scalars(select(WorkerHeartbeat).order_by(desc(WorkerHeartbeat.last_heartbeat))).all()
    workers_data = []
    cutoff = now - timedelta(seconds=60)
    for w in workers_raw:
        hb_time = w.last_heartbeat
        if hb_time.tzinfo is None:
            hb_time = hb_time.replace(tzinfo=UTC)
        is_stale = hb_time < cutoff and w.status in ["HEALTHY", "BUSY"]
        workers_data.append({
            "worker_id": w.worker_id,
            "status": "STALE" if is_stale else w.status,
            "current_job_id": str(w.current_job_id) if w.current_job_id else None,
            "jobs_processed": w.jobs_processed,
            "jobs_failed": w.jobs_failed,
            "last_heartbeat": hb_time.isoformat(),
            "started_at": w.started_at.isoformat() if w.started_at else hb_time.isoformat(),
            "last_completed_at": w.last_completed_at.isoformat() if w.last_completed_at else None,
            "last_error_at": w.last_error_at.isoformat() if w.last_error_at else None,
            "last_error_message": w.last_error_message,
        })

    # 3. Recent Failure Logs
    recent_failures = db.scalars(
        select(JobStageLog).where(
            JobStageLog.workspace_id == workspace_id,
            JobStageLog.status == "FAILED",
        ).order_by(desc(JobStageLog.started_at)).limit(10)
    ).all()
    failure_logs = [
        {
            "id": str(f.id),
            "job_id": str(f.job_id),
            "stage": f.stage,
            "error_category": f.error_category or FailureCategory.UNKNOWN_ERROR,
            "error_detail": f.error_detail,
            "retry_count": f.retry_count,
            "started_at": f.started_at.isoformat(),
        }
        for f in recent_failures
    ]

    # 4. Provider Telemetry
    avg_osm_lat = (
        round(GLOBAL_PROVIDER_METRICS.osm_total_latency_ms / GLOBAL_PROVIDER_METRICS.osm_requests_total, 2)
        if GLOBAL_PROVIDER_METRICS.osm_requests_total > 0
        else 0.0
    )
    avg_web_lat = (
        round(GLOBAL_PROVIDER_METRICS.web_enrichment_total_latency_ms / GLOBAL_PROVIDER_METRICS.web_enrichment_domains_attempted, 2)
        if GLOBAL_PROVIDER_METRICS.web_enrichment_domains_attempted > 0
        else 0.0
    )

    provider_telemetry = {
        "osm_overpass": {
            "requests_total": GLOBAL_PROVIDER_METRICS.osm_requests_total,
            "success_total": GLOBAL_PROVIDER_METRICS.osm_success_total,
            "timeouts": GLOBAL_PROVIDER_METRICS.osm_timeout_total,
            "rate_limits_429": GLOBAL_PROVIDER_METRICS.osm_rate_limit_total,
            "errors": GLOBAL_PROVIDER_METRICS.osm_error_total,
            "avg_latency_ms": avg_osm_lat,
        },
        "website_enrichment": {
            "domains_attempted": GLOBAL_PROVIDER_METRICS.web_enrichment_domains_attempted,
            "success_total": GLOBAL_PROVIDER_METRICS.web_enrichment_success_total,
            "http_errors": GLOBAL_PROVIDER_METRICS.web_enrichment_http_errors,
            "dns_errors": GLOBAL_PROVIDER_METRICS.web_enrichment_dns_errors,
            "ssl_errors": GLOBAL_PROVIDER_METRICS.web_enrichment_ssl_errors,
            "pages_fetched": GLOBAL_PROVIDER_METRICS.web_enrichment_pages_fetched,
            "bytes_downloaded": GLOBAL_PROVIDER_METRICS.web_enrichment_bytes_downloaded,
            "avg_latency_ms": avg_web_lat,
        },
    }

    return {
        "workspace_id": str(workspace_id),
        "timestamp": now.isoformat(),
        "job_health": {
            "total_jobs": len(jobs),
            "running": running_jobs,
            "completed": completed_jobs,
            "failed": failed_jobs,
            "partial": partial_jobs,
            "stuck_count": len(stuck_jobs),
            "stuck_jobs": stuck_jobs,
        },
        "workers": {
            "total_count": len(workers_data),
            "workers": workers_data,
        },
        "recent_failures": failure_logs,
        "provider_telemetry": provider_telemetry,
    }


# ─── 3. Safe Job Recovery & Diagnostics Endpoints ────────────────────────────

@router.get("/operations/observability/jobs/{job_id}/diagnostics")
def get_job_diagnostics(
    job_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieves end-to-end execution stage logs, error categories, and recovery state for a job."""
    job = db.scalar(
        select(ScrapeJob).where(
            ScrapeJob.id == job_id,
            ScrapeJob.workspace_id == workspace_id,
        )
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    is_stuck, stuck_reason = StuckJobDetector.evaluate_job_stuck(job)

    stage_logs = db.scalars(
        select(JobStageLog).where(
            JobStageLog.job_id == job.id,
            JobStageLog.workspace_id == workspace_id,
        ).order_by(JobStageLog.started_at)
    ).all()

    persisted_leads = db.scalar(
        select(func.count()).select_from(Lead).where(
            Lead.job_id == job.id,
            Lead.workspace_id == workspace_id,
            Lead.deleted_at.is_(None),
        )
    ) or 0

    return {
        "job_id": str(job.id),
        "workspace_id": str(job.workspace_id),
        "niche": job.niche,
        "state": job.state,
        "status": job.status,
        "progress_percent": job.progress_percent,
        "leads_scraped": job.leads_scraped,
        "discovered_count": job.discovered_count,
        "valid_count": job.valid_count,
        "persisted_leads_in_db": persisted_leads,
        "is_stuck": is_stuck,
        "stuck_reason": stuck_reason,
        "error_message": job.error_message,
        "completion_reason": job.completion_reason,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "stages": [
            {
                "id": str(s.id),
                "stage": s.stage,
                "status": s.status,
                "duration_ms": s.duration_ms,
                "error_category": s.error_category,
                "error_detail": s.error_detail,
                "retry_count": s.retry_count,
                "metrics": s.metrics,
                "started_at": s.started_at.isoformat(),
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            }
            for s in stage_logs
        ],
    }


@router.post("/operations/observability/jobs/{job_id}/recover")
def recover_scrape_job(
    job_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Safely recovers a stuck or failed scrape job, preserving idempotency and existing leads."""
    try:
        result = SafeJobRecoveryManager.recover_job(
            db=db,
            job_id=job_id,
            workspace_id=workspace_id,
        )
        return result
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(val_err))


# ─── 4. Worker Heartbeat Registration Endpoint ───────────────────────────────

@router.post("/operations/observability/heartbeat")
def post_worker_heartbeat(
    payload: HeartbeatPayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Receives and records worker lifecycle heartbeats."""
    worker = WorkerHeartbeatManager.record_heartbeat(
        db=db,
        worker_id=payload.worker_id,
        status=payload.status,
        current_job_id=payload.current_job_id,
        jobs_processed=payload.jobs_processed,
        jobs_failed=payload.jobs_failed,
        error_message=payload.error_message,
        details=payload.details,
    )
    return {
        "status": "RECORDED",
        "worker_id": worker.worker_id,
        "last_heartbeat": worker.last_heartbeat.isoformat(),
    }
