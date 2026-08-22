from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api import get_db
from backend.app.database import Base
from backend.app.main import app
from backend.app.models import Lead, ScrapeJob, SourceRecord
from backend.app.models_phase2 import Base as Phase2Base
from backend.app.security import create_access_token
from backend.app.sources.base import NormalizedLeadRecord
from backend.app.worker import process_scrape_job_task


@pytest.fixture
def test_db_session(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Phase2Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    def override_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr("backend.app.database.SessionLocal", session_factory)
    with session_factory() as session:
        yield session
    app.dependency_overrides.clear()


def test_create_and_get_scrape_job(test_db_session) -> None:
    workspace_id = uuid.uuid4()
    token = create_access_token(uuid.uuid4(), workspace_id)

    with patch("backend.app.worker.process_scrape_job_task.delay") as mock_delay:
        with TestClient(app) as client:
            response = client.post(
                "/api/scrape-jobs",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "niche": "Dental Clinics",
                    "country": "India",
                    "state": "Delhi",
                    "target_lead_count": 50,
                    "sources": ["google_maps"],
                },
            )
            assert response.status_code == 201
            data = response.json()
            job_id = data["id"]
            assert data["niche"] == "Dental Clinics"
            assert data["status"] == "PENDING"
            mock_delay.assert_called_once_with(job_id)

            # List jobs
            list_res = client.get("/api/scrape-jobs", headers={"Authorization": f"Bearer {token}"})
            assert list_res.status_code == 200
            assert len(list_res.json()) == 1

            # Get single job
            single_res = client.get(
                f"/api/scrape-jobs/{job_id}", headers={"Authorization": f"Bearer {token}"}
            )
            assert single_res.status_code == 200
            assert single_res.json()["id"] == job_id


def test_process_scrape_job_task_execution_and_deduplication(test_db_session) -> None:
    workspace_id = uuid.uuid4()
    job = ScrapeJob(
        workspace_id=workspace_id,
        niche="Dentists",
        country="India",
        sources=["google_maps"],
        target_lead_count=2,
    )
    test_db_session.add(job)
    test_db_session.commit()
    test_db_session.refresh(job)

    mock_records = [
        NormalizedLeadRecord(
            source="google_maps",
            source_id="gmaps-unique-1",
            business_name="Smile Care Dental",
            phone="+91 9876543210",
        ),
        NormalizedLeadRecord(
            source="google_maps",
            source_id="gmaps-unique-2",
            business_name="City Dental Clinic",
            phone="+91 8765432109",
        ),
    ]

    mock_connector = MagicMock()
    mock_connector.search_leads.return_value = mock_records

    with patch("backend.app.sources.google_maps.GoogleMapsConnector", return_value=mock_connector):
        process_scrape_job_task(str(job.id))

    test_db_session.refresh(job)
    assert job.status == "COMPLETED"
    assert job.leads_scraped == 2

    # Verify leads created in DB
    leads = test_db_session.scalars(select(Lead).where(Lead.workspace_id == workspace_id)).all()
    assert len(leads) == 2

    source_recs = test_db_session.scalars(
        select(SourceRecord).where(SourceRecord.workspace_id == workspace_id)
    ).all()
    assert len(source_recs) == 2

    # Re-running task with same source_ids should NOT duplicate leads
    job2 = ScrapeJob(
        workspace_id=workspace_id,
        niche="Dentists",
        country="India",
        sources=["google_maps"],
        target_lead_count=10,
    )
    test_db_session.add(job2)
    test_db_session.commit()
    test_db_session.refresh(job2)

    with patch("backend.app.sources.google_maps.GoogleMapsConnector", return_value=mock_connector):
        process_scrape_job_task(str(job2.id))

    test_db_session.refresh(job2)
    assert job2.status == "PARTIAL"
    assert job2.leads_scraped == 0  # No new leads ingested due to source_id deduplication
