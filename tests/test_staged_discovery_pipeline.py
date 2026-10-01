import uuid
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import select

from backend.app.database import SessionLocal
from backend.app.models import Workspace, ScrapeJob, Lead, EvidenceRecord
from backend.app.sources.base import NormalizedLeadRecord
from backend.app.orchestration.discovery_orchestrator import DiscoveryOrchestrator, is_viable_candidate


@pytest.fixture
def clean_db():
    import backend.app.models_phase2
    from backend.app.database import Base
    db = SessionLocal()
    Base.metadata.create_all(bind=db.get_bind())
    yield db
    db.close()


def test_is_viable_candidate_filtering():
    """Verifies that candidates without any contact vectors are rejected as junk."""
    # 1. Junk: Business name only (no phone, website, email, or address)
    junk_1 = NormalizedLeadRecord(
        source="google_maps",
        source_id="j1",
        business_name="Acme Corporation",
        phone=None,
        website=None,
        email=None,
        address=None,
    )
    assert not is_viable_candidate(junk_1), "Company name only must be eliminated as junk"

    # 2. Junk: Unknown / generic business name
    junk_2 = NormalizedLeadRecord(
        source="osm_overpass",
        source_id="j2",
        business_name="Unknown Business",
        phone="+1234567890",
        website="https://acme.com",
    )
    assert not is_viable_candidate(junk_2), "Generic 'Unknown Business' must be eliminated"

    # 3. Viable: Business name + website
    viable_web = NormalizedLeadRecord(
        source="google_maps",
        source_id="v1",
        business_name="Metro Plumbing",
        website="https://metroplumbing.com",
        phone=None,
        email=None,
        address=None,
    )
    assert is_viable_candidate(viable_web), "Business with website must be viable"

    # 4. Viable: Business name + phone
    viable_phone = NormalizedLeadRecord(
        source="osm_overpass",
        source_id="v2",
        business_name="City Cafe",
        phone="+15551234567",
        website=None,
        email=None,
        address=None,
    )
    assert is_viable_candidate(viable_phone), "Business with phone must be viable"

    # 5. Viable: Business name + physical address
    viable_addr = NormalizedLeadRecord(
        source="osm_overpass",
        source_id="v3",
        business_name="Apex Dental Care",
        address="123 Main Street, Suite 400",
        phone=None,
        website=None,
        email=None,
    )
    assert is_viable_candidate(viable_addr), "Business with address must be viable"


def test_staged_orchestrator_backfills_discarded_junk_leads(clean_db):
    """
    Verifies that when Stage 1 encounters junk leads (company name only),
    it discards them and backfills from subsequent batches until target N is reached.
    """
    ws = clean_db.scalar(select(Workspace).limit(1))
    if not ws:
        ws = Workspace(name="Test Staged WS")
        clean_db.add(ws)
        clean_db.commit()
        clean_db.refresh(ws)

    job = ScrapeJob(
        workspace_id=ws.id,
        niche="Plumber",
        country="United States",
        region="California",
        state="San Francisco",
        target_lead_count=2,  # Target N = 2 viable leads
        status="PENDING",
        sources=["google_maps"],
    )
    clean_db.add(job)
    clean_db.commit()
    clean_db.refresh(job)

    # Batch 1 returns: 1 Viable Lead + 2 Junk Leads (company name only)
    batch_1 = [
        NormalizedLeadRecord(
            source="google_maps",
            source_id=f"j1_{uuid.uuid4().hex[:6]}",
            business_name=f"Junk Plumber 1 {uuid.uuid4().hex[:4]}",
            phone=None,
            website=None,
            email=None,
            address=None,
        ),
        NormalizedLeadRecord(
            source="google_maps",
            source_id=f"v1_{uuid.uuid4().hex[:6]}",
            business_name=f"Viable Plumber 1 {uuid.uuid4().hex[:4]}",
            phone=f"+1415555{uuid.uuid4().hex[:4]}",
            website=f"https://sfplumbing1_{uuid.uuid4().hex[:4]}.com",
            address="100 Mission St, San Francisco, CA, USA",
        ),
        NormalizedLeadRecord(
            source="google_maps",
            source_id=f"j2_{uuid.uuid4().hex[:6]}",
            business_name=f"Junk Plumber 2 {uuid.uuid4().hex[:4]}",
            phone="",
            website="",
            email="",
            address="",
        ),
    ]

    # Batch 2 returns: 1 Viable Lead (satisfying the remaining N-1 space)
    batch_2 = [
        NormalizedLeadRecord(
            source="google_maps",
            source_id=f"v2_{uuid.uuid4().hex[:6]}",
            business_name=f"Viable Plumber 2 {uuid.uuid4().hex[:4]}",
            phone=f"+1415555{uuid.uuid4().hex[:4]}",
            website=f"https://sfplumbing2_{uuid.uuid4().hex[:4]}.com",
            address="200 Market St, San Francisco, CA, USA",
        ),
    ]

    mock_conn = MagicMock()
    mock_conn.supports_category.return_value = True
    mock_conn.search_leads.side_effect = [batch_1, batch_2]

    orchestrator = DiscoveryOrchestrator(
        db=clean_db,
        job=job,
        connectors={"google_maps": mock_conn},
        max_request_budget=10,
    )

    # Execute full staged discovery
    orchestrator.run_discovery()

    clean_db.refresh(job)
    assert job.status == "COMPLETED"
    assert job.completion_reason == "TARGET_REACHED"
    assert job.leads_scraped == 2

    # Verify only the 2 viable leads were persisted in the DB
    leads = clean_db.scalars(select(Lead).where(Lead.job_id == job.id)).all()
    assert len(leads) == 2
    for lead in leads:
        assert "Viable Plumber" in lead.business_name
        assert lead.phone is not None
        assert lead.website is not None

    # Verify EvidenceRecords exist
    ev_records = clean_db.scalars(select(EvidenceRecord).where(EvidenceRecord.lead_id.in_([l.id for l in leads]))).all()
    assert len(ev_records) > 0
