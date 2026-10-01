from __future__ import annotations

import time
import uuid

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


def run_controlled_phase11_e2e():
    print("=== STARTING PHASE 11 LEAD OPERATIONS CONTROLLED E2E TEST ===")

    # In-memory DB setup
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
    workspace = Workspace(name="Goregaon Operations Workspace")
    session.add(workspace)
    session.commit()
    session.refresh(workspace)

    # Populate 15 diverse leads
    categories = ["VERY_HIGH", "HIGH", "HIGH", "MEDIUM", "MEDIUM", "MEDIUM", "LOW", "MINIMAL"]
    leads_data = [
        ("Dr. Sharma Dental Clinic", "+91 98201 11111", None, None, 0.92, "VERY_HIGH", 88, ["No website found", "Verified phone available"]),
        ("Apex Multispeciality Dental", "+91 98201 22222", "apex@dental.com", "https://apexdental.in", 0.95, "VERY_HIGH", 84, ["Missing HTTPS on subdomains", "SEO meta description missing"]),
        ("Goregaon Smiles & Braces", "+91 98201 33333", None, "http://goregaonsmiles.com", 0.88, "HIGH", 76, ["Unreachable website (HTTP 500)", "Direct WhatsApp active"]),
        ("Perfect 32 Dental Care", "+91 98201 44444", "info@p32.com", None, 0.85, "HIGH", 72, ["No website found", "Email verified"]),
        ("Dr. Mehta Orthodontics", "+91 98201 55555", None, "https://mehtaortho.com", 0.80, "MEDIUM", 58, ["Outdated mobile viewport", "No Instagram link"]),
        ("City Dental Lounge", "+91 98201 66666", "contact@citydental.in", "https://citydental.in", 0.78, "MEDIUM", 52, ["Low social presence", "Slow page response (3200ms)"]),
        ("DentCare Express", None, "help@dentcare.com", None, 0.75, "LOW", 38, ["Missing direct phone", "Generic email"]),
        ("Care & Cure Dental Hospital", "+91 98201 77777", "admin@carecure.org", "https://carecure.org", 0.99, "MINIMAL", 18, ["Complete modern digital presence"]),
        ("Suburban Dental Studio", "+91 98201 88888", None, None, 0.91, "VERY_HIGH", 86, ["No website found", "Direct phone available"]),
        ("Zenith Smile Studio", "+91 98201 99999", "zenith@gmail.com", "https://zenithsmile.com", 0.89, "HIGH", 70, ["Missing Schema.org LocalBusiness JSON-LD"]),
        ("Dr. Roy Periodontist", "+91 98201 00000", None, None, 0.82, "HIGH", 68, ["No website found"]),
        ("Sai Krupa Dental Care", "+91 98202 11111", None, "http://saikrupadental.com", 0.76, "MEDIUM", 50, ["HTTP unencrypted"]),
        ("Maxillofacial Surgery Center", "+91 98202 22222", "info@maxillo.com", "https://maxillosurgery.in", 0.90, "LOW", 32, ["Strong SEO metadata"]),
        ("Om Dental Clinic", "+91 98202 33333", None, None, 0.80, "MEDIUM", 54, ["No website found"]),
        ("Dr. Kulkarni Dental Implants", "+91 98202 44444", "drkulkarni@implants.in", "https://kulkarniimplants.com", 0.96, "MINIMAL", 12, ["Fully optimized web presence"]),
    ]

    persisted_leads = []
    for bname, phone, email, web, gen_score, opp_cat, opp_score, reasons in leads_data:
        l = Lead(
            workspace_id=workspace.id,
            business_name=bname,
            phone=phone,
            email=email,
            website=web,
            genuineness_score=gen_score,
            workflow_status="NEW",
        )
        session.add(l)
        persisted_leads.append((l, opp_cat, opp_score, reasons, web))

    session.commit()

    for l, opp_cat, opp_score, reasons, web in persisted_leads:
        session.refresh(l)
        # Add intelligence evidence
        session.add(
            EvidenceRecord(
                workspace_id=workspace.id,
                lead_id=l.id,
                field_name="lead_intelligence",
                status=opp_cat,
                confidence_score=90,
                source="LEAD_INTELLIGENCE_ENGINE",
                details={
                    "overall_opportunity_score": opp_score,
                    "opportunity_category": opp_cat,
                    "top_reasons": reasons,
                    "contactability_score": 80 if l.phone and l.email else (50 if l.phone else 20),
                    "website_opportunity_score": 100 if not web else (60 if web.startswith("http:") else 20),
                    "seo_opportunity_score": 75 if web else 0,
                    "digital_presence_gap_score": 60,
                },
            )
        )
        if web:
            session.add(
                EvidenceRecord(
                    workspace_id=workspace.id,
                    lead_id=l.id,
                    field_name="website",
                    status="ACCEPT",
                    confidence_score=95,
                    source="ZERO_BUDGET_VERIFIED",
                    details={"verified_url": web},
                )
            )
            session.add(
                EvidenceRecord(
                    workspace_id=workspace.id,
                    lead_id=l.id,
                    field_name="seo",
                    status="ACCEPT",
                    confidence_score=90,
                    source="WEBSITE_ENRICHMENT",
                    details={"seo_score": 65 if web.startswith("https") else 40, "title": f"{l.business_name} Official"},
                )
            )

    # Add a contact conflict to lead 2
    session.add(
        EvidenceRecord(
            workspace_id=workspace.id,
            lead_id=persisted_leads[1][0].id,
            field_name="conflicts",
            status="WARNING",
            confidence_score=80,
            source="WEBSITE_ENRICHMENT",
            details={"phone": {"osm_value": "+91 98201 22222", "website_value": "+91 98201 99999"}},
        )
    )

    session.commit()
    print(f"Seeded {len(persisted_leads)} diverse leads with full intelligence and evidence.")

    # Override dependencies
    app.dependency_overrides[current_workspace_id] = lambda: workspace.id
    app.dependency_overrides[get_db] = lambda: session

    client = TestClient(app)

    # 1. Measure Lead List Latency
    t0 = time.perf_counter()
    res_list = client.get("/api/operations/leads?page=1&page_size=20")
    lat_list_ms = (time.perf_counter() - t0) * 1000.0
    assert res_list.status_code == 200
    list_data = res_list.json()
    print(f"1. Default Lead List Loaded: {list_data['total']} leads in {lat_list_ms:.2f}ms")
    assert list_data["total"] == 15

    # 2. Filter by VERY_HIGH Opportunity
    t0 = time.perf_counter()
    res_vh = client.get("/api/operations/leads?opportunity_category=VERY_HIGH")
    lat_filter_ms = (time.perf_counter() - t0) * 1000.0
    assert res_vh.status_code == 200
    vh_data = res_vh.json()
    print(f"2. Filter VERY_HIGH: {vh_data['total']} leads in {lat_filter_ms:.2f}ms")
    assert vh_data["total"] == 3

    # 3. Filter by No Website
    res_no_web = client.get("/api/operations/leads?website_status=no_website")
    assert res_no_web.status_code == 200
    print(f"3. Filter No Website: {res_no_web.json()['total']} leads")
    assert res_no_web.json()["total"] == 6

    # 4. Search by Keyword 'Goregaon'
    res_search = client.get("/api/operations/leads?search=Goregaon")
    assert res_search.status_code == 200
    print(f"4. Search 'Goregaon': {res_search.json()['total']} leads")
    assert res_search.json()["total"] == 1
    assert res_search.json()["results"][0]["business_name"] == "Goregaon Smiles & Braces"

    # 5. Open Lead Detail (Lead with conflict)
    conflict_lead_id = persisted_leads[1][0].id
    t0 = time.perf_counter()
    res_detail = client.get(f"/api/operations/leads/{conflict_lead_id}")
    lat_detail_ms = (time.perf_counter() - t0) * 1000.0
    assert res_detail.status_code == 200
    detail_data = res_detail.json()
    print(f"5. Lead Detail Loaded in {lat_detail_ms:.2f}ms")
    print(f"   - Business: {detail_data['business_name']}")
    print(f"   - Score: {detail_data['opportunity_score']} ({detail_data['opportunity_category']})")
    print(f"   - Top Reasons: {detail_data['top_reasons']}")
    print(f"   - Has Conflict: {detail_data['has_conflict']}")
    print(f"   - Conflict Data: {detail_data['conflicts']}")
    assert detail_data["has_conflict"] is True
    assert "phone" in detail_data["conflicts"]

    # 6. Workflow Transition: NEW -> REVIEWED -> CONTACTED -> QUALIFIED
    target_lead_id = persisted_leads[0][0].id
    transitions = ["REVIEWED", "CONTACTED", "QUALIFIED"]
    for status_val in transitions:
        res_patch = client.patch(
            f"/api/operations/leads/{target_lead_id}/workflow",
            json={"workflow_status": status_val},
        )
        assert res_patch.status_code == 200
        assert res_patch.json()["workflow_status"] == status_val
        print(f"6. Workflow State Transitioned -> {status_val}")

    # 7. Bulk Workflow Update
    bulk_ids = [str(persisted_leads[2][0].id), str(persisted_leads[3][0].id)]
    res_bulk = client.patch(
        "/api/operations/leads/bulk-workflow",
        json={"lead_ids": bulk_ids, "workflow_status": "DISMISSED"},
    )
    assert res_bulk.status_code == 200
    assert res_bulk.json()["updated_count"] == 2
    print(f"7. Bulk Updated 2 leads to DISMISSED")

    # 8. Data Integrity Verification
    session.expire_all()
    reloaded_lead = session.get(Lead, target_lead_id)
    assert reloaded_lead.workflow_status == "QUALIFIED"
    assert reloaded_lead.phone == "+91 98201 11111"
    assert reloaded_lead.business_name == "Dr. Sharma Dental Clinic"
    print("8. Data Integrity Verified: Zero source data mutation during workflow operations.")

    print("\n=== PHASE 11 CONTROLLED E2E TEST: ALL CHECKS PASSED ===")


if __name__ == "__main__":
    run_controlled_phase11_e2e()
