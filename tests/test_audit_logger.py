from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api import get_db
from backend.app.database import Base
from backend.app.main import app
from backend.app.models import AuditLog, Workspace
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
    monkeypatch.setattr("backend.app.middleware.audit_logger.SessionLocal", session_factory)
    with session_factory() as session:
        yield session
    app.dependency_overrides.clear()


def test_audit_logger_creates_entry_on_mutating_request(test_db_session) -> None:
    workspace_id = uuid.uuid4()
    token = create_access_token(uuid.uuid4(), workspace_id)

    ws = Workspace(id=workspace_id, name="Audit WS")
    test_db_session.add(ws)
    test_db_session.commit()

    with TestClient(app) as client:
        response = client.post(
            "/api/leads",
            headers={"Authorization": f"Bearer {token}"},
            json={"business_name": "Audit Test Clinic"},
        )
        assert response.status_code == 201

        # Verify audit log entry created
        logs = test_db_session.scalars(
            select(AuditLog).where(AuditLog.workspace_id == workspace_id)
        ).all()
        assert len(logs) == 1
        assert "POST" in logs[0].action
        assert logs[0].resource == "/api/leads"


def test_audit_logger_creates_entry_on_export_request(test_db_session) -> None:
    workspace_id = uuid.uuid4()
    token = create_access_token(uuid.uuid4(), workspace_id)

    ws = Workspace(id=workspace_id, name="Export Audit WS")
    test_db_session.add(ws)
    test_db_session.commit()

    with TestClient(app) as client:
        response = client.get(
            "/api/leads/export.csv",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

        logs = test_db_session.scalars(
            select(AuditLog).where(AuditLog.workspace_id == workspace_id)
        ).all()
        assert len(logs) == 1
        assert logs[0].resource == "/api/leads/export.csv"
