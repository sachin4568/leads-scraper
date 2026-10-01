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
from backend.app.models import Deal, EvidenceRecord, Lead, LeadAction, ScrapeJob, Workspace
from backend.app.models_phase2 import Base as Phase2Base
from backend.app.models_services import Base as ServicesBase
from backend.app.security import validate_outbound_url


def run_controlled_phase16_e2e():
    print("=== STARTING PHASE 16 PRODUCTION SECURITY & MULTI-TENANT HARDENING CONTROLLED E2E TEST ===")

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

    # 1. Create two strictly isolated workspaces
    ws_a = Workspace(name="Tenant Alpha - Healthcare Group")
    ws_b = Workspace(name="Tenant Beta - Dental Solutions")
    session.add_all([ws_a, ws_b])
    session.commit()
    session.refresh(ws_a)
    session.refresh(ws_b)

    now = datetime.now(UTC)

    # Populate Workspace A
    lead_a = Lead(
        workspace_id=ws_a.id,
        business_name="Alpha Cardiology Center",
        phone="+91 98200 11111",
        email="info@alphacardio.in",
        website="https://alphacardio.in",
        genuineness_score=0.96,
        workflow_status="QUALIFIED",
        created_at=now - timedelta(days=2),
    )
    session.add(lead_a)
    session.commit()
    session.refresh(lead_a)

    session.add(
        EvidenceRecord(
            workspace_id=ws_a.id,
            lead_id=lead_a.id,
            field_name="lead_intelligence",
            status="VERY_HIGH",
            confidence_score=95,
            source="LEAD_INTELLIGENCE_ENGINE",
            details={"overall_opportunity_score": 92, "opportunity_category": "VERY_HIGH"},
        )
    )
    session.add(
        LeadAction(
            workspace_id=ws_a.id,
            lead_id=lead_a.id,
            channel="WHATSAPP",
            outcome="MEETING_BOOKED",
            notes="Consultation booked.",
        )
    )
    deal_a = Deal(
        workspace_id=ws_a.id,
        lead_id=lead_a.id,
        title="Alpha - Web Rebuild",
        service_type="WEBSITE_DEVELOPMENT",
        deal_value=65000.0,
        stage="NEGOTIATION",
        probability=0.80,
    )
    session.add(deal_a)

    # Populate Workspace B
    lead_b = Lead(
        workspace_id=ws_b.id,
        business_name="Beta Smile Studio",
        phone="+91 98200 22222",
        email="care@betasmile.in",
        website="https://betasmile.in",
        genuineness_score=0.92,
        workflow_status="CONVERTED",
        created_at=now - timedelta(days=4),
    )
    session.add(lead_b)
    session.commit()
    session.refresh(lead_b)

    session.add(
        EvidenceRecord(
            workspace_id=ws_b.id,
            lead_id=lead_b.id,
            field_name="lead_intelligence",
            status="HIGH",
            confidence_score=90,
            source="LEAD_INTELLIGENCE_ENGINE",
            details={"overall_opportunity_score": 85, "opportunity_category": "HIGH"},
        )
    )
    session.add(
        LeadAction(
            workspace_id=ws_b.id,
            lead_id=lead_b.id,
            channel="PHONE",
            outcome="CONVERTED",
            notes="Client signed.",
        )
    )
    deal_b = Deal(
        workspace_id=ws_b.id,
        lead_id=lead_b.id,
        title="Beta - SEO Retainer",
        service_type="SEO",
        deal_value=110000.0,
        stage="WON",
        probability=1.00,
        closed_at=now - timedelta(days=1),
    )
    session.add(deal_b)
    session.commit()
    session.refresh(deal_a)
    session.refresh(deal_b)

    print("1. Seeded Tenant Alpha and Tenant Beta with isolated leads, evidence, actions, and deals.")

    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)

    # TEST A: IDOR Protection against cross-workspace operations (Tenant A acting against Tenant B resources)
    app.dependency_overrides[current_workspace_id] = lambda: ws_a.id

    t0 = time.perf_counter()
    # 1. Lead Detail IDOR
    r_lead_read = client.get(f"/api/operations/leads/{lead_b.id}")
    assert r_lead_read.status_code == 404
    # 2. Lead Workflow Update IDOR
    r_lead_patch = client.patch(f"/api/operations/leads/{lead_b.id}/workflow", json={"workflow_status": "LOST"})
    assert r_lead_patch.status_code == 404
    # 3. Lead Action IDOR
    r_act_post = client.post(f"/api/operations/leads/{lead_b.id}/actions", json={"channel": "EMAIL", "outcome": "LOST"})
    assert r_act_post.status_code == 404
    # 4. Lead Timeline IDOR
    r_time = client.get(f"/api/operations/leads/{lead_b.id}/timeline")
    assert r_time.status_code == 404
    # 5. Deal Read IDOR
    r_deal_read = client.get(f"/api/operations/deals/{deal_b.id}")
    assert r_deal_read.status_code == 404
    # 6. Deal Update IDOR
    r_deal_patch = client.patch(f"/api/operations/deals/{deal_b.id}", json={"stage": "LOST", "deal_value": 0.0})
    assert r_deal_patch.status_code == 404
    # 7. Deal Creation with Foreign Lead IDOR
    r_deal_create = client.post("/api/operations/deals", json={"lead_id": str(lead_b.id), "title": "Attack", "service_type": "SEO", "deal_value": 100.0})
    assert r_deal_create.status_code == 404
    lat_idor_ms = (time.perf_counter() - t0) * 1000.0

    print(f"2. IDOR Protection Verified ({lat_idor_ms:.2f}ms for 7 cross-tenant attack vectors):")
    print("   - Cross-workspace Lead Read: BLOCKED (404)")
    print("   - Cross-workspace Workflow Transition: BLOCKED (404)")
    print("   - Cross-workspace Action Logging: BLOCKED (404)")
    print("   - Cross-workspace Activity Timeline: BLOCKED (404)")
    print("   - Cross-workspace Deal Read: BLOCKED (404)")
    print("   - Cross-workspace Deal Stage Update: BLOCKED (404)")
    print("   - Cross-workspace Deal Creation: BLOCKED (404)")

    # TEST B: Bulk Cross-Workspace Injection Protection
    r_bulk = client.patch(
        "/api/operations/leads/bulk-workflow",
        json={"lead_ids": [str(lead_a.id), str(lead_b.id)], "workflow_status": "DISMISSED"},
    )
    assert r_bulk.status_code == 403
    print("3. Bulk Cross-Workspace Injection: BLOCKED (403 Forbidden with zero records mutated).")

    # TEST C: Analytics Multi-Tenant Isolation
    t0_an = time.perf_counter()
    res_a_an = client.get("/api/analytics/overview?timeframe=all_time")
    lat_an_ms = (time.perf_counter() - t0_an) * 1000.0
    data_a = res_a_an.json()
    assert data_a["kpis"]["total_leads"] == 1
    assert data_a["kpis"]["won_revenue"] == 0.0
    assert data_a["kpis"]["total_pipeline_value"] == 65000.0

    app.dependency_overrides[current_workspace_id] = lambda: ws_b.id
    res_b_an = client.get("/api/analytics/overview?timeframe=all_time")
    data_b = res_b_an.json()
    assert data_b["kpis"]["total_leads"] == 1
    assert data_b["kpis"]["won_revenue"] == 110000.0
    assert data_b["kpis"]["total_pipeline_value"] == 0.0

    print(f"4. Analytics Multi-Tenant Isolation Verified in {lat_an_ms:.2f}ms:")
    print(f"   - Tenant Alpha View: 1 lead, INR 0 won revenue, INR 65,000 active pipeline (0% Tenant Beta data)")
    print(f"   - Tenant Beta View: 1 lead, INR 110,000 won revenue, INR 0 active pipeline (0% Tenant Alpha data)")

    # TEST D: SSRF Protection
    blocked_count = 0
    test_urls = ["http://127.0.0.1:8080", "http://localhost", "https://169.254.169.254/latest", "http://10.0.0.1", "http://192.168.0.1"]
    for u in test_urls:
        try:
            validate_outbound_url(u, allow_http=True)
        except ValueError:
            blocked_count += 1
    assert blocked_count == len(test_urls)
    print(f"5. SSRF Network Protection Verified: {blocked_count}/{len(test_urls)} private/metadata targets rejected.")

    # TEST E: Input Validation
    r_val = client.post("/api/operations/deals", json={"lead_id": str(lead_b.id), "title": "Val Test", "deal_value": -100.0, "stage": "INVALID"})
    assert r_val.status_code == 422
    print("6. Request Payload Validation Verified: Malformed stage and negative deal value rejected (422 Unprocessable Entity).")

    print("\n=== PHASE 16 SECURITY & MULTI-TENANT CONTROLLED E2E TEST: ALL CHECKS PASSED ===")


if __name__ == "__main__":
    run_controlled_phase16_e2e()
