from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.enrichment.enrichment_engine import DeepFeatureEnrichmentEngine
from backend.app.ingestion.lifecycle import LifecycleResolver, LifecycleState
from backend.app.models_phase2 import Base as Phase2Base
from backend.app.models_phase2 import CanonicalLead
from backend.app.models_services import ServiceOpportunity
from backend.app.services.classification_agent import MultiLabelClassificationAgent
from backend.app.sources.data_axle import DataAxleConnector
from backend.app.sources.foursquare import FoursquareConnector
from backend.app.sources.google_maps import GooglePlacesConnector


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Phase2Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_multi_provider_pipeline_ingestion_and_classification(db_session):
    """End-to-end trace: 3 Providers -> Normalization -> Canonical Resolution -> Enrichment -> Classification -> DB Persistence."""
    # 1. Instantiate Connectors
    gp = GooglePlacesConnector(api_key="mock_key")
    fq = FoursquareConnector(api_key="mock_key")
    da = DataAxleConnector(api_key="mock_key")

    # 2. Mock Raw Provider Responses
    gp_payload = {
        "place_id": "gp_nairobi_001",
        "name": "Nairobi Solar Solutions Ltd",
        "formatted_address": "Ngong Road, Nairobi, Kenya",
        "formatted_phone_number": "+254 700 112233",
        "website": "https://www.nairobisolar.co.ke",
        "types": ["solar_installer"],
    }
    fq_payload = {
        "fsq_id": "fq_lagos_001",
        "name": "Lagos Web Agency",
        "location": {
            "formatted_address": "Ikeja, Lagos, Nigeria",
            "locality": "Lagos",
            "country": "Nigeria",
        },
        "tel": "+234 802 345 6789",
        "website": None,
        "categories": [{"name": "Web Design"}],
    }
    da_payload = {
        "id": "da_joburg_001",
        "name": "JoBurg Accounting Services",
        "street": "Sandton City",
        "city": "Johannesburg",
        "country": "South Africa",
        "phone": "+27 11 987 6543",
        "website": "https://www.joburgaccounting.co.za",
        "primary_sic_description": "Accounting Services",
    }

    rec1 = gp.parse_place_record(gp_payload)
    rec2 = fq.parse_foursquare_record(fq_payload)
    rec3 = da.parse_data_axle_record(da_payload)

    assert rec1.source == "google_places"
    assert rec2.source == "foursquare"
    assert rec3.source == "data_axle"

    # 3. Process Records Through LifecycleResolver
    resolver = LifecycleResolver()

    c1, obs1, s1 = resolver.process_observation(db_session, rec1)
    c2, obs2, s2 = resolver.process_observation(db_session, rec2)
    c3, obs3, s3 = resolver.process_observation(db_session, rec3)

    assert s1 == LifecycleState.NEW
    assert s2 == LifecycleState.NEW
    assert s3 == LifecycleState.NEW

    total_canonicals = db_session.query(CanonicalLead).count()
    assert total_canonicals == 3

    # 4. Multi-Label Classification & Database Persistence for Each Lead
    enrichment_engine = DeepFeatureEnrichmentEngine()

    for canonical in [c1, c2, c3]:
        # Enrichment
        features = enrichment_engine.enrich_lead(canonical.id, rec1)
        assert features is not None

        # Classification
        payload = {
            "canonical_lead_id": canonical.id,
            "business_name": canonical.business_name,
            "website": canonical.canonical_domain,
            "phone": canonical.canonical_phone,
            "email": canonical.canonical_email,
            "country": canonical.country or "Kenya",
            "region_state": canonical.state or "Nairobi",
            "city": canonical.city or "Nairobi",
            "niche": canonical.industry or "General",
            "business_type": "SMALL_BUSINESS",
            "genuineness_probability": 0.95,
            "genuineness_decision": "GENUINE",
            "website_state": "active" if canonical.canonical_domain else "no_website",
            "ssl_valid": "Y" if canonical.canonical_domain else "N",
            "facebook_ads_detected": "N",
        }

        classified = MultiLabelClassificationAgent.classify_lead(payload)
        s_map = classified.get("service_classifications", {})

        for s_name, s_info in s_map.items():
            stype_upper = s_name.upper()
            so = ServiceOpportunity(
                canonical_lead_id=canonical.id,
                service_type=stype_upper,
                eligible="Y" if s_info.get("eligible") else "N",
                score=float(s_info.get("score", 0.0)),
                confidence=s_info.get("confidence", 0.85),
                reasons=json.dumps(s_info.get("reasons", [])),
            )
            db_session.add(so)
        db_session.commit()

    # 5. Assert service_opportunities rows created (3 canonicals * 4 services = 12 records)
    total_so = db_session.query(ServiceOpportunity).count()
    assert total_so == 12
