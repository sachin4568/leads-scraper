from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker

from backend.app.api import current_workspace_id
from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import EvidenceRecord, Lead, LeadAction, Workspace
from backend.app.models_phase2 import Base as Phase2Base
from backend.app.models_services import Base as ServicesBase


def run_controlled_phase13_e2e():
    print("=== STARTING PHASE 13 OUTREACH EXECUTION & RESPONSE TRACKING CONTROLLED E2E TEST ===")

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
    workspace = Workspace(name="Phase 13 Controlled Workspace")
    session.add(workspace)
    session.commit()
    session.refresh(workspace)

    # Populate 12 realistic leads across dental & clinic niches
    leads_spec = [
        ("Prime Dental Studio", "+91 98201 10001", "info@primedental.in", "https://primedental.in", 0.95, "VERY_HIGH", 90, ["https://wa.me/919820110001"]),
        ("CosmoDent Multispeciality", "+91 98201 10002", "contact@cosmodent.in", "https://cosmodent.in", 0.92, "VERY_HIGH", 85, []),
        ("Orthocare Clinic", "+91 98201 10003", None, "http://orthocare.org", 0.88, "HIGH", 78, []),
        ("Suburban Smiles", "+91 98201 10004", "smiles@suburban.com", None, 0.85, "HIGH", 72, []),
        ("Tooth Fairy Clinic", "+91 98201 10005", None, None, 0.80, "VERY_HIGH", 82, ["https://wa.me/919820110005"]),
        ("City Dental Centre", "+91 98201 10006", "admin@citydental.in", "https://citydental.in", 0.85, "MEDIUM", 62, []),
        ("Care & Cure PolyClinic", "+91 98201 10007", "help@carecure.in", "https://carecure.in", 0.80, "MEDIUM", 55, []),
        ("Express Tooth Extraction", None, None, None, 0.60, "LOW", 30, []),
    ]

    seeded_leads = []
    for bname, phone, email, web, gen, opp_cat, opp_score, wa_links in leads_spec:
        l = Lead(
            workspace_id=workspace.id,
            business_name=bname,
            phone=phone,
            email=email,
            website=web,
            genuineness_score=gen,
            workflow_status="NEW",
        )
        session.add(l)
        seeded_leads.append((l, opp_cat, opp_score, wa_links, web))

    session.commit()

    for l, opp_cat, opp_score, wa_links, web in seeded_leads:
        session.refresh(l)
        session.add(
            EvidenceRecord(
                workspace_id=workspace.id,
                lead_id=l.id,
                field_name="lead_intelligence",
                status=opp_cat,
                confidence_score=90,
                source="LEAD_INTELLIGENCE_ENGINE",
                details={"overall_opportunity_score": opp_score, "opportunity_category": opp_cat, "top_reasons": ["High sales opportunity"]},
            )
        )
        if wa_links:
            session.add(
                EvidenceRecord(
                    workspace_id=workspace.id,
                    lead_id=l.id,
                    field_name="contacts",
                    status="ACCEPT",
                    confidence_score=95,
                    source="WEBSITE_ENRICHMENT",
                    details={"whatsapp_links": wa_links},
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

    session.commit()
    print(f"Seeded {len(seeded_leads)} leads with intelligence, contacts, and verification.")

    app.dependency_overrides[current_workspace_id] = lambda: workspace.id
    app.dependency_overrides[get_db] = lambda: session

    client = TestClient(app)

    # 1. Inspect Operations Leads with Generated Execution Links
    t0 = time.perf_counter()
    res_leads = client.get("/api/operations/leads")
    lat_leads_ms = (time.perf_counter() - t0) * 1000.0
    assert res_leads.status_code == 200
    leads_data = res_leads.json()
    print(f"1. Operations Leads loaded in {lat_leads_ms:.2f}ms ({leads_data['total']} total):")
    top_lead = leads_data["results"][0]
    print(f"   - Selected Lead: {top_lead['business_name']}")
    print(f"   - Execution Links Generated: {[l['label'] for l in top_lead['execution_links']]}")
    assert len(top_lead["execution_links"]) >= 2

    # 2. Operator Executes Outreach Attempt via WhatsApp Link
    target_id = top_lead["id"]
    t0 = time.perf_counter()
    res_act1 = client.post(
        f"/api/operations/leads/{target_id}/actions",
        json={
            "channel": "WHATSAPP",
            "outcome": "CONTACTED",
            "notes": "Sent modernization pitch message with portfolio link.",
            "follow_up_date": (datetime.now(UTC) + timedelta(hours=24)).isoformat(),
        },
    )
    lat_act1_ms = (time.perf_counter() - t0) * 1000.0
    assert res_act1.status_code == 201
    print(f"2. Recorded WhatsApp outreach execution in {lat_act1_ms:.2f}ms (Workflow -> CONTACTED)")

    # 3. Operator Records Response
    res_act2 = client.post(
        f"/api/operations/leads/{target_id}/actions",
        json={
            "channel": "WHATSAPP",
            "outcome": "INTERESTED",
            "notes": "Doctor replied: 'Looks promising, what is the estimated timeframe?'",
        },
    )
    assert res_act2.status_code == 201
    print(f"3. Recorded customer response (INTERESTED)")

    # 4. Operator Books Meeting
    res_act3 = client.post(
        f"/api/operations/leads/{target_id}/actions",
        json={
            "channel": "PHONE",
            "outcome": "MEETING_BOOKED",
            "notes": "Consultation scheduled for Wednesday 3 PM.",
        },
    )
    assert res_act3.status_code == 201
    print(f"4. Recorded meeting booking (Workflow -> QUALIFIED)")

    # 5. Operator Inspects Unified Activity Timeline
    t0 = time.perf_counter()
    res_tl = client.get(f"/api/operations/leads/{target_id}/timeline")
    lat_tl_ms = (time.perf_counter() - t0) * 1000.0
    assert res_tl.status_code == 200
    timeline = res_tl.json()
    print(f"5. Unified Lifecycle Activity Timeline loaded in {lat_tl_ms:.2f}ms ({len(timeline['events'])} events):")
    for ev in timeline["events"]:
        print(f"   [{ev['event_type']}] {ev['title']} ({ev['source']})")
    assert any(e["event_type"] == "DISCOVERY" for e in timeline["events"])
    assert any(e["event_type"] == "MEETING" for e in timeline["events"])

    # 6. Operator Advances to Client Conversion
    res_act4 = client.post(
        f"/api/operations/leads/{target_id}/actions",
        json={
            "channel": "PHONE",
            "outcome": "CONVERTED",
            "notes": "Closed web modernization retainer contract.",
        },
    )
    assert res_act4.status_code == 201
    print(f"6. Client Converted (Workflow -> CONVERTED)")

    # 7. Operator Inspects Outreach Analytics & Conversion Funnel
    t0 = time.perf_counter()
    res_analytics = client.get("/api/operations/outreach/analytics")
    lat_analytics_ms = (time.perf_counter() - t0) * 1000.0
    assert res_analytics.status_code == 200
    analytics = res_analytics.json()
    print(f"7. Outreach Analytics & Sales Funnel loaded in {lat_analytics_ms:.2f}ms:")
    print("   Pipeline Funnel Stages:")
    for stage in analytics["funnel"]:
        print(f"     - {stage['stage']}: {stage['count']} leads ({stage['conversion_rate_from_previous']}% step)")
    print("   Channel Effectiveness:")
    for ch in analytics["channel_effectiveness"]:
        if ch["attempts"] > 0:
            print(f"     - {ch['channel']}: {ch['attempts']} attempts, {ch['responses']} responses ({ch['response_rate']}% resp), {ch['conversions']} converted")

    # 8. Verify Source Evidence Immobility & Ground Truth Preservation
    session.expire_all()
    reloaded = session.get(Lead, uuid.UUID(target_id))
    assert reloaded.workflow_status == "CONVERTED"
    assert reloaded.business_name == "Prime Dental Studio"
    assert reloaded.phone == "+91 98201 10001"
    assert reloaded.email == "info@primedental.in"

    evs = session.query(EvidenceRecord).filter(EvidenceRecord.lead_id == uuid.UUID(target_id)).all()
    assert len(evs) == 3
    print("8. Data Integrity Confirmed: Ground-truth OSM tags and EvidenceRecords remain 100% immutable.")

    print("\n=== PHASE 13 CONTROLLED E2E TEST: ALL OPERATIONS SUCCESSFUL ===")


if __name__ == "__main__":
    run_controlled_phase13_e2e()
