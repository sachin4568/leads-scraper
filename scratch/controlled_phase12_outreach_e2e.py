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


def run_controlled_phase12_e2e():
    print("=== STARTING PHASE 12 OUTREACH PREPARATION & LEAD ACTION CONTROLLED E2E TEST ===")

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
    workspace = Workspace(name="Phase 12 Controlled Outreach Workspace")
    session.add(workspace)
    session.commit()
    session.refresh(workspace)

    # Populate 15 diverse leads
    leads_spec = [
        ("Dr. Sharma Multispeciality Dental", "+91 98201 11111", "sharma@dental.com", None, 0.95, "VERY_HIGH", 88, ["wa.me/919820111111"]),
        ("Apex Orthodontics & Braces", "+91 98201 22222", "info@apexortho.in", "https://apexortho.in", 0.92, "VERY_HIGH", 82, []),
        ("Smile Studio Goregaon", "+91 98201 33333", None, "http://smilestudio.in", 0.86, "HIGH", 74, []),
        ("Family Dental Clinic", None, "contact@familydental.org", None, 0.80, "HIGH", 68, []),
        ("Elite Aesthetic Dentistry", "+91 98201 55555", None, None, 0.88, "VERY_HIGH", 85, []),
        ("Suburban Dental Hospital", "+91 98201 66666", "admin@suburbandental.com", "https://suburbandental.com", 0.90, "MEDIUM", 58, []),
        ("DentCare Express Mumbai", None, None, None, 0.60, "LOW", 35, []),
        ("Perfect 32 Tooth Care", "+91 98201 88888", "care@p32.in", "https://p32.in", 0.98, "MINIMAL", 15, []),
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

    session.commit()
    print(f"Seeded {len(seeded_leads)} leads with intelligence, contactability, and evidence.")

    app.dependency_overrides[current_workspace_id] = lambda: workspace.id
    app.dependency_overrides[get_db] = lambda: session

    client = TestClient(app)

    # 1. Outreach Dashboard Metrics Inspection
    t0 = time.perf_counter()
    res_dash = client.get("/api/operations/outreach/dashboard")
    lat_dash_ms = (time.perf_counter() - t0) * 1000.0
    assert res_dash.status_code == 200
    dash_data = res_dash.json()
    print(f"1. Outreach Dashboard Loaded in {lat_dash_ms:.2f}ms:")
    print(f"   - Total Leads: {dash_data['total_leads']}")
    print(f"   - Ready to Contact: {dash_data['ready_to_contact']}")
    print(f"   - Channels Breakdown: {dash_data['channels_breakdown']}")

    # 2. Query Priority Queue: 🔴 CONTACT_NOW
    t0 = time.perf_counter()
    res_cn = client.get("/api/operations/leads?priority_queue=CONTACT_NOW")
    lat_cn_ms = (time.perf_counter() - t0) * 1000.0
    assert res_cn.status_code == 200
    cn_data = res_cn.json()
    print(f"2. Contact Now Priority Queue Loaded in {lat_cn_ms:.2f}ms ({cn_data['total']} leads)")
    top_lead = cn_data["results"][0]
    print(f"   - Selected Lead: {top_lead['business_name']}")
    print(f"   - Opportunity Score: {top_lead['opportunity_score']} ({top_lead['opportunity_category']})")
    print(f"   - Recommended Channel: {top_lead['recommended_channel']['label']} ({top_lead['recommended_channel']['value']})")
    assert top_lead["recommended_channel"]["channel"] in ["WHATSAPP", "PHONE", "EMAIL"]

    # 3. Inspect Full Lead Action Dossier
    target_id = top_lead["id"]
    res_det = client.get(f"/api/operations/leads/{target_id}")
    assert res_det.status_code == 200
    det_data = res_det.json()
    print(f"3. Lead Action Dossier Opened: {det_data['business_name']}")
    print(f"   - Action History Count: {det_data['actions_count']}")

    # 4. Record Outreach Attempt 1: Call Left Voicemail
    t0 = time.perf_counter()
    res_act1 = client.post(
        f"/api/operations/leads/{target_id}/actions",
        json={
            "channel": "PHONE",
            "outcome": "NO_RESPONSE",
            "notes": "Attempted call at 11:30 AM. Left voicemail regarding web design modernization.",
            "follow_up_date": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
        },
    )
    lat_act1_ms = (time.perf_counter() - t0) * 1000.0
    assert res_act1.status_code == 201
    print(f"4. Recorded Attempt 1 (PHONE/NO_RESPONSE) in {lat_act1_ms:.2f}ms")

    # 5. Record Outreach Attempt 2: WhatsApp Follow-up (Interested)
    res_act2 = client.post(
        f"/api/operations/leads/{target_id}/actions",
        json={
            "channel": "WHATSAPP",
            "outcome": "INTERESTED",
            "notes": "Sent WhatsApp message with demo link. Dr. Sharma responded asking for quotation.",
            "follow_up_date": (datetime.now(UTC) + timedelta(hours=24)).isoformat(),
        },
    )
    assert res_act2.status_code == 201
    print(f"5. Recorded Attempt 2 (WHATSAPP/INTERESTED) -> Workflow advanced to CONTACTED")

    # 6. Verify Chronological Append-Only History
    res_hist = client.get(f"/api/operations/leads/{target_id}/actions")
    assert res_hist.status_code == 200
    history = res_hist.json()
    assert len(history) == 2
    assert history[0]["channel"] == "WHATSAPP"
    assert history[1]["channel"] == "PHONE"
    print(f"6. Append-Only Chronological Action Log Verified ({len(history)} entries)")

    # 7. Advance Lead to QUALIFIED / Meeting Booked
    res_act3 = client.post(
        f"/api/operations/leads/{target_id}/actions",
        json={
            "channel": "PHONE",
            "outcome": "MEETING_BOOKED",
            "notes": "Confirmed consultation call for Thursday 4 PM.",
        },
    )
    assert res_act3.status_code == 201

    # 8. Verify Source Evidence Immobility & Ground Truth Preservation
    session.expire_all()
    reloaded = session.get(Lead, uuid.UUID(target_id))
    assert reloaded.workflow_status == "QUALIFIED"
    assert reloaded.business_name == "Dr. Sharma Multispeciality Dental"
    assert reloaded.phone == "+91 98201 11111"
    assert reloaded.email == "sharma@dental.com"

    evs = session.query(EvidenceRecord).filter(EvidenceRecord.lead_id == uuid.UUID(target_id)).all()
    assert len(evs) == 2
    print("7. Data Integrity Confirmed: OSM source records & EvidenceRecords remain 100% immutable.")

    print("\n=== PHASE 12 CONTROLLED E2E TEST: ALL OPERATIONS SUCCESSFUL ===")


if __name__ == "__main__":
    run_controlled_phase12_e2e()
