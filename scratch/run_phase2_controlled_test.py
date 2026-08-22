from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.ingestion.ingestion import (
    DirectoryAdapter,
    FacebookAdapter,
    GooglePlacesAdapter,
    YelpAdapter,
)
from backend.app.ingestion.intelligence_foundations import (
    HumanFeedbackManager,
)
from backend.app.ingestion.lifecycle import LifecycleResolver, LifecycleState
from backend.app.models_phase2 import (
    Base,
    CanonicalLead,
    HumanOutcomeEventRecord,
    LeadChangeHistory,
    LeadObservation,
)

logger = logging.getLogger(__name__)


def run_phase2_controlled_test() -> dict[str, Any]:
    print("=== Executing Phase 2 Controlled Ingestion Test Scenarios ===")

    # Use in-memory SQLite for isolated scenario execution
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    resolver = LifecycleResolver()
    gp_adapter = GooglePlacesAdapter()
    yelp_adapter = YelpAdapter()
    fb_adapter = FacebookAdapter()
    dir_adapter = DirectoryAdapter()

    results: list[dict[str, Any]] = []

    # -------------------------------------------------------------
    # Scenario 1: First Ingestion of Apex Dental Clinic (Dehradun)
    # -------------------------------------------------------------
    p1 = gp_adapter.normalize_payload(
        {
            "place_id": "ChIJ_apex_dehradun_001",
            "name": "Apex Dental Clinic",
            "formatted_address": "Rajpur Road, Dehradun",
            "city": "Dehradun",
            "state": "Uttarakhand",
            "website": "https://www.apexdental.com",
            "formatted_phone_number": "+91-98970-01001",
            "types": ["Dental Clinics"],
        }
    )
    c1, obs1, st1 = resolver.process_observation(db, p1)
    results.append(
        {
            "scenario": "1. First Ingestion",
            "expected": "NEW",
            "actual": st1.value,
            "pass": st1 == LifecycleState.NEW,
        }
    )

    # -------------------------------------------------------------
    # Scenario 2: Idempotent Ingestion (Same payload, same source ID)
    # -------------------------------------------------------------
    c2, obs2, st2 = resolver.process_observation(db, p1)
    results.append(
        {
            "scenario": "2. Idempotent Ingestion",
            "expected": "DUPLICATE",
            "actual": st2.value,
            "pass": st2 == LifecycleState.DUPLICATE,
        }
    )

    # -------------------------------------------------------------
    # Scenario 3: Cross-Source Consolidation (Yelp payload for same Apex Dental)
    # -------------------------------------------------------------
    p3 = yelp_adapter.normalize_payload(
        {
            "id": "yelp_apex_001",
            "name": "Apex Dental",
            "location": {"address1": "Rajpur Road", "city": "Dehradun", "state": "Uttarakhand"},
            "url": "https://apexdental.com/yelp",
            "display_phone": "+91 98970 01001",
            "categories": [{"title": "Dental Clinics"}],
        }
    )
    c3, obs3, st3 = resolver.process_observation(db, p3)
    results.append(
        {
            "scenario": "3. Cross-Source Consolidation",
            "expected_canonical_id": c1.id,
            "actual_canonical_id": c3.id,
            "actual_state": st3.value,
            "pass": c1.id == c3.id,
        }
    )

    # -------------------------------------------------------------
    # Scenario 4: Changed Website & Phone (UPDATED state & Audit Delta)
    # -------------------------------------------------------------
    p4 = fb_adapter.normalize_payload(
        {
            "page_id": "fb_apex_001",
            "name": "Apex Dental Clinic",
            "location": {"city": "Dehradun"},
            "website": "https://www.apexdentalclinic.in",
            "phone": "+91-98970-01001",
            "category": "Dental Clinics",
        }
    )
    c4, obs4, st4 = resolver.process_observation(db, p4)
    ch_count = (
        db.query(LeadChangeHistory).filter(LeadChangeHistory.canonical_lead_id == c1.id).count()
    )
    results.append(
        {
            "scenario": "4. Field Update & Change History",
            "expected_state": "UPDATED",
            "actual_state": st4.value,
            "change_history_entries": ch_count,
            "pass": st4 == LifecycleState.UPDATED and ch_count >= 2,
        }
    )

    # -------------------------------------------------------------
    # Scenario 5: Same Business Name in DIFFERENT City (Haridwar) -> Zero False Merge
    # -------------------------------------------------------------
    p5 = dir_adapter.normalize_payload(
        {
            "source_name": "directory",
            "id": "dir_apex_haridwar_001",
            "business_name": "Apex Dental Clinic",
            "city": "Haridwar",
            "state": "Uttarakhand",
            "phone": "+91-98970-02002",
            "website": "https://www.apexdentalharidwar.com",
            "industry": "Dental Clinics",
        }
    )
    c5, obs5, st5 = resolver.process_observation(db, p5)
    results.append(
        {
            "scenario": "5. Same Name Different City (Zero False Merge)",
            "expected_separate_lead": True,
            "pass": c5.id != c1.id,
        }
    )

    # -------------------------------------------------------------
    # Scenario 6: Same Name Different Phone (Zero False Merge)
    # -------------------------------------------------------------
    p6 = dir_adapter.normalize_payload(
        {
            "source_name": "directory",
            "id": "dir_apex_rishikesh_001",
            "business_name": "Apex Dental Clinic",
            "city": "Rishikesh",
            "phone": "+91-98970-03003",
            "industry": "Dental Clinics",
        }
    )
    c6, obs6, st6 = resolver.process_observation(db, p6)
    results.append(
        {
            "scenario": "6. Same Name Different Phone (Zero False Merge)",
            "expected_separate_lead": True,
            "pass": c6.id != c1.id,
        }
    )

    # -------------------------------------------------------------
    # Scenario 7: Human Feedback Preservation
    # -------------------------------------------------------------
    HumanFeedbackManager.record_feedback(
        db=db,
        canonical_lead_id=c1.id,
        original_prediction="GENUINE",
        original_probability=0.94,
        model_version="v1.1_phase1_stratified",
        human_outcome="GENUINE_PRODUCTIVE",
        reason="Owner booked meeting for SEO redesign",
    )
    fb_count = (
        db.query(HumanOutcomeEventRecord)
        .filter(HumanOutcomeEventRecord.canonical_lead_id == c1.id)
        .count()
    )
    results.append(
        {
            "scenario": "7. Human Feedback Storage",
            "expected_entries": 1,
            "actual_entries": fb_count,
            "pass": fb_count == 1,
        }
    )

    print("\n=== CONTROLLED TEST RESULTS ===")
    all_passed = True
    for r in results:
        status = "PASSED" if r["pass"] else "FAILED"
        if not r["pass"]:
            all_passed = False
        print(f"[{status}] {r['scenario']}: {r}")

    summary = {
        "all_passed": all_passed,
        "scenarios_executed": len(results),
        "scenarios_passed": sum(1 for r in results if r["pass"]),
        "canonical_leads_created": db.query(CanonicalLead).count(),
        "total_observations_recorded": db.query(LeadObservation).count(),
        "change_history_logs": db.query(LeadChangeHistory).count(),
        "human_feedback_events": db.query(HumanOutcomeEventRecord).count(),
    }
    print(f"\nSummary: {summary}")
    return summary


if __name__ == "__main__":
    run_phase2_controlled_test()
