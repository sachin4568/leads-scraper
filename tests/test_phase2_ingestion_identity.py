from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.ingestion.ingestion import (
    DirectoryAdapter,
    FacebookAdapter,
    GooglePlacesAdapter,
    YelpAdapter,
)
from backend.app.ingestion.intelligence_foundations import (
    HumanFeedbackManager,
    NicheProfileRegistry,
)
from backend.app.ingestion.lifecycle import LifecycleResolver, LifecycleState
from backend.app.models_phase2 import (
    Base,
    CanonicalLead,
    HumanOutcomeEventRecord,
    LeadChangeHistory,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_source_adapter_normalization() -> None:
    gp_adapter = GooglePlacesAdapter()
    raw = gp_adapter.normalize_payload(
        {
            "place_id": "ChIJ001",
            "name": "Apex Dental Clinic",
            "formatted_phone_number": "+91 98970 01001",
            "website": "https://www.apexdental.com",
            "types": ["Dental Clinics"],
        }
    )
    assert raw.source_name == "google_places"
    assert raw.source_record_id == "ChIJ001"
    assert raw.business_name == "Apex Dental Clinic"
    assert raw.get_idempotency_key() == "google_places:ChIJ001"


def test_idempotent_ingestion(db_session) -> None:
    resolver = LifecycleResolver()
    gp_adapter = GooglePlacesAdapter()
    raw = gp_adapter.normalize_payload(
        {
            "place_id": "ChIJ_idempotent_001",
            "name": "City HVAC Center",
            "formatted_phone_number": "+91 98970 05005",
            "website": "https://www.cityhvac.com",
            "types": ["HVAC Services"],
        }
    )

    c1, obs1, state1 = resolver.process_observation(db_session, raw)
    assert state1 == LifecycleState.NEW

    c2, obs2, state2 = resolver.process_observation(db_session, raw)
    assert state2 == LifecycleState.DUPLICATE
    assert c1.id == c2.id


def test_cross_source_consolidation(db_session) -> None:
    resolver = LifecycleResolver()
    gp_adapter = GooglePlacesAdapter()
    yelp_adapter = YelpAdapter()

    raw_gp = gp_adapter.normalize_payload(
        {
            "place_id": "ChIJ_cross_001",
            "name": "Urban Plumbing Group",
            "city": "Mohali",
            "formatted_phone_number": "+91 98970 06006",
            "website": "https://www.urbanplumbing.com",
            "types": ["Plumbing Contractors"],
        }
    )
    c1, _, _ = resolver.process_observation(db_session, raw_gp)

    raw_yelp = yelp_adapter.normalize_payload(
        {
            "id": "yelp_cross_001",
            "name": "Urban Plumbing",
            "location": {"city": "Mohali"},
            "display_phone": "+91 98970 06006",
            "url": "https://www.urbanplumbing.com/yelp",
            "categories": [{"title": "Plumbing Contractors"}],
        }
    )
    c2, _, state2 = resolver.process_observation(db_session, raw_yelp)

    assert c1.id == c2.id
    assert db_session.query(CanonicalLead).count() == 1
    assert c2.observation_count == 2


def test_field_update_and_change_history(db_session) -> None:
    resolver = LifecycleResolver()
    gp_adapter = GooglePlacesAdapter()
    fb_adapter = FacebookAdapter()

    raw1 = gp_adapter.normalize_payload(
        {
            "place_id": "ChIJ_update_001",
            "name": "Nova Dental Studio",
            "city": "Haridwar",
            "website": "https://www.oldsite.com",
            "formatted_phone_number": "+91 98970 07007",
            "types": ["Dental Clinics"],
        }
    )
    c1, _, _ = resolver.process_observation(db_session, raw1)

    raw2 = fb_adapter.normalize_payload(
        {
            "page_id": "fb_update_001",
            "name": "Nova Dental Studio",
            "location": {"city": "Haridwar"},
            "website": "https://www.newsite.com",
            "phone": "+91 98970 07007",
            "category": "Dental Clinics",
        }
    )
    c2, obs2, state2 = resolver.process_observation(db_session, raw2)

    assert state2 == LifecycleState.UPDATED
    assert c2.canonical_domain == "https://www.newsite.com"

    history_entries = (
        db_session.query(LeadChangeHistory)
        .filter(LeadChangeHistory.canonical_lead_id == c1.id)
        .all()
    )
    assert len(history_entries) == 1
    assert history_entries[0].field_name == "canonical_domain"
    assert history_entries[0].old_value == "https://www.oldsite.com"
    assert history_entries[0].new_value == "https://www.newsite.com"


def test_zero_false_merge_different_cities(db_session) -> None:
    resolver = LifecycleResolver()
    dir_adapter = DirectoryAdapter()

    raw1 = dir_adapter.normalize_payload(
        {
            "source_name": "directory",
            "id": "dir_001",
            "business_name": "Apex Dental Clinic",
            "city": "Dehradun",
            "phone": "+91 98970 01001",
            "website": "https://www.apexdentaldehradun.com",
            "industry": "Dental Clinics",
        }
    )
    c1, _, _ = resolver.process_observation(db_session, raw1)

    raw2 = dir_adapter.normalize_payload(
        {
            "source_name": "directory",
            "id": "dir_002",
            "business_name": "Apex Dental Clinic",
            "city": "Haridwar",
            "phone": "+91 98970 02002",
            "website": "https://www.apexdentalharidwar.com",
            "industry": "Dental Clinics",
        }
    )
    c2, _, _ = resolver.process_observation(db_session, raw2)

    assert c1.id != c2.id
    assert db_session.query(CanonicalLead).count() == 2


def test_human_feedback_preservation(db_session) -> None:
    resolver = LifecycleResolver()
    gp_adapter = GooglePlacesAdapter()
    raw = gp_adapter.normalize_payload(
        {
            "place_id": "ChIJ_fb_001",
            "name": "Sterling HVAC",
            "types": ["HVAC Services"],
        }
    )
    c1, _, _ = resolver.process_observation(db_session, raw)

    record = HumanFeedbackManager.record_feedback(
        db=db_session,
        canonical_lead_id=c1.id,
        original_prediction="GENUINE",
        original_probability=0.92,
        model_version="v1.1_phase1_stratified",
        human_outcome="GENUINE_PRODUCTIVE",
        reason="Owner booked meeting",
    )
    assert record.human_outcome == "GENUINE_PRODUCTIVE"
    assert record.original_prediction == "GENUINE"
    assert db_session.query(HumanOutcomeEventRecord).count() == 1


def test_niche_registry_15_niches() -> None:
    registry = NicheProfileRegistry()
    assert len(registry.profiles) == 15
    profile = registry.get_profile("Dental Clinics")
    assert profile is not None
    assert "Website Redesign" in profile.relevant_services
