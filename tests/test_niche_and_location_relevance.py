import uuid
import pytest
from sqlalchemy import select
from unittest.mock import MagicMock

from backend.app.database import SessionLocal
from backend.app.models import Workspace, ScrapeJob, Lead
from backend.app.sources.base import NormalizedLeadRecord
from backend.app.orchestration.discovery_orchestrator import DiscoveryOrchestrator
from backend.app.intelligence.niche_relevance import NicheRelevanceGate
from backend.app.ingestion.location_normalizer import LocationNormalizer, is_location_relevant


@pytest.fixture
def clean_db():
    import backend.app.models_phase2
    from backend.app.database import Base
    db = SessionLocal()
    Base.metadata.create_all(bind=db.get_bind())
    yield db
    db.close()


def test_niche_relevance_gate_rejects_unrelated_businesses():
    """Verifies that churches, schools, banks, restaurants, and drug marts
    are strictly rejected when searching for Plumbers.
    """
    target_niche = "Plumbers"

    unrelated_candidates = [
        NormalizedLeadRecord(
            source="osm_overpass",
            source_id="c1",
            business_name="St. Michael's Cathedral Basilica",
            category="place_of_worship",
            phone="+14165550001",
            website="https://stmichaelscathedral.com",
            raw_data={"tags": {"amenity": "place_of_worship", "religion": "christian"}},
        ),
        NormalizedLeadRecord(
            source="google_maps",
            source_id="c2",
            business_name="Royal Bank of Canada",
            category="bank",
            phone="+14165550002",
            website="https://rbc.com",
            raw_data={"types": ["bank", "finance", "atm"]},
        ),
        NormalizedLeadRecord(
            source="osm_overpass",
            source_id="c3",
            business_name="Toronto Elementary School",
            category="school",
            phone="+14165550003",
            website="https://torontoschool.edu",
            raw_data={"tags": {"amenity": "school"}},
        ),
        NormalizedLeadRecord(
            source="yelp",
            source_id="c4",
            business_name="Toronto Pizza & Pasta Bistro",
            category="restaurant",
            phone="+14165550004",
            website="https://torontopizza.com",
            raw_data={"categories": [{"title": "Pizza"}]},
        ),
        NormalizedLeadRecord(
            source="google_maps",
            source_id="c5",
            business_name="Shoppers Drug Mart Pharmacy",
            category="pharmacy",
            phone="+14165550005",
            website="https://shoppersdrugmart.ca",
            raw_data={"types": ["pharmacy", "health"]},
        ),
    ]

    for cand in unrelated_candidates:
        decision = NicheRelevanceGate.evaluate_candidate(
            business_name=cand.business_name,
            category=cand.category,
            raw_data=cand.raw_data,
            target_niche=target_niche,
            query_context="plumbers in Toronto",
        )
        assert not decision.is_relevant, f"Candidate '{cand.business_name}' should have been rejected as irrelevant"
        assert decision.confidence_score == 0.0


def test_niche_relevance_gate_accepts_valid_plumbers():
    """Verifies that authentic plumbing variants and contractors are accepted."""
    target_niche = "Plumbers"

    valid_candidates = [
        NormalizedLeadRecord(
            source="google_maps",
            source_id="v1",
            business_name="Toronto Plumbing & Drain Solutions",
            category="Plumber",
            phone="+14165551001",
            website="https://torontoplumbingdrain.com",
            raw_data={"types": ["plumber", "point_of_interest"]},
        ),
        NormalizedLeadRecord(
            source="osm_overpass",
            source_id="v2",
            business_name="Rapid Rooter & Pipe Repair",
            category=None,
            phone="+14165551002",
            website="https://rapidrooter.ca",
            raw_data={"tags": {"craft": "plumber"}},
        ),
        NormalizedLeadRecord(
            source="yelp",
            source_id="v3",
            business_name="GTA Emergency Plumbing Contractors Ltd",
            category="Plumbing Services",
            phone="+14165551003",
            website="https://gtaplumbing.ca",
            raw_data={"categories": [{"title": "Plumbing"}]},
        ),
    ]

    for cand in valid_candidates:
        decision = NicheRelevanceGate.evaluate_candidate(
            business_name=cand.business_name,
            category=cand.category,
            raw_data=cand.raw_data,
            target_niche=target_niche,
            query_context="plumbers in Toronto",
        )
        assert decision.is_relevant, f"Valid candidate '{cand.business_name}' was unexpectedly rejected"
        assert decision.confidence_score >= 0.85


