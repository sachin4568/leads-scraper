from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.websockets import WebSocketDisconnect

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


def test_websocket_rejects_missing_token(test_db_session) -> None:
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                "/api/scrape-jobs/123e4567-e89b-12d3-a456-426614174000/ws"
            ):
                pass


def test_websocket_streams_initial_job_status(test_db_session) -> None:
    workspace_id = uuid.uuid4()
    token = create_access_token(uuid.uuid4(), workspace_id)
    job = ScrapeJob(
        workspace_id=workspace_id,
        niche="Dental Clinics",
        country="India",
        status="RUNNING",
        target_lead_count=100,
        leads_scraped=25,
    )
    test_db_session.add(job)
    test_db_session.commit()
    test_db_session.refresh(job)

    with TestClient(app) as client:
        with client.websocket_connect(f"/api/scrape-jobs/{job.id}/ws?token={token}") as websocket:
            data = websocket.receive_json()
            assert data["job_id"] == str(job.id)
            assert data["status"] == "RUNNING"
            assert data["leads_scraped"] == 25
            assert data["target_lead_count"] == 100
