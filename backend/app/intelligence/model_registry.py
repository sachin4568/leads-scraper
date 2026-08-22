from __future__ import annotations

import logging

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ModelVersionRecord(BaseModel):
    version: str
    status: str = Field(..., description="PRODUCTION, STAGING, REJECTED, ARCHIVED")
    metrics: dict[str, float]
    training_sample_count: int
    created_at_timestamp: float


class ModelRegistry:
    """Model governance registry managing model evaluation, staging, and controlled promotion."""

    _versions: dict[str, ModelVersionRecord] = {
        "v1.0": ModelVersionRecord(
            version="v1.0",
            status="PRODUCTION",
            metrics={"precision": 0.85, "recall": 0.82, "f1_score": 0.83, "roc_auc": 0.88},
            training_sample_count=100,
            created_at_timestamp=1700000000.0,
        )
    }
    _active_production_version: str = "v1.0"

    @classmethod
    def register_version(
        self, version: str, metrics: dict[str, float], sample_count: int
    ) -> ModelVersionRecord:
        record = ModelVersionRecord(
            version=version,
            status="STAGING",
            metrics=metrics,
            training_sample_count=sample_count,
            created_at_timestamp=1700000100.0,
        )
        self._versions[version] = record
        logger.info(f"[Model Registry] Registered candidate model version {version} in STAGING")
        return record

    @classmethod
    def list_versions(self) -> list[ModelVersionRecord]:
        return list(self._versions.values())

    @classmethod
    def get_active_production_version(self) -> str:
        return self._active_production_version

    @classmethod
    def promote_to_production(self, version: str) -> ModelVersionRecord:
        if version not in self._versions:
            raise ValueError(f"Model version {version} not found in registry.")

        # Demote previous production version
        if self._active_production_version in self._versions:
            prev = self._versions[self._active_production_version]
            self._versions[self._active_production_version] = ModelVersionRecord(
                version=prev.version,
                status="ARCHIVED",
                metrics=prev.metrics,
                training_sample_count=prev.training_sample_count,
                created_at_timestamp=prev.created_at_timestamp,
            )

        target = self._versions[version]
        promoted = ModelVersionRecord(
            version=target.version,
            status="PRODUCTION",
            metrics=target.metrics,
            training_sample_count=target.training_sample_count,
            created_at_timestamp=target.created_at_timestamp,
        )
        self._versions[version] = promoted
        self._active_production_version = version
        logger.info(f"[Model Registry] Promoted model version {version} to PRODUCTION!")
        return promoted
