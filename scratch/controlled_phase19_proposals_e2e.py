from __future__ import annotations

import sys
import time
import uuid
from datetime import UTC, datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker

from backend.app.api import current_workspace_id
from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import Deal, Lead, LeadAction, Proposal, ProposalVersion, Workspace
from backend.app.models_phase2 import Base as Phase2Base
from backend.app.models_services import Base as ServicesBase


def run_controlled_phase19_e2e():
    print("=== STARTING PHASE 19 PROPOSAL, QUOTATION & DEAL CLOSING SYSTEM CONTROLLED E2E TEST ===")

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

    ws = Workspace(name="Acme Agency Workspace")
    session.add(ws)
    session.commit()
    session.refresh(ws)

    app.dependency_overrides[current_workspace_id] = lambda: ws.id
    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)

    # 1. Seed Qualified Lead & CRM Deal
    lead = Lead(
        workspace_id=ws.id,
        business_name="Dr. Sharma Multispeciality Dental",
        phone="+91 98200 88888",
        email="contact@sharmadental.in",
        genuineness_score=0.96,
        workflow_status="QUALIFIED",
    )
    session.add(lead)
    session.commit()
    session.refresh(lead)

    deal = Deal(
        workspace_id=ws.id,
        lead_id=lead.id,
        title="Full Stack Dental Modernization",
        service_type="WEBSITE_DEVELOPMENT",
        deal_value=75000.0,
        stage="QUALIFIED",
        probability=0.6,
    )
    session.add(deal)
    session.commit()
    session.refresh(deal)
    print(f"1. Qualified CRM Deal Initialized: '{deal.title}' | Estimated Value: ₹{deal.deal_value:,.2f} | Stage: {deal.stage}")

    # 2. Create Proposal (v1): Base 70k + Addons 10k - Discount 5k = Quoted 75k
    res_p1 = client.post(
        f"/api/operations/deals/{deal.id}/proposals",
        json={
            "title": "Dental Modernization Package & WhatsApp Integration",
            "service_type": "WEBSITE_DEVELOPMENT",
            "base_price": 70000.0,
            "addons_total": 10000.0,
            "discount_amount": 5000.0,
            "timeline": "4-week delivery",
            "deliverables": ["Responsive Website", "Appointment Form", "WhatsApp Bot", "SEO Foundation"],
            "terms_and_conditions": "50% upfront, 50% on deployment.",
        },
    )
    assert res_p1.status_code == 201
    p1_data = res_p1.json()
    prop_id = p1_data["id"]
    print(f"2. Proposal Draft Created: {p1_data['proposal_number']} (v1) | Quoted: ₹{p1_data['quoted_amount']:,.2f} | Deal Stage: PROPOSAL")

    # 3. Transition: Sent -> Viewed
    client.patch(f"/api/operations/proposals/{prop_id}/status", json={"status": "PROPOSAL_SENT"})
    client.patch(f"/api/operations/proposals/{prop_id}/status", json={"status": "VIEWED"})
    print("3. Proposal Lifecycle Advanced: PROPOSAL_SENT -> VIEWED by client.")

    # 4. Negotiate & Create Version 2 (Client requested extra discount)
    res_v2 = client.post(
        f"/api/operations/proposals/{prop_id}/versions",
        json={
            "base_price": 70000.0,
            "addons_total": 10000.0,
            "discount_amount": 12000.0,  # Discount increased by ₹7,000 -> Final ₹68,000
            "change_summary": "Discounted by ₹7,000 during closing call to secure annual contract",
        },
    )
    assert res_v2.status_code == 200
    v2_data = res_v2.json()
    print(f"4. Version 2 Appended: Quoted: ₹{v2_data['quoted_amount']:,.2f} (Base: ₹70k, Addons: ₹10k, Discount: ₹12k)")

    # 5. Transition to NEGOTIATION
    client.patch(f"/api/operations/proposals/{prop_id}/status", json={"status": "NEGOTIATION"})
    session.expire_all()
    reloaded_deal = session.get(Deal, deal.id)
    assert reloaded_deal.stage == "NEGOTIATION"
    print("5. Negotiation Status Synchronized: Deal Stage moved to NEGOTIATION.")

    # 6. Accept Proposal (WON)
    res_acc = client.patch(f"/api/operations/proposals/{prop_id}/status", json={"status": "ACCEPTED"})
    assert res_acc.status_code == 200
    acc_data = res_acc.json()
    assert acc_data["status"] == "ACCEPTED"

    # 7. Verify CRM Deal Closing Synchronization
    session.expire_all()
    closed_deal = session.get(Deal, deal.id)
    assert closed_deal.stage == "WON"
    assert closed_deal.deal_value == 68000.0
    assert closed_deal.closed_at is not None
    assert closed_deal.probability == 1.0
    print(f"6. Proposal ACCEPTED -> CRM Deal Closed as WON! Won Revenue: ₹{closed_deal.deal_value:,.2f} | Closed At: {closed_deal.closed_at}")

    # 8. Verify Commercial History & Immutability
    res_hist = client.get(f"/api/operations/proposals/{prop_id}")
    assert res_hist.status_code == 200
    hist_data = res_hist.json()
    assert len(hist_data["versions"]) == 2
    assert hist_data["versions"][0]["version_number"] == 1
    assert hist_data["versions"][0]["quoted_amount"] == 75000.0
    assert hist_data["versions"][1]["version_number"] == 2
    assert hist_data["versions"][1]["quoted_amount"] == 68000.0
    print("7. Commercial Versioning Immutability Verified: v1 (₹75k) and v2 (₹68k) preserved with zero overwrites.")

    # 9. Verify Closing Intelligence Metrics
    res_metrics = client.get("/api/operations/proposals/metrics")
    assert res_metrics.status_code == 200
    m = res_metrics.json()
    assert m["total_proposals"] == 1
    assert m["accepted_count"] == 1
    assert m["total_won_revenue"] == 68000.0
    assert m["proposal_to_win_rate"] == 100.0
    assert m["avg_negotiation_reduction"] == 7000.0  # (₹75,000 - ₹68,000)
    print(f"8. Closing Intelligence Verified: Win Rate: {m['proposal_to_win_rate']}% | Won Revenue: ₹{m['total_won_revenue']:,.2f} | Avg Negotiation Reduction: ₹{m['avg_negotiation_reduction']:,.2f}")

    print("\n=== PHASE 19 PROPOSAL, QUOTATION & DEAL CLOSING SYSTEM CONTROLLED E2E TEST: ALL CHECKS PASSED ===")


if __name__ == "__main__":
    run_controlled_phase19_e2e()
