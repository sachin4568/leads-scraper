from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

REGISTRY_DIR = Path("/Users/sachinchaubey/Desktop/Leads/models/phase1_registry")
REGISTRY_DIR.mkdir(parents=True, exist_ok=True)


class Phase1ModelRecord(BaseModel):
    model_name: str
    model_version: str
    status: str = Field(
        default="EXPERIMENTAL", description="EXPERIMENTAL, STAGING, PRODUCTION, ARCHIVED"
    )
    dataset_version: str
    feature_version: str
    training_timestamp: str
    random_seed: int
    training_sample_count: int
    positive_count: int
    negative_count: int
    validation_metrics: dict[str, float]
    test_metrics: dict[str, float]
    selected_threshold: float
    artifact_path: str


class Phase1ModelRegistry:
    """Versioned Model Registry storing EXPERIMENTAL model artifacts and performance metadata."""

    def __init__(self) -> None:
        self.records: dict[str, Phase1ModelRecord] = {}

    def register_experimental_model(self, record: Phase1ModelRecord) -> Phase1ModelRecord:
        record_dict = record.model_dump()
        file_path = REGISTRY_DIR / f"{record.model_version}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(record_dict, f, indent=2)

        self.records[record.model_version] = record
        logger.info(
            f"[Phase 1 Model Registry] Saved EXPERIMENTAL model metadata version {record.model_version}"
        )
        return record

    def list_models(self) -> list[Phase1ModelRecord]:
        results: list[Phase1ModelRecord] = []
        for file in REGISTRY_DIR.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    results.append(Phase1ModelRecord(**data))
            except Exception as err:
                logger.warning(f"Error loading model registry file {file}: {err}")
        return results
