from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api import get_db
from backend.app.database import Base
from backend.app.main import app
from backend.app.models import ScrapeJob
from backend.app.security import create_access_token


@pytest.fixture
def test_db_session(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    def override_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    with session_factory() as session:
        yield session
    app.dependency_overrides.clear()


def test_stop_save_scrape_job_endpoint(test_db_session) -> None:
    workspace_id = uuid.uuid4()
    token = create_access_token(uuid.uuid4(), workspace_id)
    job = ScrapeJob(
        workspace_id=workspace_id,
        niche="Legal",
        country="India",
        status="RUNNING",
        target_lead_count=50,
        leads_scraped=12,
    )
    test_db_session.add(job)
    test_db_session.commit()
    test_db_session.refresh(job)

    with TestClient(app) as client:
        response = client.post(
            f"/api/scrape-jobs/{job.id}/stop-save",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "STOPPED_SAVED"
        assert data["leads_scraped"] == 12


def test_cancel_scrape_job_endpoint(test_db_session) -> None:
    workspace_id = uuid.uuid4()
    token = create_access_token(uuid.uuid4(), workspace_id)
    job = ScrapeJob(
        workspace_id=workspace_id,
        niche="Real Estate",
        country="India",
        status="RUNNING",
        target_lead_count=100,
        leads_scraped=5,
    )
    test_db_session.add(job)
    test_db_session.commit()
    test_db_session.refresh(job)

    with TestClient(app) as client:
        response = client.post(
            f"/api/scrape-jobs/{job.id}/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "CANCELLED"


def test_stop_save_unauthorized_workspace_returns_404(test_db_session) -> None:
    workspace_a = uuid.uuid4()
    workspace_b = uuid.uuid4()
    token_b = create_access_token(uuid.uuid4(), workspace_b)

    job = ScrapeJob(
        workspace_id=workspace_a,
        niche="Plumbers",
        country="India",
        status="RUNNING",
    )
    test_db_session.add(job)
    test_db_session.commit()
    test_db_session.refresh(job)

    with TestClient(app) as client:
        response = client.post(
            f"/api/scrape-jobs/{job.id}/stop-save",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert response.status_code == 404
