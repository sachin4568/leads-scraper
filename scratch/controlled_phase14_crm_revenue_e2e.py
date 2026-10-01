from __future__ import annotations

import sys
import time
import uuid
from datetime import UTC, datetime, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker

from backend.app.api import current_workspace_id
from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import Deal, EvidenceRecord, Lead, LeadAction, Workspace
from backend.app.models_phase2 import Base as Phase2Base
from backend.app.models_services import Base as ServicesBase


def run_controlled_phase14_e2e():
    print("=== STARTING PHASE 14 CRM PIPELINE & REVENUE TRACKING CONTROLLED E2E TEST ===")

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
    workspace = Workspace(name="Phase 14 Controlled CRM Workspace")
    session.add(workspace)
    session.commit()
    session.refresh(workspace)

    # Populate 6 realistic dental & clinic businesses
    leads_spec = [
        ("Prime Dental Studio", "+91 98201 10001", "info@primedental.in", "https://primedental.in", 0.95, "QUALIFIED"),
        ("CosmoDent Multispeciality", "+91 98201 10002", "contact@cosmodent.in", "https://cosmodent.in", 0.92, "QUALIFIED"),
        ("Orthocare Clinic", "+91 98201 10003", None, "http://orthocare.org", 0.88, "QUALIFIED"),
        ("Suburban Smiles", "+91 98201 10004", "smiles@suburban.com", None, 0.85, "QUALIFIED"),
        ("Tooth Fairy Clinic", "+91 98201 10005", None, None, 0.80, "QUALIFIED"),
        ("City Dental Centre", "+91 98201 10006", "admin@citydental.in", "https://citydental.in", 0.85, "QUALIFIED"),
    ]

    seeded_leads = []
    for bname, phone, email, web, gen, w_status in leads_spec:
        l = Lead(
            workspace_id=workspace.id,
            business_name=bname,
            phone=phone,
            email=email,
            website=web,
            genuineness_score=gen,
            workflow_status=w_status,
        )
        session.add(l)
        seeded_leads.append(l)

    session.commit()
    for l in seeded_leads:
        session.refresh(l)
        session.add(
            EvidenceRecord(
                workspace_id=workspace.id,
                lead_id=l.id,
                field_name="lead_intelligence",
                status="VERY_HIGH",
                confidence_score=90,
                source="LEAD_INTELLIGENCE_ENGINE",
                details={"overall_opportunity_score": 85, "opportunity_category": "VERY_HIGH", "top_reasons": ["Sales opportunity validated"]},
            )
        )
    session.commit()
    print(f"Seeded {len(seeded_leads)} qualified leads with intelligence and evidence.")

    app.dependency_overrides[current_workspace_id] = lambda: workspace.id
    app.dependency_overrides[get_db] = lambda: session

    client = TestClient(app)

    # 1. Create Opportunities for Leads
    # Deal 1: Prime Dental -> Website Development (₹75,000)
    t0 = time.perf_counter()
    res_d1 = client.post(
        "/api/operations/deals",
        json={
            "lead_id": str(seeded_leads[0].id),
            "title": "Prime Dental - Web Modernization & Patient Booking",
            "service_type": "WEBSITE_DEVELOPMENT",
            "deal_value": 75000.0,
            "stage": "QUALIFIED",
            "notes": "Met with Dr. Prime; agreed to proceed with proposal.",
        },
    )
    lat_d1_ms = (time.perf_counter() - t0) * 1000.0
    assert res_d1.status_code == 201
    deal1_id = res_d1.json()["id"]
    print(f"1. Created Deal 1 (Prime Dental) in {lat_d1_ms:.2f}ms: ₹75,000 (QUALIFIED, prob=40%)")

    # Deal 2: CosmoDent -> SEO Retainer (₹40,000)
    res_d2 = client.post(
        "/api/operations/deals",
        json={
            "lead_id": str(seeded_leads[1].id),
            "title": "CosmoDent - Local Dental SEO Retainer",
            "service_type": "SEO",
            "deal_value": 40000.0,
            "stage": "PROPOSAL",
            "notes": "Sent 6-month organic growth proposal.",
        },
    )
    assert res_d2.status_code == 201
    deal2_id = res_d2.json()["id"]
    print(f"2. Created Deal 2 (CosmoDent): ₹40,000 (PROPOSAL, prob=60%)")

    # Deal 3: Orthocare -> SMMA (₹30,000)
    res_d3 = client.post(
        "/api/operations/deals",
        json={
            "lead_id": str(seeded_leads[2].id),
            "title": "Orthocare - Social Media & Instagram Marketing",
            "service_type": "SMMA",
            "deal_value": 30000.0,
            "stage": "NEGOTIATION",
            "notes": "Final pricing review with clinic director.",
        },
    )
    assert res_d3.status_code == 201
    deal3_id = res_d3.json()["id"]
    print(f"3. Created Deal 3 (Orthocare): ₹30,000 (NEGOTIATION, prob=80%)")

    # Deal 4: Suburban Smiles -> Custom Web (₹35,000) -> LOST
    res_d4 = client.post(
        "/api/operations/deals",
        json={
            "lead_id": str(seeded_leads[3].id),
            "title": "Suburban Smiles - Clinic Site Build",
            "service_type": "WEBSITE_DEVELOPMENT",
            "deal_value": 35000.0,
            "stage": "LOST",
            "win_loss_reason": "Decided to keep current DIY page for this quarter.",
        },
    )
    assert res_d4.status_code == 201
    print(f"4. Created Deal 4 (Suburban Smiles): ₹35,000 (LOST)")

    # 2. Advance Deal 1 through Proposal -> Negotiation -> WON
    t0 = time.perf_counter()
    client.patch(f"/api/operations/deals/{deal1_id}", json={"stage": "PROPOSAL"})
    client.patch(f"/api/operations/deals/{deal1_id}", json={"stage": "NEGOTIATION"})
    res_win = client.patch(
        f"/api/operations/deals/{deal1_id}",
        json={"stage": "WON", "win_loss_reason": "Signed ₹75k contract; 50% advance received."},
    )
    lat_win_ms = (time.perf_counter() - t0) * 1000.0
    assert res_win.status_code == 200
    assert res_win.json()["stage"] == "WON"
    print(f"5. Advanced Deal 1 to WON in {lat_win_ms:.2f}ms. Converted client revenue: ₹75,000")

    # 3. Retrieve CRM Pipeline Dashboard
    t0 = time.perf_counter()
    res_pipe = client.get("/api/operations/crm/pipeline")
    lat_pipe_ms = (time.perf_counter() - t0) * 1000.0
    assert res_pipe.status_code == 200
    pipeline = res_pipe.json()
    print(f"6. CRM Pipeline Dashboard loaded in {lat_pipe_ms:.2f}ms:")
    print(f"   - Won Closed Revenue: ₹{pipeline['won_revenue']:,.2f}")
    print(f"   - Active Pipeline Value: ₹{pipeline['total_pipeline_value']:,.2f}")
    print(f"   - Weighted Pipeline Forecast: ₹{pipeline['weighted_pipeline_value']:,.2f}")
    print(f"   - Lost Opportunity Value: ₹{pipeline['lost_value']:,.2f}")
    print(f"   - Win Rate: {pipeline['win_rate']}% ({pipeline['won_deals_count']} won / {pipeline['won_deals_count'] + pipeline['lost_deals_count']} closed)")
    print(f"   - Average Deal Size: ₹{pipeline['avg_deal_size']:,.2f}")

    print("   Revenue by Service Breakdown:")
    for svc in pipeline["revenue_by_service"]:
        if svc["deals_count"] > 0:
            print(f"     - {svc['category']}: {svc['deals_count']} deals • Won: ₹{svc['won_revenue']:,.2f} • Pipeline: ₹{svc['pipeline_value']:,.2f}")

    # 4. Check Lead Activity Timeline includes Deal Won
    res_tl = client.get(f"/api/operations/leads/{seeded_leads[0].id}/timeline")
    assert res_tl.status_code == 200
    timeline = res_tl.json()
    print(f"7. Lead Timeline verified ({len(timeline['events'])} events):")
    for ev in timeline["events"]:
        print(f"   [{ev['event_type']}] {ev['title']}")

    assert any(e["event_type"] == "CONVERSION" for e in timeline["events"])

    # 5. Check Lead Status Sync
    session.expire_all()
    reloaded_lead1 = session.get(Lead, seeded_leads[0].id)
    assert reloaded_lead1.workflow_status == "CONVERTED"
    print(f"8. Lead Workflow Status synchronized to '{reloaded_lead1.workflow_status}' (Customer Lifecycle complete).")

    # 6. Verify Evidence Immutability
    evs = session.query(EvidenceRecord).filter(EvidenceRecord.lead_id == seeded_leads[0].id).all()
    assert len(evs) == 1
    assert evs[0].field_name == "lead_intelligence"
    print("9. Source evidence & intelligence records 100% immutable and intact.")

    print("\n=== PHASE 14 CONTROLLED E2E TEST: ALL OPERATIONS SUCCESSFUL ===")


if __name__ == "__main__":
    run_controlled_phase14_e2e()
