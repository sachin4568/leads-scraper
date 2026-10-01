from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.app.models import AuditLog, JobStageLog, Lead, ScrapeJob, WorkerHeartbeat

logger = logging.getLogger(__name__)


class FailureCategory(str, Enum):
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_RATE_LIMIT = "PROVIDER_RATE_LIMIT"
    PROVIDER_HTTP_ERROR = "PROVIDER_HTTP_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    SSRF_BLOCKED = "SSRF_BLOCKED"
    WEBSITE_TIMEOUT = "WEBSITE_TIMEOUT"
    WEBSITE_HTTP_ERROR = "WEBSITE_HTTP_ERROR"
    WEBSITE_DNS_ERROR = "WEBSITE_DNS_ERROR"
    WEBSITE_SSL_ERROR = "WEBSITE_SSL_ERROR"
    ENRICHMENT_ERROR = "ENRICHMENT_ERROR"
    CLASSIFICATION_ERROR = "CLASSIFICATION_ERROR"
    INTELLIGENCE_ERROR = "INTELLIGENCE_ERROR"
    WORKER_CRASH = "WORKER_CRASH"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


def classify_exception(err: Exception) -> FailureCategory:
    """Classifies runtime exceptions deterministically into standard operational failure categories."""
    msg = str(err).lower()
    err_type = type(err).__name__.lower()

    if "ssrf" in msg:
        return FailureCategory.SSRF_BLOCKED
    if "429" in msg or "rate limit" in msg or "too many requests" in msg:
        return FailureCategory.PROVIDER_RATE_LIMIT
    if "timeout" in msg or "timed out" in msg:
        if "website" in msg or "http" in msg:
            return FailureCategory.WEBSITE_TIMEOUT
        return FailureCategory.PROVIDER_TIMEOUT
    if "dns" in msg or "name resolution" in msg or "getaddrinfo" in msg:
        return FailureCategory.WEBSITE_DNS_ERROR
    if "ssl" in msg or "certificate" in msg or "tls" in msg:
        return FailureCategory.WEBSITE_SSL_ERROR
    if "http" in msg or "status code" in msg or "4" in msg or "5" in msg:
        if "website" in msg:
            return FailureCategory.WEBSITE_HTTP_ERROR
        return FailureCategory.PROVIDER_HTTP_ERROR
    if "database" in msg or "sql" in msg or "integrity" in msg or "operationalerror" in err_type:
        return FailureCategory.DATABASE_ERROR
    if "validation" in msg or "valueerror" in err_type or "pydantic" in err_type:
        return FailureCategory.VALIDATION_ERROR
    if "enrichment" in msg:
        return FailureCategory.ENRICHMENT_ERROR
    if "classification" in msg:
        return FailureCategory.CLASSIFICATION_ERROR
    if "intelligence" in msg:
        return FailureCategory.INTELLIGENCE_ERROR
    return FailureCategory.UNKNOWN_ERROR


@dataclass
class ProviderMetricsTracker:
    """In-memory thread-safe operational metrics for external data and website operations."""
    osm_requests_total: int = 0
    osm_success_total: int = 0
    osm_timeout_total: int = 0
    osm_rate_limit_total: int = 0
    osm_error_total: int = 0
    osm_total_latency_ms: float = 0.0

    web_discovery_searches: int = 0
    web_discovery_verified: int = 0
    web_discovery_rejected: int = 0
    web_discovery_failures: int = 0

    web_enrichment_domains_attempted: int = 0
    web_enrichment_success_total: int = 0
    web_enrichment_http_errors: int = 0
    web_enrichment_dns_errors: int = 0
    web_enrichment_ssl_errors: int = 0
    web_enrichment_pages_fetched: int = 0
    web_enrichment_bytes_downloaded: int = 0
    web_enrichment_total_latency_ms: float = 0.0

    def record_osm_request(self, duration_ms: float, status: str, error_category: str | None = None) -> None:
        self.osm_requests_total += 1
        self.osm_total_latency_ms += duration_ms
        if status == "SUCCESS":
            self.osm_success_total += 1
        elif error_category == FailureCategory.PROVIDER_TIMEOUT:
            self.osm_timeout_total += 1
        elif error_category == FailureCategory.PROVIDER_RATE_LIMIT:
            self.osm_rate_limit_total += 1
        else:
            self.osm_error_total += 1

    def record_web_enrichment(
        self,
        duration_ms: float,
        pages_count: int,
        bytes_count: int,
        is_success: bool,
        error_category: str | None = None,
    ) -> None:
        self.web_enrichment_domains_attempted += 1
        self.web_enrichment_pages_fetched += pages_count
        self.web_enrichment_bytes_downloaded += bytes_count
        self.web_enrichment_total_latency_ms += duration_ms

        if is_success:
            self.web_enrichment_success_total += 1
        elif error_category == FailureCategory.WEBSITE_DNS_ERROR:
            self.web_enrichment_dns_errors += 1
        elif error_category == FailureCategory.WEBSITE_SSL_ERROR:
            self.web_enrichment_ssl_errors += 1
        else:
            self.web_enrichment_http_errors += 1


GLOBAL_PROVIDER_METRICS = ProviderMetricsTracker()


