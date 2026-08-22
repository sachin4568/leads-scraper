from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.enrichment.enrichment_engine import DeepFeatureEnrichmentEngine
from backend.app.enrichment.scale_auditor import (
    CrossFieldConsistencyChecker,
    MissingDataSemantic,
    ProvenanceType,
    ScaleDataQualityAuditor,
)
from backend.app.ingestion.ingestion import DirectoryAdapter, GooglePlacesAdapter
from backend.app.ingestion.lifecycle import LifecycleResolver, LifecycleState
from backend.app.models_phase2 import Base, LeadChangeHistory


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_provenance_and_missing_data_semantics(db_session) -> None:
    gp_adapter = GooglePlacesAdapter()
    raw = gp_adapter.normalize_payload(
        {
            "place_id": "ChIJ_scale_001",
            "name": "Apex Dental Studio",
            "types": ["Dental Clinics"],
            "city": "Dehradun",
            "formatted_phone_number": "+91 98970 01001",
        }
    )
    resolver = LifecycleResolver()
    canonical, _, state = resolver.process_observation(db_session, raw)

    enrichment_engine = DeepFeatureEnrichmentEngine()
    snap = enrichment_engine.enrich_lead(canonical.id, raw)

    assert state == LifecycleState.NEW
    assert snap.website_evidence.website_exists is False

    report = ScaleDataQualityAuditor.audit_scale_batch(
        [snap], provenance=ProvenanceType.REAL_VERIFIED_SOURCE
    )
    assert report.total_canonical_businesses == 1
    assert report.provenance_distribution["REAL_VERIFIED_SOURCE"] == 1
    assert report.field_coverage["website"][MissingDataSemantic.BUSINESSALLY_MISSING.value] == 1


def test_deduplication_reingestion_and_field_update_deltas(db_session) -> None:
    gp_adapter = GooglePlacesAdapter()
    p1 = gp_adapter.normalize_payload(
        {
            "place_id": "ChIJ_dedup_100",
            "name": "Pinnacle Plumbing",
            "types": ["Plumbing Contractors"],
            "city": "Mohali",
            "formatted_phone_number": "+91 98970 02002",
            "website": "https://www.pinnacleplumbing.com",
        }
    )
    resolver = LifecycleResolver()
    c1, _, s1 = resolver.process_observation(db_session, p1)
    assert s1 == LifecycleState.NEW

    # 1. Repeat Ingestion -> EXISTING / DUPLICATE
    c2, _, s2 = resolver.process_observation(db_session, p1)
    assert s2 in (LifecycleState.EXISTING, LifecycleState.DUPLICATE)
    assert c2.id == c1.id

    # 2. Changed Ingestion -> UPDATED with delta history
    dir_adapter = DirectoryAdapter()
    p2 = dir_adapter.normalize_payload(
        {
            "id": "dir_dedup_100",
            "business_name": "Pinnacle Plumbing",
            "industry": "Plumbing Contractors",
            "city": "Mohali",
            "phone": "+91 98970 02002",
            "website": "https://www.pinnacleplumbing_new.com",
        }
    )
    c3, _, s3 = resolver.process_observation(db_session, p2)
    assert s3 == LifecycleState.UPDATED
    assert c3.id == c1.id

    history_entries = (
        db_session.query(LeadChangeHistory)
        .filter(LeadChangeHistory.canonical_lead_id == c1.id)
        .all()
    )
    field_names = [h.field_name for h in history_entries]
    assert "canonical_domain" in field_names or "website" in field_names


def test_cross_field_consistency_checker(db_session) -> None:
    gp_adapter = GooglePlacesAdapter()
    raw = gp_adapter.normalize_payload(
        {
            "place_id": "ChIJ_cons_001",
            "name": "Himalayan Roofing",
            "types": ["Roofing Specialists"],
            "city": "Haridwar",
            "formatted_address": "Main Road, Dehradun",  # City mismatch
        }
    )
    enrichment_engine = DeepFeatureEnrichmentEngine()
    snap = enrichment_engine.enrich_lead("c_cons", raw)

    c_res = CrossFieldConsistencyChecker.check_lead_consistency(snap)
    assert c_res.is_clean is False
    assert len(c_res.warnings) > 0
