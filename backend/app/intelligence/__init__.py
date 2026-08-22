from __future__ import annotations

from backend.app.intelligence.ads_analyzer import AdsOpportunityAnalyzer, AdsOpportunityResult
from backend.app.intelligence.catboost_lightgbm import (
    CatBoostLightGBMScorer,
    MLEvaluationMetrics,
)
from backend.app.intelligence.genuineness import GenuinenessAgent, GenuinenessDecision
from backend.app.intelligence.learning_agent import ActiveLearningItem, LearningAgent
from backend.app.intelligence.llm_explanation import LLMExplanationGenerator, LLMExplanationResponse
from backend.app.intelligence.ml_scorer import MLScorer
from backend.app.intelligence.model_registry import ModelRegistry, ModelVersionRecord
from backend.app.intelligence.permutation_generator import PermutationDataGenerator
from backend.app.intelligence.phase3_trainer import Phase3AITrainer, Phase3TrainingReport
from backend.app.intelligence.adaptive_discovery import AdaptiveDiscoveryEngine
from backend.app.intelligence.completeness import CompletenessChecker
from backend.app.intelligence.rule_engine import DeterministicRuleEngine
from backend.app.intelligence.source_confidence import SourceConfidenceSystem
from backend.app.intelligence.seo_analyzer import SEOOpportunityAnalyzer, SEOOpportunityResult
from backend.app.intelligence.smma_analyzer import SMMAOpportunityAnalyzer, SMMAOpportunityResult
from backend.app.intelligence.social_analyzer import SocialSignalAnalyzer, SocialSignalResult
from backend.app.intelligence.website_analyzer import (
    WebsiteOpportunityAnalyzer,
    WebsiteOpportunityResult,
)

__all__ = [
    "ActiveLearningItem",
    "AdsOpportunityAnalyzer",
    "AdsOpportunityResult",
    "CatBoostLightGBMScorer",
    "AdaptiveDiscoveryEngine",
    "DatasetCoverageReport",
    "CompletenessChecker",
    "DeterministicRuleEngine",
    "SourceConfidenceSystem",
    "GenuinenessAgent",
    "GenuinenessDecision",
    "LearningAgent",
    "LLMExplanationGenerator",
    "LLMExplanationResponse",
    "MLEvaluationMetrics",
    "MLScorer",
    "ModelRegistry",
    "ModelVersionRecord",
    "PermutationDataGenerator",
    "Phase3AITrainer",
    "Phase3TrainingReport",
    "SEOOpportunityAnalyzer",
    "SEOOpportunityResult",
    "SMMAOpportunityAnalyzer",
    "SMMAOpportunityResult",
    "SocialSignalAnalyzer",
    "SocialSignalResult",
    "WebsiteOpportunityAnalyzer",
    "WebsiteOpportunityResult",
]
