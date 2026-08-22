from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api import get_db
from backend.app.database import Base
from backend.app.main import app
from backend.app.models import Lead, Workspace
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


def test_enrich_lead_endpoint(test_db_session) -> None:
    workspace_id = uuid.uuid4()
    token = create_access_token(uuid.uuid4(), workspace_id)

    ws = Workspace(id=workspace_id, name="Enrich WS")
    test_db_session.add(ws)

    lead = Lead(
        workspace_id=workspace_id,
        business_name="Metro Dental Clinic",
        website="https://metrodental.com",
        email="contact@metrodental.com",
        phone="+14155552671",
    )
    test_db_session.add(lead)
    test_db_session.commit()
    test_db_session.refresh(lead)

    with patch("backend.app.worker.enrich_lead_task.delay") as mock_delay:
        with TestClient(app) as client:
            response = client.post(
                f"/api/leads/{lead.id}/enrich",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["lead_id"] == str(lead.id)
            assert "overall_confidence" in data
            assert "field_scores" in data
            mock_delay.assert_called_once_with(str(lead.id))

            # Fetch evidence history endpoint
            ev_res = client.get(
                f"/api/leads/{lead.id}/evidence",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert ev_res.status_code == 200


def test_suppression_list_endpoints(test_db_session) -> None:
    workspace_id = uuid.uuid4()
    token = create_access_token(uuid.uuid4(), workspace_id)

    ws = Workspace(id=workspace_id, name="Suppression API WS")
    test_db_session.add(ws)
    test_db_session.commit()

    with TestClient(app) as client:
        # Create suppression entry
        create_res = client.post(
            "/api/suppression-list",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "entry_type": "EMAIL",
                "entry_value": "optout@client.com",
                "reason": "Unsubscribe request",
            },
        )
        assert create_res.status_code == 201
        data = create_res.json()
        assert data["entry_type"] == "EMAIL"
        assert data["entry_value"] == "optout@client.com"

        # List suppression entries
        list_res = client.get(
            "/api/suppression-list",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert list_res.status_code == 200
        assert len(list_res.json()) == 1
