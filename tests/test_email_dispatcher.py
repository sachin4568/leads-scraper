from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.enrichment.suppression import SuppressionService
from backend.app.models import Lead, OutreachCampaign, Workspace
from backend.app.outreach.email_dispatcher import EmailDispatcher


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


def test_email_dispatcher_successful_send(db_session) -> None:
    ws_id = uuid.uuid4()
    ws = Workspace(id=ws_id, name="Dispatcher WS")
    db_session.add(ws)

    lead = Lead(
        workspace_id=ws_id,
        business_name="Apex Dental",
        website="https://apexdental.com",
        email="info@apexdental.com",
    )
    db_session.add(lead)
    db_session.commit()

    campaign = OutreachCampaign(
        workspace_id=ws_id,
        name="Intro Campaign",
        subject_template="Growth for {{ business_name }}",
        body_template="Hello {{ business_name }}, website: {{ website }}",
    )
    db_session.add(campaign)
    db_session.commit()

    dispatcher = EmailDispatcher(provider="mock")
    res = dispatcher.send_email(db_session, campaign, lead)

    assert res.success is True
    assert res.status == "SENT"
    assert res.rendered_subject == "Growth for Apex Dental"
    assert res.rendered_body == "Hello Apex Dental, website: https://apexdental.com"


def test_email_dispatcher_suppressed_send(db_session) -> None:
    ws_id = uuid.uuid4()
    ws = Workspace(id=ws_id, name="Suppressed Dispatcher WS")
    db_session.add(ws)

    lead = Lead(workspace_id=ws_id, business_name="OptOut Corp", email="optout@corp.com")
    db_session.add(lead)
    db_session.commit()

    # Add email to suppression list
    SuppressionService().add_suppression(db_session, ws_id, "EMAIL", "optout@corp.com")

    campaign = OutreachCampaign(
        workspace_id=ws_id,
        name="Campaign",
        subject_template="Hello",
        body_template="Body",
    )
    db_session.add(campaign)
    db_session.commit()

    dispatcher = EmailDispatcher(provider="mock")
    res = dispatcher.send_email(db_session, campaign, lead)

    assert res.success is False
    assert res.status == "SUPPRESSED"
    assert "suppressed" in res.error_message
