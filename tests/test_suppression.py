from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.enrichment.suppression import SuppressionService
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


def test_suppression_service_add_and_check(db_session) -> None:
    ws_id = uuid.uuid4()
    ws = Workspace(id=ws_id, name="Suppression WS")
    db_session.add(ws)
    db_session.commit()

    service = SuppressionService()
    service.add_suppression(db_session, ws_id, "EMAIL", "optout@client.com", reason="Unsubscribed")
    service.add_suppression(
        db_session, ws_id, "DOMAIN", "https://spamdomain.com", reason="Blacklisted domain"
    )

    # Check email suppression
    is_supp, reason = service.is_suppressed(db_session, ws_id, email="optout@client.com")
    assert is_supp is True
    assert "Unsubscribed" in reason

    # Check domain suppression
    is_supp_dom, _ = service.is_suppressed(db_session, ws_id, domain="spamdomain.com")
    assert is_supp_dom is True

    # Non-suppressed email
    is_clean, _ = service.is_suppressed(db_session, ws_id, email="valid@client.com")
    assert is_clean is False


def test_suppression_lead_filtering(db_session) -> None:
    ws_id = uuid.uuid4()
    ws = Workspace(id=ws_id, name="Filter WS")
    db_session.add(ws)
    db_session.commit()

    service = SuppressionService()
    service.add_suppression(db_session, ws_id, "EMAIL", "do-not-contact@badcorp.com")

    lead1 = Lead(workspace_id=ws_id, business_name="Good Business", email="hello@goodbiz.com")
    lead2 = Lead(
        workspace_id=ws_id, business_name="Bad Business", email="do-not-contact@badcorp.com"
    )

    filtered = service.filter_suppressed_leads(db_session, ws_id, [lead1, lead2])
    assert len(filtered) == 1
    assert filtered[0].business_name == "Good Business"


def test_suppression_tenant_isolation(db_session) -> None:
    ws_a = uuid.uuid4()
    ws_b = uuid.uuid4()

    service = SuppressionService()
    service.add_suppression(db_session, ws_a, "EMAIL", "blocked@domain.com")

    # ws_a is suppressed
    assert service.is_suppressed(db_session, ws_a, email="blocked@domain.com")[0] is True

    # ws_b is NOT suppressed
    assert service.is_suppressed(db_session, ws_b, email="blocked@domain.com")[0] is False
