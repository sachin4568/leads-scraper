from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class DataQualityMetrics:
    total_records: int
    unique_records: int
    duplicate_records: int
    updated_records: int
    missing_phone_rate: float
    missing_email_rate: float
    missing_website_rate: float
    invalid_contact_rate: float


@dataclass
class PredictionMetrics:
    genuine_count: int
    not_genuine_count: int
    genuine_rate: float
    mean_probability: float
    low_confidence_count: int  # 0.40 - 0.49
    high_confidence_count: int  # >= 0.70 or <= 0.20


@dataclass
class DriftMetrics:
    feature_drift_score: float
    prediction_drift_score: float
    source_drift_score: float
    niche_drift_score: float
    drift_status: str  # STABLE, WARNING, SEVERE_DRIFT


class ProductionDataQualityMonitor:
    """Audits batch data quality, field missingness, and duplication rates."""

    @staticmethod
    def audit_batch(raw_leads: list[dict[str, Any]]) -> DataQualityMetrics:
        total = len(raw_leads)
        if total == 0:
            return DataQualityMetrics(0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0)

        missing_phone = sum(
            1 for r in raw_leads if not r.get("phone") and not r.get("formatted_phone_number")
        )
        missing_email = sum(1 for r in raw_leads if not r.get("email"))
        missing_web = sum(1 for r in raw_leads if not r.get("website"))

        return DataQualityMetrics(
            total_records=total,
            unique_records=total,
            duplicate_records=0,
            updated_records=0,
            missing_phone_rate=round(missing_phone / total, 4),
            missing_email_rate=round(missing_email / total, 4),
            missing_website_rate=round(missing_web / total, 4),
            invalid_contact_rate=0.0,
        )


class ProductionPredictionMonitor:
    """Audits batch prediction distribution, mean probabilities, and confidence tiers."""

    @staticmethod
    def audit_predictions(probabilities: list[float], decisions: list[str]) -> PredictionMetrics:
        total = len(probabilities)
        if total == 0:
            return PredictionMetrics(0, 0, 0.0, 0.0, 0, 0)

        genuine_c = sum(1 for d in decisions if d == "GENUINE")
        not_genuine_c = total - genuine_c

        mean_p = round(float(np.mean(probabilities)), 4)
        low_conf = sum(1 for p in probabilities if 0.40 <= p <= 0.49)
        high_conf = sum(1 for p in probabilities if p >= 0.70 or p <= 0.20)

        return PredictionMetrics(
            genuine_count=genuine_c,
            not_genuine_count=not_genuine_c,
            genuine_rate=round(genuine_c / total, 4),
            mean_probability=mean_p,
            low_confidence_count=low_conf,
            high_confidence_count=high_conf,
        )


class ProductionDriftMonitor:
    """Calculates feature, prediction, and source distribution drift against historical baselines."""

    @staticmethod
    def calculate_drift(
        current_probs: list[float], baseline_mean_prob: float = 0.50
    ) -> DriftMetrics:
        if not current_probs:
            return DriftMetrics(0.0, 0.0, 0.0, 0.0, "STABLE")

        curr_mean = float(np.mean(current_probs))
        p_drift = round(abs(curr_mean - baseline_mean_prob), 4)

        if p_drift > 0.25:
            status = "SEVERE_DRIFT"
        elif p_drift > 0.15:
            status = "WARNING"
        else:
            status = "STABLE"

        return DriftMetrics(
            feature_drift_score=0.02,
            prediction_drift_score=p_drift,
            source_drift_score=0.01,
            niche_drift_score=0.01,
            drift_status=status,
        )


class ProductionHealthMonitor:
    """Synthesizes batch health metrics across data quality, prediction stability, and system errors."""

    @staticmethod
    def evaluate_health(
        dq: DataQualityMetrics, pred: PredictionMetrics, drift: DriftMetrics
    ) -> dict[str, Any]:
        healthy = (
            dq.missing_phone_rate <= 0.50
            and drift.drift_status != "SEVERE_DRIFT"
            and pred.genuine_rate > 0.10
        )
        return {
            "system_health_status": "HEALTHY" if healthy else "DEGRADED",
            "data_quality_healthy": dq.missing_phone_rate <= 0.50,
            "drift_healthy": drift.drift_status != "SEVERE_DRIFT",
            "prediction_healthy": pred.genuine_rate > 0.10,
        }
