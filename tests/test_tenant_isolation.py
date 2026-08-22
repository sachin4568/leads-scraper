from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api import get_db
from backend.app.database import Base
from backend.app.main import app
from backend.app.security import create_access_token


def test_workspace_cannot_access_another_workspaces_lead(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    database_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(database_engine)
    session_factory = sessionmaker(bind=database_engine)

    def override_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        first_workspace = uuid.uuid4()
        second_workspace = uuid.uuid4()
        first_token = create_access_token(uuid.uuid4(), first_workspace)
        second_token = create_access_token(uuid.uuid4(), second_workspace)
        with TestClient(app) as client:
            created = client.post(
                "/api/leads",
                headers={"Authorization": f"Bearer {first_token}"},
                json={"business_name": "First workspace business"},
            )
            assert created.status_code == 201
            lead_id = created.json()["id"]

            listing = client.get("/api/leads", headers={"Authorization": f"Bearer {second_token}"})
            assert listing.status_code == 200
            assert listing.json() == []

            update = client.patch(
                f"/api/leads/{lead_id}",
                headers={"Authorization": f"Bearer {second_token}"},
                json={"business_name": "Attempted takeover"},
            )
            assert update.status_code == 404

            deletion = client.delete(
                f"/api/leads/{lead_id}",
                headers={"Authorization": f"Bearer {second_token}"},
            )
            assert deletion.status_code == 404
    finally:
        app.dependency_overrides.clear()
