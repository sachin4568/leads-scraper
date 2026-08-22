from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api import get_db
from backend.app.database import Base
from backend.app.intelligence import (
    ModelRegistry,
    PermutationDataGenerator,
    Phase3AITrainer,
)
from backend.app.main import app
from backend.app.models import Workspace
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


def test_permutation_data_generator() -> None:
    phase_a = PermutationDataGenerator.generate_phase_a_permutations(count=50)
    assert len(phase_a) == 50
    assert "industry" in phase_a[0]
    assert "smma_opportunity" in phase_a[0]

    phase_b = PermutationDataGenerator.generate_phase_b_noisy_samples(count=50)
    assert len(phase_b) == 50
    assert phase_b[0]["is_noisy"] is True


def test_phase3_ai_trainer_workflow() -> None:
    trainer = Phase3AITrainer(model_version="v2.0_test_ensemble")
    report = trainer.execute_full_3phase_training(human_feedback_count=10)

    assert report.phase_a_samples == 10000
    assert report.phase_b_samples == 30000
    assert report.total_training_samples == 40010
    assert report.metrics.f1_score > 0.0
    assert report.status == "STAGING"

    # Verify registered version in ModelRegistry
    versions = [v.version for v in ModelRegistry.list_versions()]
    assert "v2.0_test_ensemble" in versions


def test_3phase_train_api_endpoint(test_db_session) -> None:
    workspace_id = uuid.uuid4()
    token = create_access_token(uuid.uuid4(), workspace_id)

    ws = Workspace(id=workspace_id, name="3Phase Train WS")
    test_db_session.add(ws)
    test_db_session.commit()

    with TestClient(app) as client:
        res = client.post(
            "/api/models/train-3phase",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["phase_a_samples"] == 10000
        assert data["phase_b_samples"] == 30000
        assert data["status"] == "STAGING"
