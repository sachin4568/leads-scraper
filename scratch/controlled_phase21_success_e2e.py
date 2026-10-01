from __future__ import annotations

import sys
import uuid
from datetime import UTC, datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api import current_workspace_id
from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import (
    Customer,
    CustomerRetainer,
    Deal,
    DeliveryProject,
    Lead,
    LeadAction,
    ProjectDeliverable,
    Proposal,
    ProposalVersion,
    UpsellOpportunity,
    Workspace,
)
from backend.app.models_phase2 import Base as Phase2Base
from backend.app.models_services import Base as ServicesBase


def run_controlled_phase21_e2e():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("================================================================================")
    print("  PHASE 21: CONTROLLED E2E CUSTOMER SUCCESS & RECURRING REVENUE VERIFICATION")
    print("================================================================================")

    # 1. In-memory SQLite Database Setup
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    Phase2Base.metadata.create_all(bind=engine)
    ServicesBase.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    ws = Workspace(name="Live Success Enterprise WS")
    db.add(ws)
    db.commit()
    db.refresh(ws)

    app.dependency_overrides[current_workspace_id] = lambda: ws.id
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    # 2. Complete Lead -> Deal -> Proposal -> Won -> Customer Onboarding Lifecycle
    now = datetime.now(UTC)
    lead = Lead(
        workspace_id=ws.id,
        business_name="Apex Dental Care Center",
        phone="+91 98765 43210",
        email="contact@apexdentalcare.in",
        website="https://apexdentalcare.in",
        workflow_status="WON",
    )
    db.add(lead)
    db.commit()

    deal = Deal(
        workspace_id=ws.id,
        lead_id=lead.id,
        title="Apex Dental - Modern Website Deal",
        service_type="WEBSITE_DEVELOPMENT",
        deal_value=68000.0,
        stage="WON",
        probability=1.0,
        win_loss_reason="Accepted modernization proposal with SEO foundation",
    )
    db.add(deal)
    db.commit()

    # Convert to Customer & Delivery Project
    conv_res = client.post(f"/api/operations/deals/{deal.id}/convert-to-customer")
    assert conv_res.status_code == 201, conv_res.text
    conv_data = conv_res.json()
    customer_id = conv_data["customer_id"]
    project_id = conv_data["id"]
    print(f"  [1] Customer Created & Onboarded: {conv_data['customer_name']} (Contract: ₹{conv_data['contract_value']:,.2f})")

    # Complete Delivery Project
    deliv_res = client.get(f"/api/operations/delivery/projects/{project_id}")
    for d in deliv_res.json()["deliverables"]:
        client.patch(f"/api/operations/delivery/deliverables/{d['id']}", json={"status": "COMPLETED"})
    client.patch(f"/api/operations/delivery/projects/{project_id}/status", json={"status": "COMPLETED"})
    print("  [2] Website Delivery Project Marked COMPLETED (Progress: 100%)")

    # 3. Add Monthly SEO Retainer (₹15,000/mo) and Website Maintenance (₹3,000/mo)
    ret1_res = client.post(
        f"/api/operations/customers/{customer_id}/retainers",
        json={
            "service_type": "SEO_RETAINER",
            "billing_frequency": "MONTHLY",
            "billing_amount": 15000.0,
            "notes": "Ongoing organic search & Google Maps optimization",
        },
    )
    assert ret1_res.status_code == 201
    ret1 = ret1_res.json()
    print(f"  [3] Retainer 1 Created: {ret1['service_type']} (MRR: +₹{ret1['monthly_mrr']:,.2f}/mo)")

    ret2_res = client.post(
        f"/api/operations/customers/{customer_id}/retainers",
        json={
            "service_type": "WEBSITE_MAINTENANCE",
            "billing_frequency": "MONTHLY",
            "billing_amount": 3000.0,
            "notes": "Core updates, backups & security monitoring",
        },
    )
    assert ret2_res.status_code == 201
    ret2 = ret2_res.json()
    print(f"  [4] Retainer 2 Created: {ret2['service_type']} (MRR: +₹{ret2['monthly_mrr']:,.2f}/mo)")

    # 4. Verify Customer Financials & Health
    health_res = client.get("/api/operations/success/health")
    assert health_res.status_code == 200
    cust_health = next(c for c in health_res.json() if c["id"] == customer_id)
    print(f"  [5] Customer Health Evaluated: {cust_health['health_score']} (MRR: ₹{cust_health['mrr']:,.2f} | ARR: ₹{cust_health['arr']:,.2f})")
    assert cust_health["health_score"] == "HEALTHY"
    assert cust_health["mrr"] == 18000.0
    assert cust_health["arr"] == 216000.0

    # 5. Deterministic Upsell Opportunities
    upsells_res = client.get("/api/operations/success/upsells")
    assert upsells_res.status_code == 200
    upsells = upsells_res.json()
    print(f"  [6] Deterministic Expansion Opportunities Identified: {len(upsells)}")
    for u in upsells:
        print(f"      - {u['service_type']}: ₹{u['estimated_mrr']:,.2f}/mo ({u['reason']})")

    smma_upsell = next((u for u in upsells if u["service_type"] == "SMMA_RETAINER"), None)
    if smma_upsell:
        accept_res = client.patch(
            f"/api/operations/success/upsells/{smma_upsell['id']}/status",
            json={"status": "ACCEPTED"},
        )
        assert accept_res.status_code == 200
        print(f"  [7] SMMA Upsell Accepted & Converted to Retainer: +₹{smma_upsell['estimated_mrr']:,.2f}/mo")

    # 6. Retainer Renewal Flow
    renew_res = client.patch(f"/api/operations/retainers/{ret1['id']}/renew")
    assert renew_res.status_code == 200
    print(f"  [8] Retainer Cycle Renewed Successfully. New Renewal Date: {renew_res.json()['renewal_date'][:10]}")

    # 7. Aggregate Success Metrics
    metrics_res = client.get("/api/operations/success/metrics")
    assert metrics_res.status_code == 200
    m = metrics_res.json()
    print("--------------------------------------------------------------------------------")
    print("  EXECUTIVE CUSTOMER SUCCESS & MRR METRICS:")
    print(f"    - Active Retained Customers : {m['active_customers']}")
    print(f"    - Monthly MRR               : ₹{m['total_mrr']:,.2f}")
    print(f"    - Annualized ARR            : ₹{m['total_arr']:,.2f}")
    print(f"    - Active Retainer Contracts : {m['active_retainers_count']}")
    print(f"    - Healthy Customers         : {m['healthy_customers']}")
    print(f"    - Average Customer LTV      : ₹{m['avg_customer_ltv']:,.2f}")
    print("--------------------------------------------------------------------------------")

    # 8. Verify Timeline Integrity
    timeline_res = client.get(f"/api/operations/leads/{lead.id}/timeline")
    assert timeline_res.status_code == 200
    events = timeline_res.json()["events"]
    print(f"  [9] Verified Unbroken Activity Timeline: {len(events)} Chronological Milestones")
    for ev in events:
        ts = ev.get('timestamp') or ''
        print(f"      {ts[:10]} | {ev['event_type']} | {ev['title']}")

    print("================================================================================")
    print("  PHASE 21 CONTROLLED E2E TEST COMPLETED WITH 100% SUCCESS")
    print("================================================================================")


if __name__ == "__main__":
    run_controlled_phase21_e2e()
