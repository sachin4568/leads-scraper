from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api import get_db
from backend.app.database import Base
from backend.app.dlq import DLQHandler, compute_backoff_delay
from backend.app.intelligence import CatBoostLightGBMScorer, ModelRegistry
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


def test_dlq_and_backoff_delay() -> None:
    delay = compute_backoff_delay(attempt=2, base_delay=2.0)
    assert 2.0 <= delay <= 10.0

    err_info = DLQHandler.handle_failed_task(
        "scrape_job_task",
        "task-123",
        ("job-1",),
        {"source": "google_maps"},
        RuntimeError("API Timeout"),
    )
    assert err_info["task_name"] == "scrape_job_task"
    assert "API Timeout" in err_info["exception"]


def test_catboost_lightgbm_scorer_and_registry() -> None:
    scorer = CatBoostLightGBMScorer(model_version="v1.1")
    sample_data = [
        {"smma_opportunity": 3, "lead_quality": 4, "industry": "Dental"},
        {"smma_opportunity": 1, "lead_quality": 1, "industry": "Bakery"},
    ]
    metrics = scorer.train_and_evaluate(sample_data)
    assert metrics.precision > 0.0
    assert metrics.f1_score >= 0.0

    pred = scorer.predict_lead_quality_score(
        {"industry": "Dental", "has_website": 1, "has_email": 1, "has_phone": 1}
    )
    assert pred["predicted_opportunity_score"] > 50
    assert pred["conversion_probability"] > 0.5

    # Registry Staging & Promotion
    reg_rec = ModelRegistry.register_version(
        "v1.1", metrics.model_dump(), sample_count=len(sample_data)
    )
    assert reg_rec.status == "STAGING"

    promoted = ModelRegistry.promote_to_production("v1.1")
    assert promoted.status == "PRODUCTION"
    assert ModelRegistry.get_active_production_version() == "v1.1"


def test_phase7_endpoints(test_db_session) -> None:
    workspace_id = uuid.uuid4()
    token = create_access_token(uuid.uuid4(), workspace_id)

    ws = Workspace(id=workspace_id, name="Phase 7 WS")
    test_db_session.add(ws)

    lead = Lead(workspace_id=workspace_id, business_name="Dental Clinic", email="info@clinic.com")
    test_db_session.add(lead)
    test_db_session.commit()

    with TestClient(app) as client:
        # Readiness Probe
        ready_res = client.get("/ready")
        assert ready_res.status_code == 200
        assert ready_res.json()["status"] == "ready"

        # Human Feedback
        fb_res = client.post(
            f"/api/leads/{lead.id}/feedback",
            headers={"Authorization": f"Bearer {token}"},
            json={"rating": "EXCELLENT", "service_label": "smma", "comments": "High quality lead"},
        )
        assert fb_res.status_code == 201
        assert fb_res.json()["rating"] == "EXCELLENT"

        # Model Retraining
        train_res = client.post(
            "/api/models/train",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert train_res.status_code == 200
        data = train_res.json()
        assert "model_version" in data
        assert data["status"] == "STAGING"

        # List Versions
        versions_res = client.get(
            "/api/models/versions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert versions_res.status_code == 200
        assert len(versions_res.json()) >= 1

        # Promote Version
        ver_name = data["model_version"]
        promote_res = client.post(
            f"/api/models/promote?version={ver_name}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert promote_res.status_code == 200
        assert promote_res.json()["active_version"] == ver_name
