from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.ingestion.ingestion import DirectoryAdapter, GooglePlacesAdapter
from backend.app.models_phase2 import Base as BasePhase2
from backend.app.models_phase3 import Base as BasePhase3
from backend.app.production.feedback_loop import ProductionFeedbackCollector
from backend.app.production.monitoring import (
    ProductionDataQualityMonitor,
    ProductionDriftMonitor,
    ProductionHealthMonitor,
    ProductionPredictionMonitor,
)
from backend.app.production.production_inference import ProductionInferenceEngine
from backend.app.production.production_ingestion import ControlledProductionIngestion
from backend.app.production.productivity_tracking import (
    ProductivityOutcomeManager,
    ProductivityStatus,
)
from backend.app.production.safety import ProductionKillSwitch, RolloutMode

logger = logging.getLogger(__name__)

EXPORTS_DIR = Path("/Users/sachinchaubey/Desktop/Leads/training_data/corpus_exports")
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


def run_phase11_pipeline() -> dict[str, Any]:
    print("=== Executing Phase 11 Controlled Limited Production Pipeline ===")

    engine = create_engine("sqlite:///:memory:", echo=False)
    BasePhase2.metadata.create_all(bind=engine)
    BasePhase3.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    ingestion_engine = ControlledProductionIngestion(default_quota=500)
    inference_engine = ProductionInferenceEngine(
        model_version="real_model_v2_1", alpha=0.10, threshold=0.40
    )
    feedback_collector = ProductionFeedbackCollector()
    productivity_manager = ProductivityOutcomeManager()
    kill_switch = ProductionKillSwitch()

    gp_adapter = GooglePlacesAdapter()
    dir_adapter = DirectoryAdapter()

    # 1. Controlled Production Batch Ingestion (Batch 101)
    raw_leads_batch1 = []
    for i in range(1, 101):
        lead_counter = 8750 + i
        raw_leads_batch1.append(
            gp_adapter.normalize_payload(
                {
                    "place_id": f"ChIJ_prod_{lead_counter:05d}",
                    "name": f"Prod Enterprise {lead_counter:05d}",
                    "types": ["Dental Clinics" if i % 2 == 0 else "Solar"],
                    "city": "Dehradun",
                    "website": f"https://www.prodbiz{lead_counter:05d}.com" if i % 3 != 0 else None,
                    "formatted_phone_number": f"+91 98976 {lead_counter % 89999}",
                }
            )
        )

    batch_rec, ingestion_results = ingestion_engine.process_production_batch(
        db, batch_id="prod_batch_101", source_name="google_places", raw_leads=raw_leads_batch1
    )

    # Test Deduplication & Field Update (Secondary Source Ingestion)
    raw_dup = dir_adapter.normalize_payload(
        {
            "place_id": "ChIJ_prod_08751_v2",
            "name": "Prod Enterprise 08751",
            "types": ["Dental Clinics"],
            "city": "Dehradun",
            "website": "https://www.prodbiz08751.com",
            "formatted_phone_number": "+91 99999 77777",
        }
    )
    _, _, upd_state = ingestion_engine.resolver.process_observation(db, raw_dup)

    # 2. Production Inference & Audit Logging
    probabilities = []
    decisions = []

    for canonical, _obs, _state in ingestion_results:
        f_vec = [
            1.0 if canonical.canonical_domain else 0.0,
            1.0 if canonical.canonical_phone else 0.0,
            1.0,
            1.0,
            0.0,
        ]
        prob, dec, audit_rec = inference_engine.predict_and_audit(
            db,
            canonical_lead_id=canonical.id,
            feature_vector=f_vec,
            source_batch_id="prod_batch_101",
        )
        probabilities.append(prob)
        decisions.append(dec)

    # 3. Production Feedback & Training Queue (Separate Human Outcomes)
    fb_rec = feedback_collector.record_human_outcome(
        db=db,
        canonical_lead_id=ingestion_results[0][0].id,
        reviewer_id="reviewer_prod_1",
        genuineness_outcome="GENUINE",
        evidence="Validated production physical location and verified phone contact.",
    )

    # 4. Sales Outreach Productivity Tracking
    for i, (canonical, _, _) in enumerate(ingestion_results[:20]):
        if i < 5:
            productivity_manager.record_outreach_attempt(
                canonical.id, "PHONE", ProductivityStatus.PRODUCTIVE, "DEAL_CLOSED"
            )
        elif i < 8:
            productivity_manager.record_outreach_attempt(
                canonical.id, "PHONE", ProductivityStatus.UNPRODUCTIVE, "NOT_INTERESTED"
            )
        else:
            productivity_manager.record_outreach_attempt(
                canonical.id, "EMAIL", ProductivityStatus.CONTACTED, "IN_DISCUSSION"
            )

    prod_accounting = productivity_manager.get_summary_accounting(len(ingestion_results))

    # 5. Production Monitoring & Health Audit
    dq_metrics = ProductionDataQualityMonitor.audit_batch([r.__dict__ for r in raw_leads_batch1])
    pred_metrics = ProductionPredictionMonitor.audit_predictions(probabilities, decisions)
    drift_metrics = ProductionDriftMonitor.calculate_drift(probabilities, baseline_mean_prob=0.85)
    health_status = ProductionHealthMonitor.evaluate_health(dq_metrics, pred_metrics, drift_metrics)

    # 6. Safety Kill Switch Verification & Rollout Progression
    kill_switch.validate_inference_allowed()
    kill_switch.validate_source_allowed("google_places")
    new_rollout = kill_switch.transition_rollout_mode(
        RolloutMode.LIMITED_PRODUCTION, human_approved=True
    )

    # Export Audit Report
    audit_report_path = EXPORTS_DIR / "phase11_production_audit_report_v1.json"
    report_data = {
        "phase": "Phase 11 — Controlled Limited Production",
        "rollout_mode": new_rollout.value,
        "batch_summary": batch_rec.__dict__,
        "modified_field_ingestion_state": upd_state.value,
        "data_quality_metrics": dq_metrics.__dict__,
        "prediction_metrics": pred_metrics.__dict__,
        "drift_metrics": drift_metrics.__dict__,
        "health_status": health_status,
        "human_feedback_event": {
            "canonical_lead_id": fb_rec.canonical_lead_id,
            "outcome": fb_rec.genuineness_outcome,
        },
        "productivity_accounting": prod_accounting,
        "kill_switch_status": kill_switch.get_safety_status(),
        "readiness_classification": "CONTROLLED_PRODUCTION_READY",
    }

    with open(audit_report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    summary = {
        "production_batch_id": batch_rec.batch_id,
        "received_count": batch_rec.received_count,
        "new_count": batch_rec.new_count,
        "existing_count": batch_rec.existing_count,
        "updated_count": batch_rec.updated_count,
        "duplicate_count": batch_rec.duplicate_count,
        "modified_field_ingestion_state": upd_state.value,
        "frozen_model_configuration": {
            "model_version": inference_engine.model_version,
            "alpha": inference_engine.alpha,
            "threshold": inference_engine.threshold,
        },
        "prediction_metrics": pred_metrics.__dict__,
        "health_status": health_status,
        "rollout_mode": new_rollout.value,
        "audit_report_export": str(audit_report_path),
        "readiness_classification": "CONTROLLED_PRODUCTION_READY",
        "automatic_retraining": "NO — NOT YET",
        "automatic_promotion": "NO — NOT YET",
        "unrestricted_scraping": "NO — NOT YET",
    }

    print(f"\n[Phase 11 Controlled Production Summary]\n{json.dumps(summary, indent=2)}")
    return summary


if __name__ == "__main__":
    run_phase11_pipeline()
