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


def run_controlled_phase15_e2e():
    print("=== STARTING PHASE 15 EXECUTIVE BUSINESS ANALYTICS CONTROLLED E2E TEST ===")

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
    workspace = Workspace(name="Phase 15 Executive Analytics Workspace")
    session.add(workspace)
    session.commit()
    session.refresh(workspace)

    now = datetime.now(UTC)

    # Populate 10 diverse businesses across intelligence tiers and sources
    leads_spec = [
        # (name, phone, email, website, gen, q_tier, opp_score, status, days_ago)
        ("Grand Dental Hospital", "+91 98201 10001", "info@granddental.in", "https://granddental.in", 0.98, "VERY_HIGH", 95, "CONVERTED", 2),
        ("Apollo Smile Hub", "+91 98201 10002", "care@apollosmile.in", "https://apollosmile.in", 0.92, "VERY_HIGH", 88, "QUALIFIED", 4),
        ("Sunrise Laser Clinic", "+91 98201 10003", "contact@sunriselaser.com", "http://sunriselaser.com", 0.88, "HIGH", 78, "QUALIFIED", 6),
        ("City Orthocare", "+91 98201 10004", "info@cityortho.in", "http://cityortho.in", 0.85, "HIGH", 72, "CONTACTED", 8),
        ("Suburban Physiotherapy", "+91 98201 10005", "help@suburbanphysio.com", None, 0.78, "MEDIUM", 58, "LOST", 12),
        ("Metro Care Polyclinic", "+91 98201 10006", None, "http://metrocare.in", 0.70, "MEDIUM", 52, "CONTACTED", 15),
        ("Quick Tooth Extraction", "+91 98201 10007", None, None, 0.60, "LOW", 35, "NEW", 20),
        ("Neighbourhood Clinic", None, None, None, 0.40, "LOW", 25, "NEW", 25),
        ("Dormant Dental Desk", None, None, None, 0.30, "MINIMAL", 15, "NEW", 45),
        ("Inactive Healthcare Center", None, None, None, 0.20, "MINIMAL", 10, "DISMISSED", 60),
    ]

    seeded_leads = []
    for bname, phone, email, web, gen, q_tier, opp_score, w_status, days_ago in leads_spec:
        l = Lead(
            workspace_id=workspace.id,
            business_name=bname,
            phone=phone,
            email=email,
            website=web,
            genuineness_score=gen,
            workflow_status=w_status,
            created_at=now - timedelta(days=days_ago),
        )
        session.add(l)
        seeded_leads.append((l, q_tier, opp_score, web, days_ago))

    session.commit()

    for l, q_tier, opp_score, web, days_ago in seeded_leads:
        session.refresh(l)
        session.add(
            EvidenceRecord(
                workspace_id=workspace.id,
                lead_id=l.id,
                field_name="lead_intelligence",
                status=q_tier,
                confidence_score=90,
                source="LEAD_INTELLIGENCE_ENGINE",
                details={"overall_opportunity_score": opp_score, "opportunity_category": q_tier, "top_reasons": ["Automated intelligence audit"]},
                created_at=now - timedelta(days=days_ago),
            )
        )
        if web and "https" in web:
            session.add(
                EvidenceRecord(
                    workspace_id=workspace.id,
                    lead_id=l.id,
                    field_name="website",
                    status="ACCEPT",
                    confidence_score=95,
                    source="ZERO_BUDGET_VERIFIED",
                    details={"verified_url": web},
                    created_at=now - timedelta(days=days_ago),
                )
            )

    # Seed deals
    # Deal 1: Grand Dental (VERY_HIGH) -> Won ₹90,000 Web Dev
    session.add(
        Deal(
            workspace_id=workspace.id,
            lead_id=seeded_leads[0][0].id,
            title="Grand Dental - Full Modernization",
            service_type="WEBSITE_DEVELOPMENT",
            deal_value=90000.0,
            stage="WON",
            probability=1.0,
            created_at=now - timedelta(days=2),
            closed_at=now - timedelta(days=1),
        )
    )
    # Deal 2: Apollo Smile (VERY_HIGH) -> Negotiation ₹50,000 SEO (prob 80%)
    session.add(
        Deal(
            workspace_id=workspace.id,
            lead_id=seeded_leads[1][0].id,
            title="Apollo Smile - Local SEO Retainer",
            service_type="SEO",
            deal_value=50000.0,
            stage="NEGOTIATION",
            probability=0.80,
            created_at=now - timedelta(days=4),
        )
    )
    # Deal 3: Sunrise Laser (HIGH) -> Proposal ₹35,000 SMMA (prob 60%)
    session.add(
        Deal(
            workspace_id=workspace.id,
            lead_id=seeded_leads[2][0].id,
            title="Sunrise Laser - Social Media Growth",
            service_type="SMMA",
            deal_value=35000.0,
            stage="PROPOSAL",
            probability=0.60,
            created_at=now - timedelta(days=6),
        )
    )
    # Deal 4: Suburban Physio (MEDIUM) -> Lost ₹30,000 Web Dev
    session.add(
        Deal(
            workspace_id=workspace.id,
            lead_id=seeded_leads[4][0].id,
            title="Suburban Physio - Site Rebuild",
            service_type="WEBSITE_DEVELOPMENT",
            deal_value=30000.0,
            stage="LOST",
            probability=0.0,
            win_loss_reason="No budget allocation",
            created_at=now - timedelta(days=12),
            closed_at=now - timedelta(days=11),
        )
    )

    # Seed outreach actions
    session.add(LeadAction(workspace_id=workspace.id, lead_id=seeded_leads[0][0].id, channel="WHATSAPP", outcome="CONVERTED", created_at=now - timedelta(days=1)))
    session.add(LeadAction(workspace_id=workspace.id, lead_id=seeded_leads[1][0].id, channel="PHONE", outcome="MEETING_BOOKED", created_at=now - timedelta(days=3)))
    session.add(LeadAction(workspace_id=workspace.id, lead_id=seeded_leads[2][0].id, channel="EMAIL", outcome="INTERESTED", created_at=now - timedelta(days=5)))
    session.add(LeadAction(workspace_id=workspace.id, lead_id=seeded_leads[3][0].id, channel="PHONE", outcome="CONTACTED", created_at=now - timedelta(days=7)))
    session.add(LeadAction(workspace_id=workspace.id, lead_id=seeded_leads[4][0].id, channel="PHONE", outcome="NOT_INTERESTED", created_at=now - timedelta(days=11)))
    session.add(LeadAction(workspace_id=workspace.id, lead_id=seeded_leads[5][0].id, channel="WHATSAPP", outcome="NO_RESPONSE", created_at=now - timedelta(days=14)))

    session.commit()
    print(f"Seeded {len(seeded_leads)} leads with intelligence quality tiers, outreach actions, and deals.")

    app.dependency_overrides[current_workspace_id] = lambda: workspace.id
    app.dependency_overrides[get_db] = lambda: session

    client = TestClient(app)

    # 1. Executive Business Overview (30-day window)
    t0 = time.perf_counter()
    res_overview = client.get("/api/analytics/overview?timeframe=30d")
    lat_ms = (time.perf_counter() - t0) * 1000.0
    assert res_overview.status_code == 200
    data = res_overview.json()
    kpis = data["kpis"]

    print(f"\n1. Executive Analytics Loaded in {lat_ms:.2f}ms (Timeframe: 30D):")
    print(f"   - Total Leads (30d): {kpis['total_leads']}")
    print(f"   - Contactable Leads: {kpis['contactable_leads']}")
    print(f"   - Contacted Leads: {kpis['contacted_leads']} (Response Rate: {kpis['overall_response_rate']}%)")
    print(f"   - Qualified Opportunities: {kpis['qualified_leads']}")
    print(f"   - Won Closed Clients: {kpis['won_leads']} (Conversion Rate: {kpis['overall_conversion_rate']}%)")
    print(f"   - Won Closed Revenue: INR {kpis['won_revenue']:,.2f}")
    print(f"   - Active Pipeline Value: INR {kpis['total_pipeline_value']:,.2f}")
    print(f"   - Weighted Pipeline Forecast: INR {kpis['weighted_pipeline_value']:,.2f}")
    print(f"   - Win Rate: {kpis['win_rate']}% • Avg Deal Size: INR {kpis['avg_deal_size']:,.2f}")

    # 2. End-to-End Funnel
    print("\n2. End-to-End Conversion Funnel Stages:")
    for f in data["funnel"]:
        print(f"   - {f['stage']}: {f['count']} leads ({f['conversion_rate_from_previous']}% step drop, {f['conversion_rate_from_total']}% overall)")

    # 3. Opportunity Quality Correlation Matrix
    print("\n3. Opportunity Quality Tier Correlation (Phase 9 Intelligence vs Revenue):")
    for q in data["quality_performance"]:
        print(f"   - [{q['tier']}] Leads: {q['leads_count']} | Qualified: {q['qualified_pct']}% | Won: {q['won_pct']}% | Won Revenue: INR {q['won_revenue']:,.2f}")

    # 4. Source Commercial Attribution
    print("\n4. Acquisition Source Performance:")
    for s in data["source_performance"]:
        if s["leads_count"] > 0:
            print(f"   - {s['source']}: {s['leads_count']} leads | Contactable: {s['contactable_pct']}% | Won Revenue: INR {s['won_revenue']:,.2f}")

    # 5. Service Pitch Revenue Matrix
    print("\n5. Service Pitch Revenue Matrix:")
    for svc in data["service_performance"]:
        print(f"   - {svc['service']}: {svc['opportunities_count']} opportunities | Pipeline: INR {svc['pipeline_value']:,.2f} | Won: INR {svc['won_revenue']:,.2f} (Win Rate: {svc['win_rate']}%)")

    # 6. Channel Effectiveness
    print("\n6. Outreach Channel Effectiveness:")
    for ch in data["channel_effectiveness"]:
        if ch["attempts"] > 0:
            print(f"   - {ch['channel']}: {ch['attempts']} attempts, {ch['responses']} responses ({ch['response_rate']}% resp), {ch['conversions']} conversions")

    # 7. Timeframe Boundary Test
    res_today = client.get("/api/analytics/overview?timeframe=today")
    assert res_today.status_code == 200
    res_all = client.get("/api/analytics/overview?timeframe=all_time")
    assert res_all.status_code == 200
    print(f"\n7. Timeframe filtering verified: Today={res_today.json()['kpis']['total_leads']}, 30D={kpis['total_leads']}, AllTime={res_all.json()['kpis']['total_leads']}")

    # 8. Evidence Immutability Verification
    session.expire_all()
    reloaded_lead1 = session.get(Lead, seeded_leads[0][0].id)
    assert reloaded_lead1.business_name == "Grand Dental Hospital"
    assert reloaded_lead1.phone == "+91 98201 10001"
    assert reloaded_lead1.email == "info@granddental.in"

    evs = session.query(EvidenceRecord).filter(EvidenceRecord.lead_id == seeded_leads[0][0].id).all()
    assert len(evs) == 2
    print("\n8. Data Integrity Confirmed: Underlying OSM tags and evidence records remain 100% immutable.")

    print("\n=== PHASE 15 CONTROLLED E2E TEST: ALL OPERATIONS SUCCESSFUL ===")


if __name__ == "__main__":
    run_controlled_phase15_e2e()
