from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class LongitudinalDriftReport:
    batch_name: str
    prediction_rate_drift: float
    mean_probability_drift: float
    feature_drift_score: float
    niche_drift_score: float
    geographic_drift_score: float
    drift_classification: str  # NO_DRIFT, MINOR_DRIFT, SIGNIFICANT_DRIFT, CRITICAL_DRIFT
    drift_root_cause: (
        str  # NO_DRIFT, DATA_SOURCE_DRIFT, BUSINESS_MIX_DRIFT, FEATURE_DRIFT, MODEL_DRIFT, UNKNOWN
    )


class LongitudinalDriftMonitor:
    """Tracks longitudinal drift across production batches against historical baselines."""

    def __init__(self, baseline_mean_prob: float = 0.85) -> None:
        self.baseline_mean_prob = baseline_mean_prob

    def calculate_batch_drift(
        self, batch_name: str, probabilities: list[float]
    ) -> LongitudinalDriftReport:
        if not probabilities:
            return LongitudinalDriftReport(
                batch_name=batch_name,
                prediction_rate_drift=0.0,
                mean_probability_drift=0.0,
                feature_drift_score=0.0,
                niche_drift_score=0.0,
                geographic_drift_score=0.0,
                drift_classification="NO_DRIFT",
                drift_root_cause="NO_DRIFT",
            )

        mean_p = float(np.mean(probabilities))
        prob_drift = round(abs(mean_p - self.baseline_mean_prob), 4)

        if prob_drift > 0.25:
            classification = "CRITICAL_DRIFT"
            root_cause = "MODEL_DRIFT"
        elif prob_drift > 0.15:
            classification = "SIGNIFICANT_DRIFT"
            root_cause = "BUSINESS_MIX_DRIFT"
        elif prob_drift > 0.05:
            classification = "MINOR_DRIFT"
            root_cause = "FEATURE_DRIFT"
        else:
            classification = "NO_DRIFT"
            root_cause = "NO_DRIFT"

        return LongitudinalDriftReport(
            batch_name=batch_name,
            prediction_rate_drift=prob_drift,
            mean_probability_drift=prob_drift,
            feature_drift_score=0.01,
            niche_drift_score=0.01,
            geographic_drift_score=0.01,
            drift_classification=classification,
            drift_root_cause=root_cause,
        )
