import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.models import Base as BasePhase1
from backend.app.models_phase2 import Base as BasePhase2
from backend.app.models import ScrapeJob
from backend.app.worker import execute_scrape_job

# SQLite database setup for testing
engine = create_engine("sqlite:///:memory:")
SessionLocal = sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    BasePhase1.metadata.create_all(engine)
    BasePhase2.metadata.create_all(engine)
    yield
    BasePhase2.metadata.drop_all(engine)
    BasePhase1.metadata.drop_all(engine)


def test_cartesian_query_plan_prioritization(monkeypatch):
    db = SessionLocal()
    
    # Mock database session return inside worker
    monkeypatch.setattr("backend.app.database.SessionLocal", lambda: db)
    
    # Mock expand_query to return a static set of niche expansions
    from backend.app.intelligence.query_expansion import QueryExpansionEngine
    monkeypatch.setattr(
        QueryExpansionEngine,
        "expand_query",
        lambda self, niche, loc: [
            {"query": "dental clinic", "reason": "exact niche matching"},
            {"query": "dentist office", "reason": "synonym expansion"},
        ]
    )

    # Mock AdaptiveDiscoveryEngine.get_query_score to return custom scores
    from backend.app.intelligence.adaptive_discovery import AdaptiveDiscoveryEngine
    monkeypatch.setattr(
        AdaptiveDiscoveryEngine,
        "get_query_score",
        lambda db_session, term: 95.0 if "clinic" in term else 50.0
    )

    # Mock execution of single query plan to just record plans executed
    executed_plans = []
    monkeypatch.setattr(
        "backend.app.worker.execute_single_query_plan",
        lambda db_sess, job_obj, plan_obj: executed_plans.append(plan_obj)
    )

    # Create a test scrape job
    job = ScrapeJob(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        niche="Dentist",
        sources=["google_maps", "osm_overpass"],
        state="CA",
        target_lead_count=10,
        leads_scraped=0,
        status="PENDING",
    )
    db.add(job)
    db.commit()

    # Run the executor
    execute_scrape_job(None, str(job.id))

    # Assert Cartesian plans were executed in descending order of historical score
    assert len(executed_plans) == 4
    
    # The first two plans should have "dental clinic" (score 95.0)
    assert executed_plans[0]["query"] == "dental clinic"
    assert executed_plans[0]["historical_score"] == 95.0
    assert executed_plans[1]["query"] == "dental clinic"
    assert executed_plans[1]["historical_score"] == 95.0
    
    # The next two plans should have "dentist office" (score 50.0)
    assert executed_plans[2]["query"] == "dentist office"
    assert executed_plans[2]["historical_score"] == 50.0
    assert executed_plans[3]["query"] == "dentist office"
    assert executed_plans[3]["historical_score"] == 50.0

    db.close()
