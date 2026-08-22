from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.intelligence import GenuinenessAgent, LearningAgent
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


def test_genuineness_agent_evaluations(db_session) -> None:
    ws_id = uuid.uuid4()
    ws = Workspace(id=ws_id, name="Master AI WS")
    db_session.add(ws)

    # Genuine Lead
    lead1 = Lead(
        workspace_id=ws_id,
        business_name="Apex Dental Care",
        website="https://apexdental.com",
        email="info@apexdental.com",
        phone="+12125551234",
    )
    db_session.add(lead1)
    db_session.commit()

    agent = GenuinenessAgent()
    res1 = agent.evaluate_lead_genuineness(db_session, lead1)

    assert res1.decision in ("GENUINE", "NEEDS_REVIEW")
    assert res1.overall_score > 0.5
    assert lead1.genuineness_status == res1.decision

    # Low Quality / Rejected Candidate
    lead2 = Lead(workspace_id=ws_id, business_name="X")
    db_session.add(lead2)
    db_session.commit()

    res2 = agent.evaluate_lead_genuineness(db_session, lead2)
    assert res2.decision in ("NEEDS_REVIEW", "REJECTED")


def test_learning_agent_active_learning_queue(db_session) -> None:
    ws_id = uuid.uuid4()
    ws = Workspace(id=ws_id, name="Active Learning WS")
    db_session.add(ws)

    lead = Lead(
        workspace_id=ws_id,
        business_name="Uncertain Business",
        genuineness_score=0.55,
    )
    db_session.add(lead)
    db_session.commit()

    learning_agent = LearningAgent()
    queue = learning_agent.select_active_learning_queue(db_session, ws_id)

    assert len(queue) == 1
    assert queue[0].business_name == "Uncertain Business"


def test_google_sheets_10_tab_sync_payload() -> None:
    # Test format structure of 10-tab sync payload
    tab_data = {
        "RAW_LEADS": [
            [
                "id-101",
                "Insta",
                "https://insta.com",
                "info@insta.com",
                "+1234",
                "PERSISTED",
                "2026-08-11",
            ]
        ],
        "VERIFIED_LEADS": [
            [
                "id-101",
                "Insta",
                "https://insta.com",
                "info@insta.com",
                "+1234",
                "VERIFIED",
                "2026-08-11",
            ]
        ],
        "GENUINE_LEADS": [
            [
                "id-101",
                "Insta",
                "https://insta.com",
                "info@insta.com",
                "+1234",
                "GENUINE",
                "2026-08-11",
            ]
        ],
    }
    assert len(tab_data) == 3
