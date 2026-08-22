from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.models import Base as Base1, Lead, ScrapeJob, ScrapeJobExecutionLog, Workspace
from backend.app.models_phase2 import Base as Base2
from backend.app.models_phase3 import Base as Base3
from backend.app.models_services import Base as BaseServices
from backend.app.sources.base import NormalizedLeadRecord, SourceConnector
from backend.app.worker import generate_search_plan, process_scrape_job_task


class MockPaginatedConnector(SourceConnector):
    def __init__(self, total_available: int = 35) -> None:
        super().__init__()
        self.total_available = total_available

    @property
    def source_name(self) -> str:
        return "mock_paginated"

    def search_leads(
        self, query: str, location: str | None = None, limit: int = 100, page: int = 1
    ) -> list[NormalizedLeadRecord]:
        page_size = 10
        start_idx = (page - 1) * page_size
        if start_idx >= self.total_available:
            return []

        end_idx = min(start_idx + page_size, self.total_available)
        results = []
        for i in range(start_idx, end_idx):
            results.append(
                NormalizedLeadRecord(
                    source=self.source_name,
                    source_id=f"mock_{i:04d}",
                    business_name=f"Mock Business {i:04d} for {query}",
                    website=f"https://www.mockbiz{i:04d}.com",
                    phone=f"+1 555 000 {i:04d}",
                    address=f"{i} Main St, {location or 'London'}",
                    category=query,
                )
            )
        return results

    def health_check(self) -> bool:
        return True


def test_search_plan_generation():
    queries = generate_search_plan("Dental Clinics", "London")
    assert "Dental Clinics" in queries
    assert any("dentist" in q.lower() or "practice" in q.lower() for q in queries)
    assert len(queries) >= 3


def test_exact_count_partial_status(monkeypatch, tmp_path):
    db_path = tmp_path / "test_exact_count.db"
    engine = create_engine(f"sqlite:///{db_path}")
    TestingSessionLocal = sessionmaker(bind=engine)
    Base1.metadata.create_all(bind=engine)
    Base2.metadata.create_all(bind=engine)
    Base3.metadata.create_all(bind=engine)
    BaseServices.metadata.create_all(bind=engine)

    import backend.app.database
    monkeypatch.setattr(backend.app.database, "SessionLocal", TestingSessionLocal)

    with TestingSessionLocal() as session:
        ws = Workspace(name="Test Workspace")
        session.add(ws)
        session.commit()

        job = ScrapeJob(
            workspace_id=ws.id,
            niche="Dental Clinics",
            country="United Kingdom",
            region="London",
            target_lead_count=100,
            sources=["mock_paginated"],
            status="PENDING",
        )
        session.add(job)
        session.commit()
        job_id_str = str(job.id)

    mock_conn = MockPaginatedConnector(total_available=35)
    connectors_map = {"mock_paginated": mock_conn}

    with patch("backend.app.worker_concurrency.workspace_concurrency_guard") as mock_guard, \
         patch("backend.app.websockets.publish_job_progress"), \
         patch("backend.app.worker.get_connectors", return_value=connectors_map):
        mock_guard.return_value.__enter__.return_value = None

        process_scrape_job_task.component = None
        process_scrape_job_task(job_id_str)

    with TestingSessionLocal() as session:
        completed_job = session.scalar(select(ScrapeJob).where(ScrapeJob.id == uuid.UUID(job_id_str)))
        assert completed_job is not None
        assert completed_job.target_lead_count == 100
        assert completed_job.leads_scraped == 35
        assert completed_job.status == "PARTIAL"
        assert completed_job.discovered_count >= 35
        assert completed_job.valid_count >= 35

        logs = list(session.scalars(select(ScrapeJobExecutionLog).where(ScrapeJobExecutionLog.job_id == completed_job.id)))
        assert len(logs) > 0
        assert logs[0].source == "mock_paginated"
