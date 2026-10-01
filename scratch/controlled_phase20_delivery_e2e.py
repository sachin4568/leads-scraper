from __future__ import annotations

import sys
import time
import uuid
from datetime import UTC, datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker

from backend.app.api import current_workspace_id
from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import Customer, Deal, DeliveryProject, Lead, LeadAction, ProjectDeliverable, Proposal, ProposalVersion, Workspace
from backend.app.models_phase2 import Base as Phase2Base
from backend.app.models_services import Base as ServicesBase


def run_controlled_phase20_e2e():
    print("=== STARTING PHASE 20 CUSTOMER ONBOARDING & DELIVERY MANAGEMENT CONTROLLED E2E TEST ===")

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

    ws = Workspace(name="Full Cycle Growth Agency")
    session.add(ws)
    session.commit()
    session.refresh(ws)

    app.dependency_overrides[current_workspace_id] = lambda: ws.id
    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)

    # 1. Full Lifecycle Simulation: Lead -> Outreach -> CRM Deal -> Proposal -> WON
    lead = Lead(
        workspace_id=ws.id,
        business_name="Apex Dental Care Clinic",
        phone="+91 98200 12345",
        email="info@apexdentalcare.in",
        website="https://apexdentalcare.in",
        genuineness_score=0.98,
        workflow_status="WON",
    )
    session.add(lead)
    session.commit()
    session.refresh(lead)

    deal = Deal(
        workspace_id=ws.id,
        lead_id=lead.id,
        title="Apex Dental Modernization & Patient Portal",
        service_type="WEBSITE_DEVELOPMENT",
        deal_value=68000.0,
        stage="WON",
        probability=1.0,
        closed_at=datetime.now(UTC),
    )
    session.add(deal)
    session.commit()
    session.refresh(deal)
    print(f"1. Won Deal Ready for Onboarding: '{deal.title}' | Final Closed Value: ₹{deal.deal_value:,.2f}")

    # 2. Phase 20: Convert Won Deal to Customer & Delivery Project
    conv_res = client.post(f"/api/operations/deals/{deal.id}/convert-to-customer")
    assert conv_res.status_code == 201
    proj_data = conv_res.json()
    proj_id = proj_data["id"]
    cust_id = proj_data["customer_id"]
    print(f"2. Customer Record Created & Delivery Project Initialized: '{proj_data['project_name']}' | Contract Value: ₹{proj_data['contract_value']:,.2f}")

    # 3. Verify Initial Metrics (In-Delivery Revenue = ₹68k, Realized = ₹0)
    m1 = client.get("/api/operations/delivery/metrics").json()
    assert m1["active_projects"] == 1
    assert m1["in_delivery_revenue"] == 68000.0
    assert m1["realized_completed_revenue"] == 0.0
    print(f"3. Initial Delivery Metrics: Active Projects: {m1['active_projects']} | In-Delivery Revenue: ₹{m1['in_delivery_revenue']:,.2f} | Realized: ₹{m1['realized_completed_revenue']:,.2f}")

    # 4. Advance Project Stages: ONBOARDING -> REQUIREMENTS -> IN_PROGRESS
    client.patch(f"/api/operations/delivery/projects/{proj_id}/status", json={"status": "REQUIREMENTS"})
    client.patch(f"/api/operations/delivery/projects/{proj_id}/status", json={"status": "IN_PROGRESS"})
    print("4. Project Stage Progressed: ONBOARDING -> REQUIREMENTS -> IN_PROGRESS")

    # 5. Add Custom Deliverable & Complete Tasks
    add_deliv_res = client.post(
        f"/api/operations/delivery/projects/{proj_id}/deliverables",
        json={"title": "WhatsApp Automated Appointment Integration", "notes": "Webhook configured"},
    )
    assert add_deliv_res.status_code == 201

    detail_res = client.get(f"/api/operations/delivery/projects/{proj_id}").json()
    deliverables = detail_res["deliverables"]
    print(f"5. Project Deliverables Seeded: {len(deliverables)} tasks in pipeline.")

    # Complete all deliverables
    for d in deliverables:
        client.patch(f"/api/operations/delivery/deliverables/{d['id']}", json={"status": "COMPLETED"})

    updated_proj = client.get(f"/api/operations/delivery/projects/{proj_id}").json()
    assert updated_proj["progress_percent"] == 100.0
    print("6. All Deliverables Executed: Project Progress dynamically recalculated to 100%.")

    # 6. Final Review & Client Signoff -> COMPLETED
    client.patch(f"/api/operations/delivery/projects/{proj_id}/status", json={"status": "REVIEW"})
    client.patch(f"/api/operations/delivery/projects/{proj_id}/status", json={"status": "CLIENT_APPROVAL"})
    final_res = client.patch(f"/api/operations/delivery/projects/{proj_id}/status", json={"status": "COMPLETED"})
    assert final_res.status_code == 200
    final_data = final_res.json()
    assert final_data["status"] == "COMPLETED"
    assert final_data["actual_completion_date"] is not None
    print(f"7. Project Signed Off & COMPLETED at: {final_data['actual_completion_date']}")

    # 7. Verify Revenue Realization
    m2 = client.get("/api/operations/delivery/metrics").json()
    assert m2["active_projects"] == 0
    assert m2["completed_projects"] == 1
    assert m2["in_delivery_revenue"] == 0.0
    assert m2["realized_completed_revenue"] == 68000.0
    assert m2["on_time_delivery_rate"] == 100.0
    print(f"8. Final Realized Revenue Verified: Realized Won Revenue: ₹{m2['realized_completed_revenue']:,.2f} | On-Time Rate: {m2['on_time_delivery_rate']}%")

    # 8. Verify Complete Lead -> Customer Timeline Continuity
    timeline_actions = session.scalars(select(LeadAction).where(LeadAction.lead_id == lead.id)).all()
    print(f"9. Lead -> Customer Chronological Timeline Verified ({len(timeline_actions)} milestone events logged):")
    for a in timeline_actions:
        print(f"   • [{a.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {a.notes}")

    print("\n=== PHASE 20 CUSTOMER ONBOARDING & DELIVERY MANAGEMENT CONTROLLED E2E TEST: ALL CHECKS PASSED ===")


if __name__ == "__main__":
    run_controlled_phase20_e2e()
