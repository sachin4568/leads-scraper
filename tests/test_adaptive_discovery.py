from __future__ import annotations

import pytest
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.intelligence.adaptive_discovery import AdaptiveDiscoveryEngine
from backend.app.models import ScrapeJobExecutionLog


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_adaptive_discovery_prioritization(db_session) -> None:
    job_id = uuid.uuid4()
    
    # Create historical execution logs
    # Source 1 (yelp) has low yield (0 received, 0 new)
    log1 = ScrapeJobExecutionLog(
        id=uuid.uuid4(),
        job_id=job_id,
        source="yelp",
        query="Dentists (Synonym)",
        page=1,
        records_received=0,
        records_valid=0,
        new_count=0,
        failed_count=1,
    )
    # Source 2 (google_places) has high yield (50 received, 10 new)
    log2 = ScrapeJobExecutionLog(
        id=uuid.uuid4(),
        job_id=job_id,
        source="google_places",
        query="Apex Dentist (Original)",
        page=1,
        records_received=50,
        records_valid=45,
        new_count=10,
        failed_count=0,
    )
    db_session.add(log1)
    db_session.add(log2)
    db_session.commit()

    queries = [
        {"query": "Dentists", "reason": "Synonym"},
        {"query": "Apex Dentist", "reason": "Original"},
    ]
    sources = ["yelp", "google_places"]

    sorted_queries, sorted_sources = AdaptiveDiscoveryEngine.prioritize_search_plan(
        db_session, queries, sources
    )

    # "Apex Dentist" query should be prioritized first because of high yield log2
    assert sorted_queries[0]["query"] == "Apex Dentist"
    # "google_places" source should be prioritized first because of high yield log2
    assert sorted_sources[0] == "google_places"
