from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.app.ml.staging_engine import StagingModelEngine
from backend.app.models_phase3 import PredictionHistoryRecord

logger = logging.getLogger(__name__)


class ProductionConfigurationError(Exception):
    """Raised when the production model configuration deviates from the frozen specification."""

    pass


@dataclass
class FrozenModelConfig:
    model_name: str = "real_model_v2_1"
    model_version: str = "real_model_v2_1"
    feature_version: str = "v1.0_allowlist"
    ensemble_alpha: float = 0.10
    operating_threshold: float = 0.40
    inference_mode: str = "READ_ONLY"


class FrozenModelGuard:
    """Validates frozen model parameters before executing production inferences."""

    def __init__(self, config: FrozenModelConfig | None = None) -> None:
        self.config = config or FrozenModelConfig()

    def validate_configuration(self, model_version: str, alpha: float, threshold: float) -> bool:
        if model_version != self.config.model_version:
            raise ProductionConfigurationError(
                f"Model version mismatch! Expected '{self.config.model_version}', got '{model_version}'."
            )
        if not abs(alpha - self.config.ensemble_alpha) < 1e-5:
            raise ProductionConfigurationError(
                f"Ensemble alpha mismatch! Expected {self.config.ensemble_alpha}, got {alpha}."
            )
        if not abs(threshold - self.config.operating_threshold) < 1e-5:
            raise ProductionConfigurationError(
                f"Operating threshold mismatch! Expected {self.config.operating_threshold}, got {threshold}."
            )
        return True


class PredictionAuditLogger:
    """Logs append-only immutable prediction history records into persistent storage."""

    @staticmethod
    def log_prediction(
        db: Session,
        canonical_lead_id: str,
        model_name: str,
        model_version: str,
        feature_version: str,
        probability: float,
        decision: str,
        feature_snapshot_timestamp: str,
        source_batch_id: str | None = None,
    ) -> PredictionHistoryRecord:
        ts = datetime.datetime.now(datetime.UTC)
        pred_rec = PredictionHistoryRecord(
            canonical_lead_id=canonical_lead_id,
            model_name=model_name,
            model_version=model_version,
            feature_version=feature_version,
            predicted_probability=probability,
            predicted_decision=decision,
            operating_threshold=0.40,
            feature_snapshot_timestamp=ts,
            prediction_timestamp=ts,
        )
        db.add(pred_rec)
        db.commit()
        return pred_rec


class ProductionInferenceEngine:
    """Production inference engine enforcing frozen configuration validation and audit logging."""

    def __init__(
        self,
        model_version: str = "real_model_v2_1",
        alpha: float = 0.10,
        threshold: float = 0.40,
    ) -> None:
        self.guard = FrozenModelGuard()
        self.guard.validate_configuration(model_version, alpha, threshold)
        self.model_version = model_version
        self.alpha = alpha
        self.threshold = threshold
        self.staging_engine = StagingModelEngine(alpha=alpha, threshold=threshold)

    def predict_and_audit(
        self,
        db: Session,
        canonical_lead_id: str,
        feature_vector: list[float],
        source_batch_id: str | None = None,
    ) -> tuple[float, str, PredictionHistoryRecord]:
        self.guard.validate_configuration(self.model_version, self.alpha, self.threshold)
        pred_out = self.staging_engine.predict_lead(canonical_lead_id, feature_vector)

        ts = datetime.datetime.now(datetime.UTC).isoformat()
        audit_rec = PredictionAuditLogger.log_prediction(
            db=db,
            canonical_lead_id=canonical_lead_id,
            model_name=pred_out.model_name,
            model_version=self.model_version,
            feature_version=pred_out.feature_version,
            probability=pred_out.predicted_probability,
            decision=pred_out.predicted_decision,
            feature_snapshot_timestamp=ts,
            source_batch_id=source_batch_id,
        )

        return pred_out.predicted_probability, pred_out.predicted_decision, audit_rec
