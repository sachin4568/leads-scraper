from __future__ import annotations

import uuid
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.models import Workspace, ScrapeJob, Lead, SourceRecord, PredictionLedger, FeatureSnapshot
from backend.app.models_services import ServiceOpportunity
from backend.app.models_phase2 import Base as Phase2Base, CanonicalLead, LeadObservation
from backend.app.sources.base import NormalizedLeadRecord
from backend.app.worker import execute_single_query_plan, finalize_job_status


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Phase2Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    ws = Workspace(name="Test Workspace")
    session.add(ws)
    session.commit()
    session.refresh(ws)
    yield session, ws
    session.close()


def test_enrichment_off_skips_optional_ml_and_classification(test_db):
    """Verifies that when enrichments=[] (Enrichment OFF), core discovery persists leads but skips ML/Service classification."""
    session, ws = test_db

    job = ScrapeJob(
        workspace_id=ws.id,
        niche="restaurant",
        country="India",
        state="Mumbai",
        target_lead_count=5,
        sources=["osm_overpass"],
        enrichments=[],
        service=None,
        status="RUNNING",
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    fake_records = [
        NormalizedLeadRecord(
            source="osm_overpass",
            source_id=f"node/test_off_{i}",
            business_name=f"Off Cafe {i}",
            category="cafe",
            address="Goregaon, Mumbai",
            phone=f"+91 98200000{i:02d}",
            website=f"https://offcafe{i}.com",
            raw_data={"lat": 19.16 + (i * 0.001), "lon": 72.85 + (i * 0.001)},
        )
        for i in range(3)
    ]

    mock_connector = MagicMock()
    mock_connector.search_leads.return_value = fake_records
    mock_connector.supports_category.return_value = True

    plan = {
        "source": "osm_overpass",
        "query": "cafe",
        "reason": "niche synonym",
        "location": "Goregaon, Mumbai, India",
    }

    with patch("backend.app.worker.get_connectors", return_value={"osm_overpass": mock_connector}), \
         patch("backend.app.intelligence.genuineness.GenuinenessAgent.evaluate_lead_genuineness") as mock_gen, \
         patch("backend.app.services.classification_agent.MultiLabelClassificationAgent.classify_lead") as mock_class:

        execute_single_query_plan(session, job, plan)
        finalize_job_status(session, job, str(job.id))

    # Core discovery verifications
    assert job.leads_scraped == 3
    assert job.status in ("COMPLETED", "REGION_EXHAUSTED")
    persisted_leads = session.scalars(select(Lead).where(Lead.job_id == job.id)).all()
    assert len(persisted_leads) == 3

    # Verification that optional ML and classification were skipped
    assert mock_gen.call_count == 0
    assert mock_class.call_count == 0
    service_opps = session.scalars(select(ServiceOpportunity)).all()
    assert len(service_opps) == 0
    ledgers = session.scalars(select(PredictionLedger)).all()
    assert len(ledgers) == 0
    snapshots = session.scalars(select(FeatureSnapshot)).all()
    assert len(snapshots) == 0


def test_enrichment_on_invokes_processing(test_db):
    """Verifies that when enrichments=['email', 'website'], optional ML and classification are executed."""
    session, ws = test_db

    job = ScrapeJob(
        workspace_id=ws.id,
        niche="restaurant",
        country="India",
        state="Mumbai",
        target_lead_count=5,
        sources=["osm_overpass"],
        enrichments=["email", "website"],
        service="website_dev",
        status="RUNNING",
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    fake_records = [
        NormalizedLeadRecord(
            source="osm_overpass",
            source_id="node/test_on_1",
            business_name="Enriched Cafe 1",
            category="cafe",
            address="Goregaon, Mumbai",
            phone="+91 9820000099",
            website="https://enrichedcafe1.com",
            raw_data={"lat": 19.16, "lon": 72.85},
        )
    ]

    mock_connector = MagicMock()
    mock_connector.search_leads.return_value = fake_records
    mock_connector.supports_category.return_value = True

    plan = {
        "source": "osm_overpass",
        "query": "cafe",
        "reason": "niche synonym",
        "location": "Goregaon, Mumbai, India",
    }

    with patch("backend.app.worker.get_connectors", return_value={"osm_overpass": mock_connector}):
        execute_single_query_plan(session, job, plan)
        finalize_job_status(session, job, str(job.id))

    assert job.leads_scraped == 1
    persisted_leads = session.scalars(select(Lead).where(Lead.job_id == job.id)).all()
    assert len(persisted_leads) == 1

    # Optional records should be created
    service_opps = session.scalars(select(ServiceOpportunity)).all()
    assert len(service_opps) > 0
    ledgers = session.scalars(select(PredictionLedger)).all()
    assert len(ledgers) > 0


def test_failure_isolation_enrichment_error_preserves_lead(test_db):
    """Verifies that an unhandled exception in optional ML/enrichment does NOT roll back or delete the lead."""
    session, ws = test_db

    job = ScrapeJob(
        workspace_id=ws.id,
        niche="restaurant",
        country="India",
        state="Mumbai",
        target_lead_count=5,
        sources=["osm_overpass"],
        enrichments=["details"],
        service="website_dev",
        status="RUNNING",
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    fake_records = [
        NormalizedLeadRecord(
            source="osm_overpass",
            source_id="node/test_err_1",
            business_name="Error Cafe 1",
            category="cafe",
            address="Goregaon, Mumbai",
            phone="+91 9820000077",
            website="https://errorcafe1.com",
            raw_data={"lat": 19.16, "lon": 72.85},
        )
    ]

    mock_connector = MagicMock()
    mock_connector.search_leads.return_value = fake_records
    mock_connector.supports_category.return_value = True

    plan = {
        "source": "osm_overpass",
        "query": "cafe",
        "reason": "niche synonym",
        "location": "Goregaon, Mumbai, India",
    }

    with patch("backend.app.worker.get_connectors", return_value={"osm_overpass": mock_connector}), \
         patch("backend.app.intelligence.genuineness.GenuinenessAgent.evaluate_lead_genuineness", side_effect=RuntimeError("ML Engine Crash")), \
         patch("backend.app.services.classification_agent.MultiLabelClassificationAgent.classify_lead", side_effect=RuntimeError("Classifier Crash")):

        execute_single_query_plan(session, job, plan)
        finalize_job_status(session, job, str(job.id))

    # Lead MUST still be persisted and counted despite ML crash
    assert job.leads_scraped == 1
    persisted_leads = session.scalars(select(Lead).where(Lead.job_id == job.id)).all()
    assert len(persisted_leads) == 1
    assert persisted_leads[0].business_name == "Error Cafe 1"


def test_legacy_job_without_enrichments_field(test_db):
    """Verifies that legacy jobs where enrichments is None remain valid and respect service configuration."""
    session, ws = test_db

    job = ScrapeJob(
        workspace_id=ws.id,
        niche="restaurant",
        country="India",
        state="Mumbai",
        target_lead_count=5,
        sources=["osm_overpass"],
        enrichments=None,  # Legacy job
        service=None,
        status="RUNNING",
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    fake_records = [
        NormalizedLeadRecord(
            source="osm_overpass",
            source_id="node/test_legacy_1",
            business_name="Legacy Cafe 1",
            category="cafe",
            address="Goregaon, Mumbai",
            phone="+91 9820000055",
            website="https://legacycafe1.com",
            raw_data={"lat": 19.16, "lon": 72.85},
        )
    ]

    mock_connector = MagicMock()
    mock_connector.search_leads.return_value = fake_records
    mock_connector.supports_category.return_value = True

    plan = {
        "source": "osm_overpass",
        "query": "cafe",
        "reason": "niche synonym",
        "location": "Goregaon, Mumbai, India",
    }

    with patch("backend.app.worker.get_connectors", return_value={"osm_overpass": mock_connector}):
        execute_single_query_plan(session, job, plan)
        finalize_job_status(session, job, str(job.id))

    assert job.leads_scraped == 1
    persisted_leads = session.scalars(select(Lead).where(Lead.job_id == job.id)).all()
    assert len(persisted_leads) == 1
    # When service is None and enrichments is None, optional enrichment is skipped
    service_opps = session.scalars(select(ServiceOpportunity)).all()
    assert len(service_opps) == 0
