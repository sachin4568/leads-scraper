"""Regression tests for scraper target enforcement (CRITICAL BUG FIX).

Verifies that the '0 / 10 raw leads -> Partial Scrape Complete' bug is fixed:
- Zero leads scraped must produce FAILED (never PARTIAL or COMPLETED)
- Ten of ten scraped must produce COMPLETED with TARGET_REACHED
- Seven of ten with sources exhausted must produce PARTIAL with DISCOVERY_EXHAUSTED
- All sources failed must produce FAILED with ALL_SOURCES_FAILED
- completion_reason must be persisted to the database
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.models import Base as BasePhase1, ScrapeJob
from backend.app.models_phase2 import Base as BasePhase2

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine, autoflush=False)


@pytest.fixture(autouse=True)
def _setup_db():
    BasePhase1.metadata.create_all(_engine)
    BasePhase2.metadata.create_all(_engine)
    yield
    BasePhase2.metadata.drop_all(_engine)
    BasePhase1.metadata.drop_all(_engine)


def _make_job(
    leads_scraped: int = 0,
    target: int = 10,
    new_count: int = 0,
    failed_count: int = 0,
    updated_count: int = 0,
) -> tuple[ScrapeJob, any]:
    """Create a RUNNING ScrapeJob and return (job, db_session)."""
    db = _Session()
    job = ScrapeJob(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        niche="Restaurant",
        sources=["osm_overpass"],
        state="CA",
        target_lead_count=target,
        leads_scraped=leads_scraped,
        discovered_count=leads_scraped,
        new_count=new_count,
        failed_count=failed_count,
        updated_count=updated_count,
        status="RUNNING",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job, db


def _run_finalize(job: ScrapeJob, db) -> ScrapeJob:
    """Run finalize_job_status with websocket publishing mocked out."""
    from backend.app.worker import finalize_job_status
    with patch("backend.app.websockets.publish_job_progress"):
        finalize_job_status(db, job, str(job.id))
        db.refresh(job)
    return job


# ---------------------------------------------------------------------------
# Test 1 — THE ORIGINAL BUG: 0 leads must be FAILED, never PARTIAL
# ---------------------------------------------------------------------------

def test_zero_leads_is_failed_not_partial():
    """target=10, found=0, no source failures → FAILED (not PARTIAL, not COMPLETED)."""
    job, db = _make_job(leads_scraped=0, target=10, new_count=0, failed_count=0)
    job = _run_finalize(job, db)
    assert job.status == "FAILED", (
        f"BUG REGRESSION: expected FAILED when 0/{job.target_lead_count} leads found, got {job.status}"
    )
    assert job.completion_reason in ("ALL_SOURCES_FAILED", "DISCOVERY_EXHAUSTED"), (
        f"Expected a meaningful completion_reason, got {job.completion_reason!r}"
    )
    db.close()


# ---------------------------------------------------------------------------
# Test 2 — Target reached exactly → COMPLETED
# ---------------------------------------------------------------------------

def test_target_reached_is_completed():
    """target=10, found=10 → COMPLETED with TARGET_REACHED."""
    job, db = _make_job(leads_scraped=10, target=10, new_count=10)
    job = _run_finalize(job, db)
    assert job.status == "COMPLETED", f"Expected COMPLETED, got {job.status}"
    assert job.completion_reason == "TARGET_REACHED", (
        f"Expected TARGET_REACHED, got {job.completion_reason!r}"
    )
    db.close()


# ---------------------------------------------------------------------------
# Test 3 — Partial leads, discovery exhausted → PARTIAL
# ---------------------------------------------------------------------------

def test_partial_leads_is_partial():
    """target=10, found=7, discovery exhausted → PARTIAL."""
    job, db = _make_job(leads_scraped=7, target=10, new_count=7)
    job = _run_finalize(job, db)
    assert job.status == "PARTIAL", f"Expected PARTIAL, got {job.status}"
    assert job.completion_reason in ("DISCOVERY_EXHAUSTED", "PARTIAL_SOURCE_FAILURE"), (
        f"Unexpected completion_reason: {job.completion_reason!r}"
    )
    db.close()


# ---------------------------------------------------------------------------
# Test 4 — Multi-source success: all providers collectively hit target
# ---------------------------------------------------------------------------

def test_multi_source_combined_reaches_target():
    """Google=30, Foursquare=40, OSM=30 → 100/100, COMPLETED."""
    job, db = _make_job(leads_scraped=100, target=100, new_count=100)
    job = _run_finalize(job, db)
    assert job.status == "COMPLETED"
    assert job.completion_reason == "TARGET_REACHED"
    db.close()


# ---------------------------------------------------------------------------
# Test 5 — Duplicate cross-source: 3 observations → 1 unique
# (Discovery count tracking is in the worker loop; finalize sees 1 unique)
# ---------------------------------------------------------------------------

def test_low_unique_count_below_target_is_partial():
    """3 fetched but only 1 unique due to cross-source duplicates → PARTIAL."""
    job, db = _make_job(leads_scraped=1, target=10, new_count=1)
    job = _run_finalize(job, db)
    assert job.status in ("PARTIAL", "FAILED"), f"Got unexpected {job.status}"
    db.close()


# ---------------------------------------------------------------------------
# Test 6 — One source fails, other succeeds with enough leads
# ---------------------------------------------------------------------------

def test_one_source_fails_other_succeeds():
    """Google fails, Foursquare returns 100 → COMPLETED."""
    job, db = _make_job(leads_scraped=100, target=100, new_count=100, failed_count=1)
    job = _run_finalize(job, db)
    assert job.status == "COMPLETED"
    assert job.completion_reason == "TARGET_REACHED"
    db.close()


# ---------------------------------------------------------------------------
# Test 7 — All sources fail → FAILED with ALL_SOURCES_FAILED
# ---------------------------------------------------------------------------

def test_all_sources_failed_zero_leads():
    """All providers fail, 0 leads → FAILED + ALL_SOURCES_FAILED."""
    job, db = _make_job(leads_scraped=0, target=100, new_count=0, failed_count=5)
    job = _run_finalize(job, db)
    assert job.status == "FAILED", f"Expected FAILED, got {job.status}"
    assert job.completion_reason == "ALL_SOURCES_FAILED", (
        f"Expected ALL_SOURCES_FAILED, got {job.completion_reason!r}"
    )
    db.close()


# ---------------------------------------------------------------------------
# Test 8 — Partial with source failures
# ---------------------------------------------------------------------------

def test_partial_with_source_failure():
    """Some leads found, some sources failed → PARTIAL."""
    job, db = _make_job(leads_scraped=30, target=100, new_count=30, failed_count=1)
    job = _run_finalize(job, db)
    assert job.status == "PARTIAL", f"Expected PARTIAL, got {job.status}"
    assert job.completion_reason in ("DISCOVERY_EXHAUSTED", "PARTIAL_SOURCE_FAILURE"), (
        f"Unexpected completion_reason: {job.completion_reason!r}"
    )
    db.close()


# ---------------------------------------------------------------------------
# Test 9 — Over-target (concurrency edge case)
# ---------------------------------------------------------------------------

def test_over_target_is_completed():
    """Found 105 when target was 100 (concurrency overshoot) → COMPLETED."""
    job, db = _make_job(leads_scraped=105, target=100, new_count=105)
    job = _run_finalize(job, db)
    assert job.status == "COMPLETED"
    assert job.completion_reason == "TARGET_REACHED"
    db.close()


# ---------------------------------------------------------------------------
# Test 10 — Target reached early → no further work needed
# ---------------------------------------------------------------------------

def test_target_reached_early_stops():
    """Exact target reached → COMPLETED. In-loop guard is: leads_scraped >= target."""
    job, db = _make_job(leads_scraped=10, target=10, new_count=10)
    job = _run_finalize(job, db)
    assert job.status == "COMPLETED"
    db.close()


# ---------------------------------------------------------------------------
# completion_reason must be persisted to the database
# ---------------------------------------------------------------------------

def test_completion_reason_persisted_to_db():
    """completion_reason must be stored in the DB row after finalize."""
    job, db = _make_job(leads_scraped=0, target=10)
    job_id = job.id
    _run_finalize(job, db)
    db.close()

    fresh_db = _Session()
    fetched = fresh_db.scalar(select(ScrapeJob).where(ScrapeJob.id == job_id))
    fresh_db.close()

    assert fetched is not None, "Job should still exist in DB"
    assert fetched.status == "FAILED", f"Expected FAILED in DB, got {fetched.status!r}"
    assert fetched.completion_reason is not None, "completion_reason must be saved to DB"


# ---------------------------------------------------------------------------
# progress_percent must not exceed 100 even if leads_scraped > target
# ---------------------------------------------------------------------------

def test_progress_percent_capped_at_100():
    """progress_percent must not exceed 100% even if leads_scraped > target."""
    job, db = _make_job(leads_scraped=150, target=100, new_count=150)
    job = _run_finalize(job, db)
    assert job.progress_percent <= 100.0, (
        f"progress_percent exceeded 100: {job.progress_percent}"
    )
    db.close()
