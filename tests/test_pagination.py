import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.models import Base as BasePhase1
from backend.app.models_phase2 import Base as BasePhase2
from backend.app.models import ScrapeJob
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


class MockConnector:
    def __init__(self):
        self.call_count = 0

    def search_leads(self, query, location, limit=50, page=1, pagination_state=None):
        self.call_count += 1
        if pagination_state is not None:
            # We simulate a repeated token loop: returning the same next_page_token constantly!
            pagination_state["next_page_token"] = "repeated_token"
            pagination_state["has_more"] = True
        return []


def test_pagination_repeated_cursor_prevention(monkeypatch):
    db = SessionLocal()

    connector = MockConnector()
    monkeypatch.setattr(
        "backend.app.worker.get_connectors",
        lambda: {"mock_connector": connector}
    )

    # Create a test scrape job
    job = ScrapeJob(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        niche="Dentist",
        sources=["mock_connector"],
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
        "source": "mock_connector",
        "location": "CA"
    }

    # Execute the single plan
    execute_single_query_plan(db, job, plan)

    # The pagination loop should abort immediately when a duplicate token is seen.
    # Therefore, search_leads should have been called at most twice:
    # 1. First page fetch (sets next_page_token to "repeated_token")
    # 2. Second page fetch (sends "repeated_token", detects duplicate cursor, breaks)
    assert connector.call_count == 2

    db.close()
