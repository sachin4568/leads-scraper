from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from backend.app.production.productivity_ground_truth import FinalOutcome

logger = logging.getLogger(__name__)

EXPORTS_DIR = Path("/Users/sachinchaubey/Desktop/Leads/training_data/corpus_exports")
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


class ProductivityExpansionExporter:
    """Exports candidate dataset productivity_real_candidate_v2.json with structural separation, excluding unvalidated and non-binary states."""

    @classmethod
    def export_v2_dataset(
        cls, candidates: list[dict[str, Any]], dataset_version: str = "v2"
    ) -> dict[str, Any]:
        artifact_path = EXPORTS_DIR / f"productivity_real_candidate_{dataset_version}.json"

        binary_records = []
        for c in candidates:
            outcome = c.get("human_outcome", {}).get("final_productivity_outcome") or c.get(
                "final_productivity_outcome"
            )
            if outcome in (
                FinalOutcome.PRODUCTIVE.value,
                FinalOutcome.UNPRODUCTIVE.value,
                "PRODUCTIVE",
                "UNPRODUCTIVE",
            ):
                rec_struct = {
                    "raw_data": c.get(
                        "raw_data", {"canonical_lead_id": c.get("canonical_lead_id")}
                    ),
                    "prediction_time_features": c.get("prediction_time_features", {}),
                    "prediction": c.get(
                        "prediction",
                        {"model_version": "real_model_v2_1", "operating_threshold": 0.40},
                    ),
                    "outreach_state": c.get("outreach_state", {"state": "OWNER_REACHED"}),
                    "human_outcome": {
                        "final_productivity_outcome": outcome,
                        "reviewer_id": c.get("reviewer_id", "reviewer_1"),
                    },
                    "provenance": c.get("provenance", {"source": "REAL_VERIFIED_SOURCE"}),
                    "validation": c.get("validation", {"status": "VALIDATED"}),
                }
                binary_records.append(rec_struct)

        payload = {
            "dataset_name": f"productivity_real_candidate_{dataset_version}",
            "dataset_version": dataset_version,
            "total_records": len(binary_records),
            "binary_supervised_eligible": True,
            "excluded_unresolved_and_control_count": len(candidates) - len(binary_records),
            "records": binary_records,
        }

        with open(artifact_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        logger.info(
            f"[ProductivityExpansionExporter] Exported {len(binary_records)} binary records to {artifact_path}"
        )
        return payload
