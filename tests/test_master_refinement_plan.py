from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.intelligence import LearningAgent
from backend.app.models import Lead, Workspace


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        yield session


def test_feature_store_and_prediction_ledger(db_session) -> None:
    ws_id = uuid.uuid4()
    ws = Workspace(id=ws_id, name="Ledger WS")
    db_session.add(ws)

    lead = Lead(
        workspace_id=ws_id, business_name="Delhi Dental Clinic", website="https://delhidental.com"
    )
    db_session.add(lead)
    db_session.commit()

    agent = LearningAgent()
    snapshot = agent.record_feature_snapshot(
        db_session,
        ws_id,
        lead.id,
        {"source": "google_maps", "website_exists": True, "ssl_valid": True},
    )
    assert snapshot.id is not None
    assert snapshot.feature_version == "v3.0"

    ledger = agent.record_prediction(
        db_session,
        ws_id,
        lead.id,
        model_name="CatBoostLightGBMEnsemble",
        model_version="v2.0_phase3_ensemble",
        prediction=0.88,
        confidence=0.95,
        decision="GENUINE",
    )
    assert ledger.id is not None
    assert ledger.decision == "GENUINE"
    assert ledger.prediction == 0.88


def test_uncertainty_math_and_active_learning(db_session) -> None:
    ws_id = uuid.uuid4()
    ws = Workspace(id=ws_id, name="Uncertainty WS")
    db_session.add(ws)

    # Lead with score 0.50 -> uncertainty_score = 1.0 - |0.5 - 0.5|*2 = 1.0 (Maximum uncertainty)
    l1 = Lead(workspace_id=ws_id, business_name="High Uncertainty", genuineness_score=0.50)
    # Lead with score 0.95 -> uncertainty_score = 1.0 - |0.95 - 0.5|*2 = 0.1 (Low uncertainty)
    l2 = Lead(workspace_id=ws_id, business_name="Clear Genuine", genuineness_score=0.95)

    db_session.add_all([l1, l2])
    db_session.commit()

    agent = LearningAgent()
    queue = agent.select_active_learning_queue(db_session, ws_id)

    assert len(queue) >= 1
    assert queue[0].business_name == "High Uncertainty"
    assert queue[0].uncertainty_score == 1.0


def test_champion_vs_challenger_evaluation(db_session) -> None:
    ws_id = uuid.uuid4()
    ws = Workspace(id=ws_id, name="Governance WS")
    db_session.add(ws)

    agent = LearningAgent()
    res = agent.trigger_champion_challenger_retraining(db_session, ws_id)

    assert "champion_version" in res
    assert "challenger_version" in res
    assert res["status"] in ("STAGING_CHALLENGER_VICTORY", "STAGING_REGRESSION_REJECTED")
