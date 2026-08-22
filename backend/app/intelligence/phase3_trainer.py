from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from backend.app.intelligence.catboost_lightgbm import CatBoostLightGBMScorer, MLEvaluationMetrics
from backend.app.intelligence.model_registry import ModelRegistry
from backend.app.intelligence.permutation_generator import PermutationDataGenerator

logger = logging.getLogger(__name__)


class Phase3TrainingReport(BaseModel):
    model_version: str
    phase_a_samples: int
    phase_b_samples: int
    phase_c_human_feedback_samples: int
    total_training_samples: int
    metrics: MLEvaluationMetrics
    status: str = Field(..., description="STAGING, PRODUCTION")


class Phase3AITrainer:
    """Executes 3-Phase AI Model Training with Scaled Permutations, Noise Injection, and Multi-Objective Evaluation."""

    def __init__(self, model_version: str = "v2.0_phase3_ensemble") -> None:
        self.model_version = model_version
        self.scorer = CatBoostLightGBMScorer(model_version=model_version)

    def execute_full_3phase_training(self, human_feedback_count: int = 0) -> Phase3TrainingReport:
        # Phase A: Synthetic Feature Permutations (10,000 samples)
        logger.info("[Phase A AI Training] Generating 10,000 synthetic feature permutations...")
        phase_a_data = PermutationDataGenerator.generate_phase_a_permutations(count=10000)

        # Phase B: Noise Injection & Missing Signal Robustness (30,000 samples)
        logger.info(
            "[Phase B AI Training] Injecting noise & missing signal edge-case permutations (30,000 samples)..."
        )
        phase_b_data = PermutationDataGenerator.generate_phase_b_noisy_samples(count=30000)

        # Combined Dataset for Phase C Evaluation (40,000+ samples)
        combined_dataset = phase_a_data + phase_b_data
        total_samples = len(combined_dataset) + human_feedback_count

        # Phase C: Multi-Objective Calibration & Evaluation
        logger.info(
            f"[Phase C AI Training] Evaluating CatBoost & LightGBM metrics on {total_samples} samples..."
        )
        metrics = self.scorer.train_and_evaluate(combined_dataset)

        metrics_dict = metrics.model_dump()
        ModelRegistry.register_version(
            version=self.model_version,
            metrics=metrics_dict,
            sample_count=total_samples,
        )

        return Phase3TrainingReport(
            model_version=self.model_version,
            phase_a_samples=len(phase_a_data),
            phase_b_samples=len(phase_b_data),
            phase_c_human_feedback_samples=human_feedback_count,
            total_training_samples=total_samples,
            metrics=metrics,
            status="STAGING",
        )
