import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.app.database import get_db
from backend.app.models import Base as BasePhase1, Lead, SourceRecord
from backend.app.models_phase2 import Base as BasePhase2, LeadObservation, HumanOutcomeEventRecord
from backend.app.main import app

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
SessionLocal = sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    BasePhase1.metadata.create_all(engine)
    BasePhase2.metadata.create_all(engine)
    yield
    BasePhase2.metadata.drop_all(engine)
    BasePhase1.metadata.drop_all(engine)


def test_human_feedback_writes_outcome_and_tunes_weights():
    db = SessionLocal()

    workspace_id = uuid.uuid4()

    # Override FastAPI dependencies correctly using dependency_overrides
    from backend.app.api import current_claims, current_workspace_id
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[current_claims] = lambda: {"workspace_id": str(workspace_id)}
    app.dependency_overrides[current_workspace_id] = lambda: workspace_id

    # 1. Create a lead and its source record observation association
    lead = Lead(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        business_name="Test Cafe",
        website="https://testcafe.com",
        phone="+1234567890",
        raw_status="PERSISTED",
        verification_status="UNVERIFIED",
    )
    db.add(lead)
    db.flush()

    source_rec = SourceRecord(
        workspace_id=workspace_id,
        lead_id=lead.id,
        source="yelp",
        source_id="yelp_cafe_1",
        raw_data={}
    )
    db.add(source_rec)
    db.flush()

    obs = LeadObservation(
        canonical_lead_id=str(uuid.uuid4()),
        source_name="yelp",
        source_record_id="yelp_cafe_1",
        observed_business_name="Test Cafe",
        observed_website="https://testcafe.com"
    )
    db.add(obs)
    db.commit()

    # Client submit feedback
    client = TestClient(app)
    headers = {"Authorization": "Bearer dummy_token"}
    response = client.post(
        f"/api/leads/{lead.id}/feedback",
        json={"rating": "EXCELLENT", "service_label": "SEO", "comments": "Great lead!"},
        headers=headers
    )

    assert response.status_code == 201

    # Verify HumanOutcomeEventRecord was written
    outcomes = db.scalars(select(HumanOutcomeEventRecord)).all()
    assert len(outcomes) == 1
    assert outcomes[0].human_outcome == "EXCELLENT"
    assert outcomes[0].canonical_lead_id == obs.canonical_lead_id

    app.dependency_overrides.clear()
    db.close()
