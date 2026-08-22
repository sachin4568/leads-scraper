from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models_phase3 import (
    FeedbackDatasetRecord,
    HumanOutcomeEvent,
)

logger = logging.getLogger(__name__)

EXPORTS_DIR = Path("/Users/sachinchaubey/Desktop/Leads/training_data/feedback_exports")
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


class TemporalLeakageError(Exception):
    """Raised when post-prediction fields or invalid timestamp ordering is detected during export."""

    pass


# Forbidden Post-Prediction Leakage Fields (Must NEVER enter feature inputs)
POST_PREDICTION_LEAKAGE_FIELDS: set[str] = {
    "human_outcome",
    "productivity_outcome",
    "qualification_outcome",
    "sales_result",
    "later_audit_result",
    "reviewer_notes",
}


class FeedbackDatasetExporter:
    """Exports leak-free, versioned training datasets for Genuineness, Productivity, and Service Opportunity."""

    def export_genuineness_dataset(
        self, db: Session, dataset_version: str = "feedback_dataset_v1.0"
    ) -> dict[str, Any]:
        """Exports pre-prediction features -> VALIDATED GENUINE/NOT_GENUINE binary dataset."""
        events = (
            db.query(HumanOutcomeEvent)
            .filter(HumanOutcomeEvent.feedback_state == "VALIDATED")
            .all()
        )

        rows: list[dict[str, Any]] = []
        gen_count, not_gen_count = 0, 0

        for evt in events:
            # 1. Temporal Ordering Verification
            pred_rec = evt.prediction_record
            if pred_rec:
                if not (
                    pred_rec.feature_snapshot_timestamp
                    <= pred_rec.prediction_timestamp
                    <= evt.human_outcome_timestamp
                ):
                    raise TemporalLeakageError(
                        f"Temporal leakage detected! Invalid timestamp sequence for lead {evt.canonical_lead_id}"
                    )

            if evt.genuineness_outcome not in ("GENUINE", "NOT_GENUINE"):
                continue

            target = 1 if evt.genuineness_outcome == "GENUINE" else 0
            if target == 1:
                gen_count += 1
            else:
                not_gen_count += 1

            # Feature input (Pre-prediction ONLY)
            feature_row = {
                "canonical_lead_id": evt.canonical_lead_id,
                "prediction_id": evt.prediction_id,
                "target_genuineness": target,
                "feature_snapshot_timestamp": pred_rec.feature_snapshot_timestamp.isoformat()
                if pred_rec
                else None,
                "prediction_timestamp": pred_rec.prediction_timestamp.isoformat()
                if pred_rec
                else None,
                "outcome_timestamp": evt.human_outcome_timestamp.isoformat(),
            }
            rows.append(feature_row)

        artifact_path = EXPORTS_DIR / f"{dataset_version}_genuineness.json"
        export_payload = {
            "dataset_version": dataset_version,
            "dataset_type": "GENUINESS",
            "feature_version": "v1.0_allowlist",
            "row_count": len(rows),
            "label_distribution": {"GENUINE": gen_count, "NOT_GENUINE": not_gen_count},
            "rows": rows,
        }

        with open(artifact_path, "w", encoding="utf-8") as f:
            json.dump(export_payload, f, indent=2)

        # Register Dataset Record
        rec = FeedbackDatasetRecord(
            dataset_version=f"{dataset_version}_genuineness",
            dataset_type="GENUINENESS",
            feature_version="v1.0_allowlist",
            row_count=len(rows),
            label_distribution=json.dumps({"GENUINE": gen_count, "NOT_GENUINE": not_gen_count}),
            artifact_path=str(artifact_path),
        )
        db.add(rec)
        db.commit()

        logger.info(f"[Dataset Exporter] Exported {len(rows)} rows to {artifact_path}")
        return export_payload

    def export_productivity_dataset(
        self, db: Session, dataset_version: str = "feedback_dataset_v1.0"
    ) -> dict[str, Any]:
        """Exports pre-outcome features -> VALIDATED PRODUCTIVE/UNPRODUCTIVE dataset (Preserving GENUINE+UNPRODUCTIVE separately)."""
        events = (
            db.query(HumanOutcomeEvent)
            .filter(HumanOutcomeEvent.feedback_state == "VALIDATED")
            .filter(HumanOutcomeEvent.productivity_outcome.in_(["PRODUCTIVE", "UNPRODUCTIVE"]))
            .all()
        )

        rows: list[dict[str, Any]] = []
        prod_count, unprod_count = 0, 0

        for evt in events:
            target = 1 if evt.productivity_outcome == "PRODUCTIVE" else 0
            if target == 1:
                prod_count += 1
            else:
                unprod_count += 1

            rows.append(
                {
                    "canonical_lead_id": evt.canonical_lead_id,
                    "genuineness_outcome": evt.genuineness_outcome,
                    "target_productivity": target,
                    "outcome_timestamp": evt.human_outcome_timestamp.isoformat(),
                }
            )

        artifact_path = EXPORTS_DIR / f"{dataset_version}_productivity.json"
        export_payload = {
            "dataset_version": dataset_version,
            "dataset_type": "PRODUCTIVITY",
            "feature_version": "v1.0_allowlist",
            "row_count": len(rows),
            "label_distribution": {"PRODUCTIVE": prod_count, "UNPRODUCTIVE": unprod_count},
            "rows": rows,
        }

        with open(artifact_path, "w", encoding="utf-8") as f:
            json.dump(export_payload, f, indent=2)

        return export_payload

    def export_service_opportunity_dataset(
        self, db: Session, dataset_version: str = "feedback_dataset_v1.0"
    ) -> dict[str, Any]:
        """Exports multi-label service opportunity target dataset."""
        events = (
            db.query(HumanOutcomeEvent)
            .filter(HumanOutcomeEvent.feedback_state == "VALIDATED")
            .all()
        )

        rows: list[dict[str, Any]] = []
        for evt in events:
            flags = (
                json.loads(evt.service_opportunity_flags) if evt.service_opportunity_flags else []
            )
            rows.append(
                {
                    "canonical_lead_id": evt.canonical_lead_id,
                    "multi_label_service_targets": flags,
                    "outcome_timestamp": evt.human_outcome_timestamp.isoformat(),
                }
            )

        artifact_path = EXPORTS_DIR / f"{dataset_version}_service_opportunity.json"
        export_payload = {
            "dataset_version": dataset_version,
            "dataset_type": "SERVICE_OPPORTUNITY_MULTI_LABEL",
            "feature_version": "v1.0_allowlist",
            "row_count": len(rows),
            "rows": rows,
        }

        with open(artifact_path, "w", encoding="utf-8") as f:
            json.dump(export_payload, f, indent=2)

        return export_payload
