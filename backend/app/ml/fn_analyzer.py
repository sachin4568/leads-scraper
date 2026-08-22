from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

EXPORTS_DIR = Path("/Users/sachinchaubey/Desktop/Leads/training_data/corpus_exports")
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class WilsonScoreInterval:
    estimate: float
    lower_bound: float
    upper_bound: float
    successes: int
    trials: int
    confidence_level: float = 0.95


@dataclass
class FalseNegativeProbabilityDistribution:
    min_prob: float
    max_prob: float
    mean_prob: float
    median_prob: float
    near_threshold_count: int  # 0.40 - 0.49
    mid_low_confidence_count: int  # 0.30 - 0.39
    very_low_confidence_count: int  # < 0.30


@dataclass
class FalseNegativeRecord:
    canonical_lead_id: str
    model_version: str
    feature_version: str
    model_probability: float
    model_decision: str
    human_genuineness: str
    niche: str
    geography: str
    business_maturity: str
    website_state: str
    contactability: str
    phone_state: str
    email_state: str
    social_state: str
    sampling_source: str
    candidate_reason: str
    validated_reason: str
    attribution_type: str  # FEATURE_PIPELINE_ERROR or MODEL_BEHAVIOR_ERROR
    reviewer_1_decision: str
    reviewer_2_decision: str
    reviewers_agree: bool


class FalseNegativeAnalyzer:
    """Diagnostic analyzer for false-negative prediction root causes, feature comparison, slice FN rates, and Wilson confidence intervals."""

    @staticmethod
    def calculate_wilson_confidence_interval(
        successes: int, trials: int, confidence: float = 0.95
    ) -> WilsonScoreInterval:
        if trials == 0:
            return WilsonScoreInterval(0.0, 0.0, 0.0, 0, 0, confidence)

        z = 1.95996  # 95% confidence z-score
        p_hat = successes / trials

        denominator = 1 + (z**2 / trials)
        center = (p_hat + (z**2 / (2 * trials))) / denominator
        spread = (
            z * math.sqrt((p_hat * (1 - p_hat) / trials) + (z**2 / (4 * trials**2))) / denominator
        )

        lower = round(max(0.0, center - spread), 4)
        upper = round(min(1.0, center + spread), 4)
        estimate = round(p_hat, 4)

        return WilsonScoreInterval(
            estimate=estimate,
            lower_bound=lower,
            upper_bound=upper,
            successes=successes,
            trials=trials,
            confidence_level=confidence,
        )

    @staticmethod
    def analyze_probability_distribution(
        probabilities: list[float],
    ) -> FalseNegativeProbabilityDistribution:
        if not probabilities:
            return FalseNegativeProbabilityDistribution(0.0, 0.0, 0.0, 0.0, 0, 0, 0)

        sorted_probs = sorted(probabilities)
        min_p = round(float(sorted_probs[0]), 4)
        max_p = round(float(sorted_probs[-1]), 4)
        mean_p = round(float(sum(sorted_probs) / len(sorted_probs)), 4)
        med_p = round(float(sorted_probs[len(sorted_probs) // 2]), 4)

        near_thresh = sum(1 for p in sorted_probs if 0.40 <= p <= 0.49)
        mid_low = sum(1 for p in sorted_probs if 0.30 <= p < 0.40)
        very_low = sum(1 for p in sorted_probs if p < 0.30)

        return FalseNegativeProbabilityDistribution(
            min_prob=min_p,
            max_prob=max_p,
            mean_prob=mean_p,
            median_prob=med_p,
            near_threshold_count=near_thresh,
            mid_low_confidence_count=mid_low,
            very_low_confidence_count=very_low,
        )

    @classmethod
    def export_false_negative_dataset(
        cls, records: list[FalseNegativeRecord], dataset_version: str = "v1"
    ) -> dict[str, Any]:
        artifact_path = EXPORTS_DIR / f"real_model_v2_phase8_false_negatives_{dataset_version}.json"
        rows = [r.__dict__ for r in records]

        payload = {
            "dataset_name": f"real_model_v2_phase8_false_negatives_{dataset_version}",
            "total_false_negatives": len(rows),
            "records": rows,
        }

        with open(artifact_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        logger.info(f"[FN Analyzer] Exported {len(rows)} false negative records to {artifact_path}")
        return payload
