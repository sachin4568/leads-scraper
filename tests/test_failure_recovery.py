import uuid

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.models import Base as BasePhase1
from backend.app.models import ScrapeJob, ScrapeJobExecutionLog
from backend.app.models_phase2 import Base as BasePhase2
from backend.app.worker import execute_single_query_plan

engine = create_engine("sqlite:///:memory:")
SessionLocal = sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    BasePhase1.metadata.create_all(engine)
    BasePhase2.metadata.create_all(engine)
    yield
    BasePhase2.metadata.drop_all(engine)
    BasePhase1.metadata.drop_all(engine)


class TransientFailConnector:
    def __init__(self):
        self.call_count = 0

    def search_leads(self, query, location, limit=50, page=1):
        self.call_count += 1
        if self.call_count < 3:
            raise httpx.TimeoutException("Connection timed out")
        return []


class PermanentFailConnector:
    def __init__(self):
        self.call_count = 0

    def search_leads(self, query, location, limit=50, page=1):
        self.call_count += 1
        raise Exception("API key is unauthorized or invalid (401)")


class PersistentTransientFailConnector:
    def __init__(self):
        self.call_count = 0

    def search_leads(self, query, location, limit=50, page=1):
        self.call_count += 1
        raise httpx.TimeoutException("Connection timed out")


def test_transient_error_retries_and_success(monkeypatch):
    db = SessionLocal()
    connector = TransientFailConnector()
    monkeypatch.setattr(
        "backend.app.worker.get_connectors",
        lambda: {"transient_connector": connector}
    )
    monkeypatch.setattr("time.sleep", lambda s: None)  # fast-forward sleep

    job = ScrapeJob(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        niche="Dentist",
        sources=["transient_connector"],
        state="CA",
        target_lead_count=10,
        leads_scraped=0,
        status="RUNNING",
    )
    db.add(job)
    db.commit()

    plan = {
        "query": "dentist",
        "reason": "exact matching",
        "source": "transient_connector",
        "location": "CA"
    }

    execute_single_query_plan(db, job, plan)

    # Should have called search_leads 3 times (2 timeout failures, then successful empty page)
    assert connector.call_count == 3
    db.close()


def test_permanent_error_aborts_immediately(monkeypatch):
    db = SessionLocal()
    connector = PermanentFailConnector()
    monkeypatch.setattr(
        "backend.app.worker.get_connectors",
        lambda: {"permanent_connector": connector}
    )
    monkeypatch.setattr("time.sleep", lambda s: None)

    job = ScrapeJob(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        niche="Dentist",
        sources=["permanent_connector"],
        state="CA",
        target_lead_count=10,
        leads_scraped=0,
        status="RUNNING",
    )
    db.add(job)
    db.commit()

    plan = {
        "query": "dentist",
        "reason": "exact matching",
        "source": "permanent_connector",
        "location": "CA"
    }

    execute_single_query_plan(db, job, plan)

    # Should have aborted immediately after first failure (no retry)
    assert connector.call_count == 1
    
    # Verify execution log reports AUTH_FAILURE error reason
    logs = db.scalars(select(ScrapeJobExecutionLog)).all()
    assert len(logs) == 1
    assert "AUTH_FAILURE" in logs[0].error_reason

    db.close()


def test_transient_retries_are_bounded(monkeypatch):
    db = SessionLocal()
    connector = PersistentTransientFailConnector()
    monkeypatch.setattr(
        "backend.app.worker.get_connectors",
        lambda: {"persistent_transient_connector": connector},
    )
    monkeypatch.setattr("time.sleep", lambda s: None)

    job = ScrapeJob(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        niche="Dentist",
        sources=["persistent_transient_connector"],
        state="CA",
        target_lead_count=10,
        status="RUNNING",
    )
    db.add(job)
    db.commit()

    execute_single_query_plan(
        db,
        job,
        {
            "query": "dentist",
            "reason": "exact matching",
            "source": "persistent_transient_connector",
            "location": "CA",
        },
    )

    assert connector.call_count == 3
    db.close()
