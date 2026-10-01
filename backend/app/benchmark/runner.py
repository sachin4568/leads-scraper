from __future__ import annotations

import logging
import uuid
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.benchmark.config import BenchmarkCase
from backend.app.benchmark.metrics import BenchmarkMetricsAggregator, BenchmarkReportPayload
from backend.app.database import SessionLocal
from backend.app.models import ScrapeJob, Workspace
from backend.app.worker import execute_scrape_job

logger = logging.getLogger(__name__)


class BenchmarkRunner:
    """Executes controlled real-world benchmark scrape jobs and calculates calibration metrics."""

    @classmethod
    def run_benchmark(cls, config: BenchmarkCase) -> BenchmarkReportPayload:
        """Executes a benchmark run end-to-end and returns structured metrics."""
        with SessionLocal() as db:
            ws = db.scalars(select(Workspace)).first()
            if not ws:
                ws = Workspace(id=uuid.uuid4(), name="Benchmark Workspace")
                db.add(ws)
                db.commit()
                db.refresh(ws)

            job_id = uuid.uuid4()
            job = ScrapeJob(
                id=job_id,
                workspace_id=ws.id,
                niche=config.niche,
                country=config.country,
                region=config.region,
                state=config.state or config.location,
                target_lead_count=config.target_count,
                sources=config.sources,
                enrichments=config.enrichments,
                service=config.service,
                status="PENDING",
            )
            db.add(job)
            db.commit()
            logger.info(f"[BenchmarkRunner] Created benchmark job {job_id} for {config.niche} ({config.location})")

        # Execute Scrape Job synchronously via worker
        execute_scrape_job(None, str(job_id))

        with SessionLocal() as db:
            job = db.scalar(select(ScrapeJob).where(ScrapeJob.id == job_id))
            return BenchmarkMetricsAggregator.calculate_metrics(db, job)
