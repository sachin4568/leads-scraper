from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

EXPORTS_DIR = Path("/Users/sachinchaubey/Desktop/Leads/training_data/corpus_exports")
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ProductivityCandidateRecord:
    canonical_lead_id: str
    prediction_time_features: dict[str, Any]
    model_prediction: dict[str, Any]
    future_outreach_outcome: dict[str, Any]
    human_outcome_label: str
    dataset_version: str = "v1"


class TemporalLeakageError(Exception):
    """Raised when future outreach variables leak into prediction-time feature vectors."""

    pass


class ProductivityDatasetExporter:
    """Exports candidate dataset productivity_real_candidate_v1 with strict prediction-time feature isolation."""

    @staticmethod
    def audit_leakage(features: dict[str, Any]) -> bool:
        forbidden_keys = {
            "outreach_state",
            "contacted",
            "owner_reached",
            "decision_maker_reached",
            "productive",
            "unproductive",
            "successful_calls",
            "outreach_channel",
        }
        leaked = set(features.keys()).intersection(forbidden_keys)
        if leaked:
            raise TemporalLeakageError(
                f"Temporal leakage detected! Features contain future outreach variables: {leaked}"
            )
        return True

    @classmethod
    def export_productivity_dataset(
        cls, records: list[ProductivityCandidateRecord], dataset_version: str = "v1"
    ) -> dict[str, Any]:
        artifact_path = EXPORTS_DIR / f"productivity_real_candidate_{dataset_version}.json"

        rows = []
        for r in records:
            cls.audit_leakage(r.prediction_time_features)
            rows.append(r.__dict__)

        payload = {
            "dataset_name": f"productivity_real_candidate_{dataset_version}",
            "total_records": len(rows),
            "leakage_audit_passed": True,
            "records": rows,
        }

        with open(artifact_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        logger.info(
            f"[ProductivityDatasetExporter] Exported {len(rows)} leakage-free records to {artifact_path}"
        )
        return payload
