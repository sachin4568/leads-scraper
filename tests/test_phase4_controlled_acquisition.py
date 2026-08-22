from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.enrichment.data_quality_audit import DataQualityAuditor
from backend.app.enrichment.enrichment_engine import DataState, DeepFeatureEnrichmentEngine
from backend.app.ingestion.ingestion import DirectoryAdapter, GooglePlacesAdapter
from backend.app.ingestion.lifecycle import LifecycleResolver
from backend.app.models_phase2 import Base


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_deep_feature_enrichment_engine(db_session) -> None:
    gp_adapter = GooglePlacesAdapter()
    raw = gp_adapter.normalize_payload(
        {
            "place_id": "ChIJ_enrich_001",
            "name": "Apex Dental Clinic",
            "formatted_phone_number": "+91 98970 01001",
            "website": "https://www.apexdental.com",
            "types": ["Dental Clinics"],
        }
    )
    resolver = LifecycleResolver()
    canonical, _, _ = resolver.process_observation(db_session, raw)

    enrichment_engine = DeepFeatureEnrichmentEngine()
    snap = enrichment_engine.enrich_lead(canonical.id, raw)

    assert snap.business_name == "Apex Dental Clinic"
    assert snap.niche == "Dental Clinics"
    assert snap.website_evidence.website_exists is True
    assert snap.website_evidence.ssl_valid is True
    assert len(snap.contacts) == 1
    assert snap.contacts[0].role == "GENERIC"
    assert snap.maturity_evidence.category == "SMALL_BUSINESS"


def test_missing_data_state_handling(db_session) -> None:
    dir_adapter = DirectoryAdapter()
    raw_no_web = dir_adapter.normalize_payload(
        {
            "source_name": "directory",
            "id": "dir_no_web",
            "business_name": "Local Plumbing",
            "industry": "Plumbing Contractors",
            "phone": "+91 98970 02002",
        }
    )
    resolver = LifecycleResolver()
    canonical, _, _ = resolver.process_observation(db_session, raw_no_web)

    enrichment_engine = DeepFeatureEnrichmentEngine()
    snap = enrichment_engine.enrich_lead(canonical.id, raw_no_web)

    assert snap.website_evidence.website_exists is False
    assert snap.website_evidence.http_status is None
    assert snap.social_evidence.instagram_state == DataState.MISSING


def test_data_quality_audit_metrics(db_session) -> None:
    gp_adapter = GooglePlacesAdapter()
    raw1 = gp_adapter.normalize_payload(
        {
            "name": "Biz 1",
            "types": ["Dental Clinics"],
            "website": "https://b1.com",
            "formatted_phone_number": "+91 90000 00001",
        }
    )
    raw2 = gp_adapter.normalize_payload({"name": "Biz 2", "types": ["HVAC Services"]})

    enrichment_engine = DeepFeatureEnrichmentEngine()
    snap1 = enrichment_engine.enrich_lead("c1", raw1)
    snap2 = enrichment_engine.enrich_lead("c2", raw2)

    report = DataQualityAuditor.audit_enrichment_batch([snap1, snap2])

    assert report.total_records == 2
    assert report.phone_completeness_pct == 50.0
    assert report.website_completeness_pct == 50.0
    assert report.overall_completeness_pct == 33.33
    assert report.validity_pct == 50.0
    assert report.consistency_pct == 100.0
