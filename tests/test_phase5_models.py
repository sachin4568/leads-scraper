from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.models import EmailDispatch, Lead, OutreachCampaign, Workspace


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


def test_outreach_campaign_and_dispatch_creation(db_session) -> None:
    ws_id = uuid.uuid4()
    ws = Workspace(id=ws_id, name="Campaign WS")
    db_session.add(ws)

    lead = Lead(workspace_id=ws_id, business_name="Dental Corp", email="info@dentalcorp.com")
    db_session.add(lead)
    db_session.commit()

    campaign = OutreachCampaign(
        workspace_id=ws_id,
        name="Q3 Dental Outreach",
        subject_template="Growth opportunity for {{ business_name }}",
        body_template="Hi {{ business_name }}, we noticed your website...",
    )
    db_session.add(campaign)
    db_session.commit()
    db_session.refresh(campaign)

    assert campaign.id is not None
    assert campaign.status == "DRAFT"

    dispatch = EmailDispatch(
        workspace_id=ws_id,
        campaign_id=campaign.id,
        lead_id=lead.id,
        recipient_email="info@dentalcorp.com",
    )
    db_session.add(dispatch)
    db_session.commit()
    db_session.refresh(dispatch)

    assert dispatch.id is not None
    assert dispatch.status == "PENDING"
    assert dispatch.campaign_id == campaign.id
    assert dispatch.lead_id == lead.id