def test_location_normalizer_and_relevance_gate():
    """Tests location parsing and cross-country relevance protection."""
    # 1. Canada location parsing
    ca_loc = LocationNormalizer.parse_location("Toronto, Ontario, Canada")
    assert ca_loc.country == "Canada"
    assert ca_loc.country_code == "CA"
    assert ca_loc.state_or_province == "Ontario"
    assert ca_loc.city == "Toronto"
    assert "Canada" in ca_loc.formatted_location
    assert "United States" not in ca_loc.formatted_location

    # 2. Short Canadian location parsing
    ont_loc = LocationNormalizer.parse_location("Ontario, Canada")
    assert ont_loc.country == "Canada"
    assert ont_loc.state_or_province == "Ontario"

    # 3. UK Location parsing
    uk_loc = LocationNormalizer.parse_location("London, UK")
    assert uk_loc.country == "United Kingdom"
    assert uk_loc.country_code == "GB"

    # 4. Location Relevance Check: UK candidate phone in Canada search
    ok, reason = is_location_relevant(
        candidate_address="100 Main St, Toronto",
        candidate_phone="+442089393730",  # UK phone
        candidate_website="https://example.ca",
        candidate_country="Canada",
        target_hierarchy=ca_loc,
    )
    assert not ok, "Cross-country UK phone must be rejected for Canada search"
    assert "MISMATCH" in reason

    # 5. Location Relevance Check: Valid Canada candidate
    ok_valid, reason_valid = is_location_relevant(
        candidate_address="123 Yonge St, Toronto, ON M4B 1B3, Canada",
        candidate_phone="+14165551234",
        candidate_website="https://torontoplumbers.ca",
        candidate_country="Canada",
        target_hierarchy=ca_loc,
    )
    assert ok_valid
    assert reason_valid == "LOCATION_RELEVANT"


def test_orchestrator_integrates_niche_and_location_gates(clean_db):
    """Verifies that Stage 1 rejects unrelated churches/banks and backfills valid plumbers."""
    ws = clean_db.scalar(select(Workspace).limit(1))
    if not ws:
        ws = Workspace(name="Test Relevance WS")
        clean_db.add(ws)
        clean_db.commit()
        clean_db.refresh(ws)

    job = ScrapeJob(
        workspace_id=ws.id,
        niche="Plumbers",
        country="Canada",
        region="Ontario",
        state="Toronto",
        target_lead_count=2,  # Target N = 2
        status="PENDING",
        sources=["google_maps"],
    )
    clean_db.add(job)
    clean_db.commit()
    clean_db.refresh(job)

    # Batch 1: 1 Cathedral + 1 Bank + 1 Valid Plumber
    batch_1 = [
        NormalizedLeadRecord(
            source="google_maps",
            source_id="b1_church",
            business_name=f"St. James Church {uuid.uuid4().hex[:4]}",
            category="place_of_worship",
            phone="+14165550001",
            website="https://stjameschurch.ca",
            address="65 Church St, Toronto, ON, Canada",
            raw_data={"types": ["church", "place_of_worship"]},
        ),
        NormalizedLeadRecord(
            source="google_maps",
            source_id="b1_bank",
            business_name=f"TD Canada Trust {uuid.uuid4().hex[:4]}",
            category="bank",
            phone="+14165550002",
            website="https://td.com",
            address="55 King St, Toronto, ON, Canada",
            raw_data={"types": ["bank", "finance"]},
        ),
        NormalizedLeadRecord(
            source="google_maps",
            source_id=f"b1_plumber_{uuid.uuid4().hex[:6]}",
            business_name=f"Metro Toronto Plumbing Experts {uuid.uuid4().hex[:4]}",
            category="Plumber",
            phone=f"+1416555{uuid.uuid4().hex[:4]}",
            website=f"https://metroplumbingtoronto_{uuid.uuid4().hex[:4]}.com",
            address="100 Queen St, Toronto, ON, Canada",
            raw_data={"types": ["plumber"]},
        ),
    ]

    # Batch 2: 1 Valid Plumber (backfilling the deficit)
    batch_2 = [
        NormalizedLeadRecord(
            source="google_maps",
            source_id=f"b2_plumber_{uuid.uuid4().hex[:6]}",
            business_name=f"Ontario Drain & Plumbing Co {uuid.uuid4().hex[:4]}",
            category="Plumber",
            phone=f"+1416555{uuid.uuid4().hex[:4]}",
            website=f"https://ontarioplumbingco_{uuid.uuid4().hex[:4]}.ca",
            address="200 Bay St, Toronto, ON, Canada",
            raw_data={"types": ["plumber"]},
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

    orchestrator.run_discovery()

    clean_db.refresh(job)
    assert job.status == "COMPLETED"
    assert job.leads_scraped == 2

    # Verify only the 2 plumbers were saved
    leads = clean_db.scalars(select(Lead).where(Lead.job_id == job.id)).all()
    assert len(leads) == 2
    for l in leads:
        assert "Plumbing" in l.business_name
        assert "Church" not in l.business_name
        assert "TD Canada" not in l.business_name
