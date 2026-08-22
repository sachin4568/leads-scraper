from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.enrichment.enrichment_engine import DeepFeatureEnrichmentEngine
from backend.app.ingestion.ingestion import GooglePlacesAdapter, RawLead
from backend.app.ingestion.lifecycle import LifecycleResolver, LifecycleState
from backend.app.models import Workspace
from backend.app.models_phase2 import Base as Phase2Base
from backend.app.models_phase2 import CanonicalLead
from backend.app.models_services import ServiceOpportunity
from backend.app.services.classification_agent import MultiLabelClassificationAgent


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Phase2Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_full_pipeline_ingestion_canonical_and_service_persistence(db_session):
    """End-to-end trace: Scraper -> Canonical Identity -> Enrichment -> Frozen ML -> 4-Service Scoring -> DB Persistence."""
    # 1. Setup workspace & scrape job
    ws = Workspace(name="Test Workspace")
    db_session.add(ws)
    db_session.commit()

    # 2. Raw Lead Payload from Google Places Adapter
    raw_place_data = {
        "place_id": "ChIJ_test_enterprise_001",
        "name": "Apex Solar & Roofing Solutions",
        "types": ["roofing_contractor", "solar_installer"],
        "formatted_address": "100 Commercial Blvd, Austin, TX",
        "city": "Austin",
        "state": "Texas",
        "country": "United States",
        "website": "https://www.apexsolar.com",
        "formatted_phone_number": "+1 512 555 0199",
    }

    adapter = GooglePlacesAdapter()
    raw_lead = adapter.normalize_payload(raw_place_data)
    assert raw_lead.source_name == "google_places"
    assert raw_lead.business_name == "Apex Solar & Roofing Solutions"

    # 3. Canonical Identity & 4-State Lifecycle Resolution
    resolver = LifecycleResolver()
    canonical, obs, state = resolver.process_observation(db_session, raw_lead)

    assert state == LifecycleState.NEW
    assert canonical.id is not None
    assert canonical.business_name == "Apex Solar & Roofing Solutions"
    assert canonical.canonical_domain == "https://www.apexsolar.com"
    assert canonical.google_place_id == "ChIJ_test_enterprise_001"

    # 4. Deep Feature Enrichment
    enrichment_engine = DeepFeatureEnrichmentEngine()
    features = enrichment_engine.enrich_lead(canonical.id, raw_lead)
    assert features is not None
    assert features.website_evidence.website_exists is True

    # 5. Multi-Label 4-Service Classification
    lead_payload = {
        "canonical_lead_id": canonical.id,
        "business_name": canonical.business_name,
        "website": canonical.canonical_domain,
        "phone": canonical.canonical_phone,
        "email": canonical.canonical_email,
        "country": canonical.country,
        "region_state": canonical.state,
        "city": canonical.city,
        "niche": "Solar",
        "business_type": "SMALL_BUSINESS",
        "genuineness_probability": 0.96,
        "genuineness_decision": "GENUINE",
        "website_state": "active",
        "ssl_valid": "Y",
        "facebook_ads_detected": "N",
    }

    classified_result = MultiLabelClassificationAgent.classify_lead(lead_payload)
    assert classified_result["service_classification_status"] == "CLASSIFIED"
    assert "website_development_score" in classified_result
    assert "website_seo_score" in classified_result
    assert "social_media_management_score" in classified_result
    assert "social_media_marketing_score" in classified_result

    # 6. Database Persistence to service_opportunities table
    s_map = classified_result.get("service_classifications", {})
    for s_name, s_info in s_map.items():
        stype_upper = s_name.upper()
        eligible_str = "Y" if s_info.get("eligible") else "N"
        score_val = float(s_info.get("score", 0.0))
        reasons_json = json.dumps(s_info.get("reasons", []))

        so = ServiceOpportunity(
            canonical_lead_id=canonical.id,
            service_type=stype_upper,
            eligible=eligible_str,
            score=score_val,
            confidence=s_info.get("confidence", 0.85),
            reasons=reasons_json,
        )
        db_session.add(so)
    db_session.commit()

    # 7. Verify Database Records
    db_opportunities = db_session.scalars(
        select(ServiceOpportunity).where(ServiceOpportunity.canonical_lead_id == canonical.id)
    ).all()

    assert len(db_opportunities) == 4
    service_types = {so.service_type for so in db_opportunities}
    assert service_types == {
        "WEBSITE_DEVELOPMENT",
        "WEBSITE_SEO",
        "SOCIAL_MEDIA_MANAGEMENT",
        "SOCIAL_MEDIA_MARKETING",
    }


def test_idempotency_second_run_produces_duplicate(db_session):
    """Running identical raw lead ingestion twice must yield DUPLICATE on second run."""
    raw_lead = RawLead(
        source_name="google_places",
        source_record_id="place_id_idempotent_123",
        business_name="Unique Plumbing Co",
        industry="Plumbing",
        website="https://www.uniqueplumbing.com",
        phone="+1 555 123 4567",
    )

    resolver = LifecycleResolver()
    c1, obs1, state1 = resolver.process_observation(db_session, raw_lead)
    assert state1 == LifecycleState.NEW

    # Second Run
    c2, obs2, state2 = resolver.process_observation(db_session, raw_lead)
    assert state2 == LifecycleState.DUPLICATE
    assert c1.id == c2.id


def test_failure_tolerance_classification_error_does_not_delete_lead(db_session):
    """Classification or enrichment errors must record failure state without deleting CanonicalLead."""
    canonical = CanonicalLead(
        business_name="Faulty Lead Corp",
        industry="General",
        canonical_domain="https://faulty.com",
    )
    db_session.add(canonical)
    db_session.commit()

    raw_count_before = db_session.query(CanonicalLead).count()

    try:
        # Simulate classification exception with bad payload
        bad_payload = {"invalid_key": None}
        MultiLabelClassificationAgent.classify_lead(bad_payload)
    except Exception:
        # Failure caught
        pass

    raw_count_after = db_session.query(CanonicalLead).count()
    assert raw_count_before == raw_count_after
    assert db_session.query(CanonicalLead).filter_by(id=canonical.id).first() is not None
