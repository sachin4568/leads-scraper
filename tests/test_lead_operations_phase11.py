from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker

from backend.app.api import current_workspace_id
from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import EvidenceRecord, Lead, Workspace
from backend.app.models_phase2 import Base as Phase2Base
from backend.app.models_services import Base as ServicesBase


@pytest.fixture
def db_session():
    """Isolated in-memory SQLite session for testing with StaticPool and multi-threading support."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    Phase2Base.metadata.create_all(bind=engine)
    ServicesBase.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_setup(db_session: Session):
    """Seed workspace and a mixed set of 6 test leads with rich intelligence and evidence."""
    workspace = Workspace(name="Operations Test Workspace")
    db_session.add(workspace)
    db_session.commit()
    db_session.refresh(workspace)

    # Lead 1: High Opportunity, No Website, Has Phone
    lead1 = Lead(
        workspace_id=workspace.id,
        business_name="Apex Dental Care",
        phone="+1-555-111-2222",
        email=None,
        website=None,
        genuineness_score=0.90,
        workflow_status="NEW",
    )
    # Lead 2: Low Opportunity, Has HTTPS Website, Verified
    lead2 = Lead(
        workspace_id=workspace.id,
        business_name="Bright Smile Clinic",
        phone="+1-555-333-4444",
        email="contact@brightsmile.com",
        website="https://brightsmile.com",
        genuineness_score=0.95,
        workflow_status="REVIEWED",
    )
    # Lead 3: Very High Opportunity, Unverified Website, Has Conflict
    lead3 = Lead(
        workspace_id=workspace.id,
        business_name="Downtown Orthodontics",
        phone="+1-555-555-6666",
        email="info@downtownortho.com",
        website="http://downtownortho.com",
        genuineness_score=0.80,
        workflow_status="CONTACTED",
    )
    # Lead 4: Medium Opportunity, Has WhatsApp & Social
    lead4 = Lead(
        workspace_id=workspace.id,
        business_name="Elite Dental Spa",
        phone="+1-555-777-8888",
        email=None,
        website=None,
        genuineness_score=0.85,
        workflow_status="QUALIFIED",
    )
    # Lead 5: Minimal Opportunity, Complete profile
    lead5 = Lead(
        workspace_id=workspace.id,
        business_name="Family Dental Group",
        phone="+1-555-999-0000",
        email="hello@familydental.com",
        website="https://familydental.com",
        genuineness_score=0.98,
        workflow_status="CONVERTED",
    )

    db_session.add_all([lead1, lead2, lead3, lead4, lead5])
    db_session.commit()
    for l in [lead1, lead2, lead3, lead4, lead5]:
        db_session.refresh(l)

    # Add Evidence Records
    # Lead 1: VERY_HIGH Opportunity (no website, phone available)
    db_session.add(
        EvidenceRecord(
            workspace_id=workspace.id,
            lead_id=lead1.id,
            field_name="lead_intelligence",
            status="VERY_HIGH",
            confidence_score=90,
            source="LEAD_INTELLIGENCE_ENGINE",
            details={
                "overall_opportunity_score": 88,
                "opportunity_category": "VERY_HIGH",
                "top_reasons": ["No website detected", "Direct phone available"],
                "contactability_score": 50,
                "website_opportunity_score": 100,
            },
        )
    )

    # Lead 2: LOW Opportunity (has modern site)
    db_session.add(
        EvidenceRecord(
            workspace_id=workspace.id,
            lead_id=lead2.id,
            field_name="website",
            status="ACCEPT",
            confidence_score=95,
            source="ZERO_BUDGET_VERIFIED",
            details={"verified_url": "https://brightsmile.com"},
        )
    )
    db_session.add(
        EvidenceRecord(
            workspace_id=workspace.id,
            lead_id=lead2.id,
            field_name="lead_intelligence",
            status="LOW",
            confidence_score=90,
            source="LEAD_INTELLIGENCE_ENGINE",
            details={
                "overall_opportunity_score": 30,
                "opportunity_category": "LOW",
                "top_reasons": ["Active HTTPS website", "Modern SEO metadata"],
                "contactability_score": 80,
            },
        )
    )

    # Lead 3: VERY_HIGH with conflict
    db_session.add(
        EvidenceRecord(
            workspace_id=workspace.id,
            lead_id=lead3.id,
            field_name="conflicts",
            status="WARNING",
            confidence_score=70,
            source="WEBSITE_ENRICHMENT",
            details={"phone": {"osm_value": "+1-555-555-6666", "website_value": "+1-555-000-1111"}},
        )
    )
    db_session.add(
        EvidenceRecord(
            workspace_id=workspace.id,
            lead_id=lead3.id,
            field_name="lead_intelligence",
            status="VERY_HIGH",
            confidence_score=85,
            source="LEAD_INTELLIGENCE_ENGINE",
            details={
                "overall_opportunity_score": 82,
                "opportunity_category": "VERY_HIGH",
                "top_reasons": ["Missing HTTPS", "Contact phone discrepancy"],
                "contactability_score": 60,
                "seo_opportunity_score": 85,
            },
        )
    )

    # Lead 4: MEDIUM with WhatsApp and Social
    db_session.add(
        EvidenceRecord(
            workspace_id=workspace.id,
            lead_id=lead4.id,
            field_name="contacts",
            status="ACCEPT",
            confidence_score=90,
            source="WEBSITE_ENRICHMENT",
            details={"whatsapp_links": ["https://wa.me/15557778888"]},
        )
    )
    db_session.add(
        EvidenceRecord(
            workspace_id=workspace.id,
            lead_id=lead4.id,
            field_name="social_profiles",
            status="ACCEPT",
            confidence_score=90,
            source="WEBSITE_ENRICHMENT",
            details={"profiles": {"instagram": "https://instagram.com/elitedental"}},
        )
    )
    db_session.add(
        EvidenceRecord(
            workspace_id=workspace.id,
            lead_id=lead4.id,
            field_name="lead_intelligence",
            status="MEDIUM",
            confidence_score=80,
            source="LEAD_INTELLIGENCE_ENGINE",
            details={
                "overall_opportunity_score": 55,
                "opportunity_category": "MEDIUM",
                "top_reasons": ["WhatsApp channel active", "Social presence available"],
                "contactability_score": 75,
                "digital_presence_gap_score": 60,
            },
        )
    )

    # Lead 5: MINIMAL
    db_session.add(
        EvidenceRecord(
            workspace_id=workspace.id,
            lead_id=lead5.id,
            field_name="lead_intelligence",
            status="MINIMAL",
            confidence_score=95,
            source="LEAD_INTELLIGENCE_ENGINE",
            details={
                "overall_opportunity_score": 15,
                "opportunity_category": "MINIMAL",
                "top_reasons": ["Complete digital presence"],
                "contactability_score": 95,
            },
        )
    )

    db_session.commit()
    return {"workspace": workspace, "leads": [lead1, lead2, lead3, lead4, lead5]}


def test_lead_operations_filtering(db_session: Session, test_setup: dict):
    """Test filtering across Opportunity categories, Website presence, and Channels."""
    workspace = test_setup["workspace"]

    app.dependency_overrides[current_workspace_id] = lambda: workspace.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    # 1. Filter by Opportunity VERY_HIGH
    res = client.get("/api/operations/leads?opportunity_category=VERY_HIGH")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    assert {l["business_name"] for l in data["results"]} == {"Apex Dental Care", "Downtown Orthodontics"}

    # 2. Filter by No Website
    res_no_web = client.get("/api/operations/leads?website_status=no_website")
    assert res_no_web.status_code == 200
    assert res_no_web.json()["total"] == 2

    # 3. Filter by Has Website
    res_has_web = client.get("/api/operations/leads?website_status=has_website")
    assert res_has_web.status_code == 200
    assert res_has_web.json()["total"] == 3

    # 4. Filter by Verified Website
    res_ver = client.get("/api/operations/leads?website_status=verified_website")
    assert res_ver.status_code == 200
    assert res_ver.json()["total"] == 1
    assert res_ver.json()["results"][0]["business_name"] == "Bright Smile Clinic"

    # 5. Filter by WhatsApp
    res_wh = client.get("/api/operations/leads?has_whatsapp=true")
    assert res_wh.status_code == 200
    assert res_wh.json()["total"] == 1
    assert res_wh.json()["results"][0]["business_name"] == "Elite Dental Spa"

    # 6. Filter by Social
    res_soc = client.get("/api/operations/leads?has_social=true")
    assert res_soc.status_code == 200
    assert res_soc.json()["total"] == 1
    assert res_soc.json()["results"][0]["business_name"] == "Elite Dental Spa"


def test_lead_operations_sorting_and_search(db_session: Session, test_setup: dict):
    """Test deterministic sorting and multi-field search."""
    workspace = test_setup["workspace"]

    app.dependency_overrides[current_workspace_id] = lambda: workspace.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    # 1. Sort by Opportunity Score DESC (Default)
    res_desc = client.get("/api/operations/leads?sort_by=opportunity_score_desc")
    assert res_desc.status_code == 200
    scores = [l["opportunity_score"] for l in res_desc.json()["results"]]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] == 88  # Apex Dental Care

    # 2. Sort by Genuineness Score DESC
    res_gen = client.get("/api/operations/leads?sort_by=genuineness_score_desc")
    assert res_gen.status_code == 200
    gen_scores = [l["genuineness_score"] for l in res_gen.json()["results"]]
    assert gen_scores == sorted(gen_scores, reverse=True)

    # 3. Search by Business Name
    res_sname = client.get("/api/operations/leads?search=Downtown")
    assert res_sname.status_code == 200
    assert res_sname.json()["total"] == 1
    assert res_sname.json()["results"][0]["business_name"] == "Downtown Orthodontics"

    # 4. Search by Phone Number
    res_sphone = client.get("/api/operations/leads?search=111-2222")
    assert res_sphone.status_code == 200
    assert res_sphone.json()["total"] == 1
    assert res_sphone.json()["results"][0]["business_name"] == "Apex Dental Care"

    # 5. Search by Domain / Website
    res_sdom = client.get("/api/operations/leads?search=brightsmile")
    assert res_sdom.status_code == 200
    assert res_sdom.json()["total"] == 1
    assert res_sdom.json()["results"][0]["business_name"] == "Bright Smile Clinic"


def test_lead_detail_intelligence_and_conflicts(db_session: Session, test_setup: dict):
    """Test lead detail retrieval, complete intelligence view, and conflict preservation."""
    workspace = test_setup["workspace"]
    lead3 = test_setup["leads"][2]  # Downtown Orthodontics (has conflict)

    app.dependency_overrides[current_workspace_id] = lambda: workspace.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    res = client.get(f"/api/operations/leads/{lead3.id}")
    assert res.status_code == 200
    data = res.json()

    assert data["business_name"] == "Downtown Orthodontics"
    assert data["opportunity_score"] == 82
    assert data["opportunity_category"] == "VERY_HIGH"
    assert data["has_conflict"] is True
    assert data["top_reasons"] == ["Missing HTTPS", "Contact phone discrepancy"]
    
    # Verify conflict details separately visible
    assert "phone" in data["conflicts"]
    assert data["conflicts"]["phone"]["osm_value"] == "+1-555-555-6666"
    assert data["conflicts"]["phone"]["website_value"] == "+1-555-000-1111"

    # Verify evidence records are returned
    assert len(data["evidence_records"]) >= 2
    assert any(ev["field_name"] == "conflicts" for ev in data["evidence_records"])


def test_lead_workflow_status_transitions(db_session: Session, test_setup: dict):
    """Verify single and bulk workflow transitions without mutating ground truth."""
    workspace = test_setup["workspace"]
    lead1 = test_setup["leads"][0]
    lead2 = test_setup["leads"][1]

    app.dependency_overrides[current_workspace_id] = lambda: workspace.id
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    # 1. Transition NEW -> REVIEWED
    res1 = client.patch(
        f"/api/operations/leads/{lead1.id}/workflow",
        json={"workflow_status": "REVIEWED"},
    )
    assert res1.status_code == 200
    assert res1.json()["workflow_status"] == "REVIEWED"

    # 2. Transition REVIEWED -> CONTACTED -> QUALIFIED
    res2 = client.patch(
        f"/api/operations/leads/{lead1.id}/workflow",
        json={"workflow_status": "CONTACTED"},
    )
    assert res2.status_code == 200
    assert res2.json()["workflow_status"] == "CONTACTED"

    res3 = client.patch(
        f"/api/operations/leads/{lead1.id}/workflow",
        json={"workflow_status": "QUALIFIED"},
    )
    assert res3.status_code == 200
    assert res3.json()["workflow_status"] == "QUALIFIED"

    # 3. Ground Truth Data Remains Untouched
    db_session.expire_all()
    reloaded_lead = db_session.get(Lead, lead1.id)
    assert reloaded_lead.workflow_status == "QUALIFIED"
    assert reloaded_lead.business_name == "Apex Dental Care"
    assert reloaded_lead.phone == "+1-555-111-2222"
    assert reloaded_lead.genuineness_score == 0.90

    # 4. Bulk Workflow Transition
    bulk_res = client.patch(
        "/api/operations/leads/bulk-workflow",
        json={"lead_ids": [str(lead1.id), str(lead2.id)], "workflow_status": "CONVERTED"},
    )
    assert bulk_res.status_code == 200
    assert bulk_res.json()["updated_count"] == 2
    assert bulk_res.json()["workflow_status"] == "CONVERTED"

    db_session.expire_all()
    assert db_session.get(Lead, lead1.id).workflow_status == "CONVERTED"
    assert db_session.get(Lead, lead2.id).workflow_status == "CONVERTED"
