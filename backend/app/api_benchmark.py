from __future__ import annotations

import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.benchmark.config import BENCHMARK_PRESETS, BenchmarkCase
from backend.app.benchmark.metrics import BenchmarkMetricsAggregator
from backend.app.benchmark.audit import GroundTruthEvaluator, HumanAuditExporter
from backend.app.benchmark.report_generator import BenchmarkReportGenerator
from backend.app.benchmark.runner import BenchmarkRunner
from backend.app.database import get_db
from backend.app.models import ScrapeJob

router = APIRouter(prefix="/api/benchmark", tags=["benchmark"])


class RunBenchmarkRequest(BaseModel):
    preset_name: str | None = None
    niche: str = "Restaurant"
    location: str = "Ann Arbor, MI"
    country: str = "United States"
    region: str | None = "Michigan"
    state: str | None = "Ann Arbor, Michigan"
    target_count: int = 100
    sources: list[str] = Field(default_factory=lambda: ["google_maps", "osm_overpass", "foursquare"])
    enrichments: list[str] = Field(default_factory=lambda: ["email", "website", "phone"])


class AuditImportRequest(BaseModel):
    csv_content: str


@router.get("/presets")
def get_presets():
    return [
        {
            "id": k,
            "name": v.name,
            "niche": v.niche,
            "location": v.location,
            "target_count": v.target_count,
            "sources": v.sources,
        }
        for k, v in BENCHMARK_PRESETS.items()
    ]


@router.post("/run")
def run_benchmark(req: RunBenchmarkRequest, db: Session = Depends(get_db)):
    if req.preset_name and req.preset_name in BENCHMARK_PRESETS:
        config = BENCHMARK_PRESETS[req.preset_name]
    else:
        config = BenchmarkCase(
            name=f"{req.niche} — {req.location}",
            niche=req.niche,
            location=req.location,
            country=req.country,
            region=req.region,
            state=req.state or req.location,
            target_count=req.target_count,
            sources=req.sources,
            enrichments=req.enrichments,
        )

    try:
        report = BenchmarkRunner.run_benchmark(config)
        md = BenchmarkReportGenerator.generate_markdown(report)
        return {
            "status": "COMPLETED",
            "job_id": report.job_id,
            "metrics": report.__dict__,
            "markdown_report": md,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/{job_id}")
def get_report(job_id: str, db: Session = Depends(get_db)):
    try:
        j_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    job = db.scalar(select(ScrapeJob).where(ScrapeJob.id == j_uuid))
    if not job:
        raise HTTPException(status_code=404, detail="Benchmark job not found")

    report = BenchmarkMetricsAggregator.calculate_metrics(db, job)
    md = BenchmarkReportGenerator.generate_markdown(report)
    return {
        "job_id": str(job.id),
        "metrics": report.__dict__,
        "markdown_report": md,
    }


@router.get("/audit-export/{job_id}")
def export_audit_csv(job_id: str, sample_size: int = 20, db: Session = Depends(get_db)):
    try:
        j_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    csv_data = HumanAuditExporter.export_csv(db, str(j_uuid), sample_size=sample_size)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=audit_{job_id}.csv"},
    )


@router.post("/audit-import/{job_id}")
def import_audit_csv(job_id: str, req: AuditImportRequest, db: Session = Depends(get_db)):
    try:
        j_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    job = db.scalar(select(ScrapeJob).where(ScrapeJob.id == j_uuid))
    if not job:
        raise HTTPException(status_code=404, detail="Benchmark job not found")

    eval_result = GroundTruthEvaluator.evaluate_audit_csv(req.csv_content, str(j_uuid))
    report = BenchmarkMetricsAggregator.calculate_metrics(db, job)
    md = BenchmarkReportGenerator.generate_markdown(report, audit_eval=eval_result)

    return {
        "job_id": str(j_uuid),
        "total_audited": eval_result.total_audited,
        "overall_verification": eval_result.overall_verification.__dict__,
        "fields": {k: v.__dict__ for k, v in eval_result.fields.items()},
        "trust_calibration_curve": eval_result.trust_calibration_curve,
        "key_failure_patterns": eval_result.key_failure_patterns,
        "calibrated_markdown_report": md,
    }