class WorkerHeartbeatManager:
    """Manages worker lifecycle, heartbeats, and stale worker detection."""

    @staticmethod
    def record_heartbeat(
        db: Session,
        worker_id: str,
        status: str = "HEALTHY",
        current_job_id: uuid.UUID | None = None,
        jobs_processed: int | None = None,
        jobs_failed: int | None = None,
        error_message: str | None = None,
        details: dict | None = None,
    ) -> WorkerHeartbeat:
        now = datetime.now(UTC)
        worker = db.scalar(select(WorkerHeartbeat).where(WorkerHeartbeat.worker_id == worker_id))
        if not worker:
            worker = WorkerHeartbeat(
                worker_id=worker_id,
                status=status,
                current_job_id=current_job_id,
                jobs_processed=jobs_processed or 0,
                jobs_failed=jobs_failed or 0,
                started_at=now,
                last_heartbeat=now,
                last_error_message=error_message,
                details=details or {},
            )
            db.add(worker)
        else:
            worker.status = status
            worker.last_heartbeat = now
            if current_job_id is not None:
                worker.current_job_id = current_job_id
            if jobs_processed is not None:
                worker.jobs_processed = jobs_processed
            if jobs_failed is not None:
                worker.jobs_failed = jobs_failed
            if error_message:
                worker.last_error_at = now
                worker.last_error_message = error_message
            if details:
                worker.details = details

        db.commit()
        db.refresh(worker)
        return worker

    @staticmethod
    def get_stale_workers(db: Session, threshold_seconds: int = 60) -> list[WorkerHeartbeat]:
        cutoff = datetime.now(UTC) - timedelta(seconds=threshold_seconds)
        return list(
            db.scalars(
                select(WorkerHeartbeat).where(
                    WorkerHeartbeat.last_heartbeat < cutoff,
                    WorkerHeartbeat.status.in_(["HEALTHY", "BUSY"]),
                )
            ).all()
        )


class StuckJobDetector:
    """Detects unresponsive, frozen, or abandoned scrape jobs deterministically."""

    STUCK_THRESHOLD_SECONDS: int = 300  # 5 minutes without progress

    @classmethod
    def evaluate_job_stuck(cls, job: ScrapeJob, now: datetime | None = None) -> tuple[bool, str | None]:
        if job.status not in ["RUNNING", "PENDING"]:
            return False, None

        current_time = now or datetime.now(UTC)
        job_updated = job.updated_at or job.created_at
        if job_updated.tzinfo is None:
            job_updated = job_updated.replace(tzinfo=UTC)

        elapsed_since_update = (current_time - job_updated).total_seconds()
        if elapsed_since_update > cls.STUCK_THRESHOLD_SECONDS:
            return True, f"No progress or telemetry heartbeat received for {int(elapsed_since_update)} seconds"

        return False, None


class SafeJobRecoveryManager:
    """Safely recovers stuck/interrupted jobs preserving idempotency and zero record duplication."""

    @staticmethod
    def recover_job(
        db: Session,
        job_id: uuid.UUID,
        workspace_id: uuid.UUID,
        actor_user_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        job = db.scalar(
            select(ScrapeJob).where(
                ScrapeJob.id == job_id,
                ScrapeJob.workspace_id == workspace_id,
            )
        )
        if not job:
            raise ValueError("Job not found or access forbidden")

        is_stuck, reason = StuckJobDetector.evaluate_job_stuck(job)
        is_failed = job.status in ["FAILED", "CANCELLED"]

        if not (is_stuck or is_failed):
            return {
                "status": "SKIPPED",
                "message": f"Job {job.id} is in status '{job.status}' and does not require recovery",
                "job_id": str(job.id),
            }

        # Check existing persisted leads for this job to guarantee idempotency
        persisted_leads_count = db.scalar(
            select(func.count()).select_from(Lead).where(
                Lead.job_id == job.id,
                Lead.workspace_id == workspace_id,
                Lead.deleted_at.is_(None),
            )
        ) or 0

        # Log Recovery Attempt in JobStageLog
        stage_log = JobStageLog(
            job_id=job.id,
            workspace_id=workspace_id,
            stage="RECOVERY",
            status="SUCCESS",
            error_category=None,
            error_detail=f"Safe recovery executed. Previous status: {job.status}. Reason: {reason or 'Manual operator retry'}",
            metrics={"persisted_leads_before_recovery": persisted_leads_count},
        )
        db.add(stage_log)

        # Transition Job State
        job.status = "PENDING"
        job.error_message = None
        job.completion_reason = "RECOVERED_BY_OPERATOR"
        job.updated_at = datetime.now(UTC)

        # Audit Log
        audit = AuditLog(
            workspace_id=workspace_id,
            user_id=actor_user_id,
            action="JOB_SAFE_RECOVERY",
            resource=f"/scrape-jobs/{job.id}",
            payload={"job_id": str(job.id), "previous_status": job.status},
        )
        db.add(audit)

        db.commit()
        db.refresh(job)

        return {
            "status": "RECOVERED",
            "message": f"Job {job.id} safely recovered and reset to PENDING with all existing leads preserved",
            "job_id": str(job.id),
            "persisted_leads": persisted_leads_count,
        }
