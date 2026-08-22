from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.app.feedback.dataset_exporter import (
    TemporalLeakageError,
)
from backend.app.models_phase3 import HumanOutcomeEvent

logger = logging.getLogger(__name__)

EXPORTS_DIR = Path("/Users/sachinchaubey/Desktop/Leads/training_data/corpus_exports")
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class CorpusCountsSummary:
    """Explicit Breakdown of Total, Human-Reviewed, Validated, and Training-Eligible Corpora."""

    total_real_corpus: int
    human_reviewed_corpus: int
    fully_validated_corpus: int
    genuineness_training_eligible_corpus: int
    productivity_training_eligible_corpus: int
    service_opportunity_training_eligible_corpus: int


class CorpusExporter:
    """Manages ground-truth validation auditing, candidate dataset exports, and corpus count tracking."""

    def compute_corpus_counts(
        self, db: Session, total_real_leads_count: int = 5000
    ) -> CorpusCountsSummary:
        reviewed = db.query(HumanOutcomeEvent).count()
        validated = (
            db.query(HumanOutcomeEvent)
            .filter(HumanOutcomeEvent.feedback_state == "VALIDATED")
            .count()
        )
        gen_eligible = (
            db.query(HumanOutcomeEvent)
            .filter(HumanOutcomeEvent.feedback_state == "VALIDATED")
            .filter(HumanOutcomeEvent.genuineness_outcome.in_(["GENUINE", "NOT_GENUINE"]))
            .count()
        )
        prod_eligible = (
            db.query(HumanOutcomeEvent)
            .filter(HumanOutcomeEvent.feedback_state == "VALIDATED")
            .filter(HumanOutcomeEvent.productivity_outcome.in_(["PRODUCTIVE", "UNPRODUCTIVE"]))
            .count()
        )
        svc_eligible = (
            db.query(HumanOutcomeEvent)
            .filter(HumanOutcomeEvent.feedback_state == "VALIDATED")
            .count()
        )

        return CorpusCountsSummary(
            total_real_corpus=total_real_leads_count,
            human_reviewed_corpus=reviewed,
            fully_validated_corpus=validated,
            genuineness_training_eligible_corpus=gen_eligible,
            productivity_training_eligible_corpus=prod_eligible,
            service_opportunity_training_eligible_corpus=svc_eligible,
        )

    def export_candidate_dataset(
        self, db: Session, candidate_name: str, dataset_type: str, dataset_version: str = "v1.0"
    ) -> dict[str, Any]:
        events = (
            db.query(HumanOutcomeEvent)
            .filter(HumanOutcomeEvent.feedback_state == "VALIDATED")
            .all()
        )

        rows: list[dict[str, Any]] = []
        for evt in events:
            # Temporal Leakage Guard Check
            pred = evt.prediction_record
            if pred:
                if not (
                    pred.feature_snapshot_timestamp
                    <= pred.prediction_timestamp
                    <= evt.human_outcome_timestamp
                ):
                    raise TemporalLeakageError(
                        f"Leakage detected! Invalid timestamp order for lead {evt.canonical_lead_id}"
                    )

            if dataset_type == "GENUINENESS" and evt.genuineness_outcome not in (
                "GENUINE",
                "NOT_GENUINE",
            ):
                continue

            target: Any = None
            if dataset_type == "GENUINENESS":
                target = 1 if evt.genuineness_outcome == "GENUINE" else 0
            elif dataset_type == "PRODUCTIVITY":
                target = 1 if evt.productivity_outcome == "PRODUCTIVE" else 0
            elif dataset_type == "SERVICE_OPPORTUNITY":
                target = (
                    json.loads(evt.service_opportunity_flags)
                    if evt.service_opportunity_flags
                    else []
                )

            rows.append(
                {
                    "canonical_lead_id": evt.canonical_lead_id,
                    "prediction_id": evt.prediction_id,
                    "target": target,
                    "outcome_timestamp": evt.human_outcome_timestamp.isoformat(),
                }
            )

        artifact_path = EXPORTS_DIR / f"{candidate_name}_{dataset_version}.json"
        export_payload = {
            "candidate_name": candidate_name,
            "dataset_type": dataset_type,
            "dataset_version": dataset_version,
            "eligible_row_count": len(rows),
            "rows": rows,
        }

        with open(artifact_path, "w", encoding="utf-8") as f:
            json.dump(export_payload, f, indent=2)

        logger.info(
            f"[Corpus Exporter] Exported candidate dataset {candidate_name} with {len(rows)} eligible rows."
        )
        return export_payload
