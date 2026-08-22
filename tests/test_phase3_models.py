from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.models import AuditLog, EvidenceRecord, Lead, SuppressionList, Workspace


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


def test_evidence_record_model_creation(db_session) -> None:
    ws = Workspace(name="Test Workspace")
    db_session.add(ws)
    db_session.commit()

    lead = Lead(workspace_id=ws.id, business_name="Dental Clinic")
    db_session.add(lead)
    db_session.commit()

    evidence = EvidenceRecord(
        workspace_id=ws.id,
        lead_id=lead.id,
        field_name="website",
        status="VERIFIED",
        confidence_score=95,
        source="website_validator",
        details={"http_status": 200, "ssl_valid": True},
    )
    db_session.add(evidence)
    db_session.commit()
    db_session.refresh(evidence)

    assert evidence.id is not None
    assert evidence.workspace_id == ws.id
    assert evidence.lead_id == lead.id
    assert evidence.field_name == "website"
    assert evidence.confidence_score == 95


def test_audit_log_model_creation(db_session) -> None:
    ws = Workspace(name="Audit Workspace")
    db_session.add(ws)
    db_session.commit()

    log = AuditLog(
        workspace_id=ws.id,
        action="EXPORT_LEADS",
        resource="leads.csv",
        ip_address="192.168.1.100",
        payload={"row_count": 50},
    )
    db_session.add(log)
    db_session.commit()
    db_session.refresh(log)

    assert log.id is not None
    assert log.workspace_id == ws.id
    assert log.action == "EXPORT_LEADS"


def test_suppression_list_model_creation(db_session) -> None:
    ws = Workspace(name="Suppression Workspace")
    db_session.add(ws)
    db_session.commit()

    suppression = SuppressionList(
        workspace_id=ws.id,
        entry_type="EMAIL",
        entry_value="optout@domain.com",
        reason="User requested do not contact",
    )
    db_session.add(suppression)
    db_session.commit()
    db_session.refresh(suppression)

    assert suppression.id is not None
    assert suppression.entry_type == "EMAIL"
    assert suppression.entry_value == "optout@domain.com"
