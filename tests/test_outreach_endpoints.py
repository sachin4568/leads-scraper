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
from backend.app.models import Workspace
from backend.app.security import create_access_token
from backend.app.security.hmac_guard import generate_hmac_signature


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


def test_campaign_endpoints(test_db_session) -> None:
    workspace_id = uuid.uuid4()
    token = create_access_token(uuid.uuid4(), workspace_id)

    ws = Workspace(id=workspace_id, name="Campaign API WS")
    test_db_session.add(ws)
    test_db_session.commit()

    with TestClient(app) as client:
        # Create campaign
        create_res = client.post(
            "/api/campaigns",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "Q3 Growth Campaign",
                "subject_template": "Growth for {{ business_name }}",
                "body_template": "Hi {{ business_name }}",
            },
        )
        assert create_res.status_code == 201
        data = create_res.json()
        campaign_id = data["id"]
        assert data["name"] == "Q3 Growth Campaign"

        # List campaigns
        list_res = client.get(
            "/api/campaigns",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert list_res.status_code == 200
        assert len(list_res.json()) == 1

        # Send campaign
        with patch("backend.app.worker.dispatch_campaign_task.delay") as mock_delay:
            send_res = client.post(
                f"/api/campaigns/{campaign_id}/send",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert send_res.status_code == 200
            mock_delay.assert_called_once_with(campaign_id)


def test_crm_webhook_and_metrics_endpoints() -> None:
    secret = "crm_webhook_secret_key"
    payload_bytes = b'{"event": "lead.created"}'
    valid_sig = generate_hmac_signature(payload_bytes, secret)

    with TestClient(app) as client:
        # Verified HMAC CRM webhook
        res = client.post(
            "/api/webhooks/crm",
            content=payload_bytes,
            headers={"X-Webhook-Signature": valid_sig},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "success"

        # Invalid HMAC signature
        res_bad = client.post(
            "/api/webhooks/crm",
            content=payload_bytes,
            headers={"X-Webhook-Signature": "invalid_sig"},
        )
        assert res_bad.status_code == 401

        # Prometheus metrics endpoint
        metrics_res = client.get("/metrics")
        assert metrics_res.status_code == 200
        assert "scrape_jobs_total" in metrics_res.text
