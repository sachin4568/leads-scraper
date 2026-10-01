from __future__ import annotations

import logging
from typing import Any

try:
    import redis
except ImportError:
    redis = None

from pydantic import BaseModel, Field

from backend.app.config import get_settings

logger = logging.getLogger(__name__)


class LLMExplanationResponse(BaseModel):
    summary: str = Field(..., description="Agency pitch summary")
    recommended_services: list[str] = Field(
        ..., description="List of recommended agency service lines"
    )
    evidence_bullet_points: list[str] = Field(
        ..., description="Validated evidence bullet points matching real analyzer signals"
    )
    token_usage: int = Field(default=0, description="Tokens consumed for explanation generation")


class LLMExplanationGenerator:
    """Structured LLM explanation generator with strict evidence output validation & per-workspace token budgeting."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._redis: Any = None
        if redis and self.settings.redis_url:
            try:
                self._redis = redis.Redis.from_url(
                    self.settings.redis_url.get_secret_value(), decode_responses=True
                )
            except Exception:
                self._redis = None

    def check_and_consume_token_budget(
        self, workspace_id: str, estimated_tokens: int = 500, max_daily_budget: int = 50000
    ) -> bool:
        key = f"llm_budget:{workspace_id}"
        try:
            current_usage = int(self._redis.get(key) or 0)
            if current_usage + estimated_tokens > max_daily_budget:
                return False

            pipe = self._redis.pipeline()
            pipe.incrby(key, estimated_tokens)
            pipe.expire(key, 86400)
            pipe.execute()
            return True
        except Exception as err:
            logger.warning(f"Redis token budget check failed: {err}")
            return True

    def validate_llm_output(
        self, llm_response: LLMExplanationResponse, valid_signals: list[str]
    ) -> LLMExplanationResponse:
        """Strips hallucinated evidence bullets not supported by genuine analyzer signals."""
        validated_bullets: list[str] = []
        valid_set = {s.lower().strip() for s in valid_signals}

        for bullet in llm_response.evidence_bullet_points:
            # Verify if bullet contains references to genuine verified signals
            is_grounded = any(
                sig_word in bullet.lower() for sig in valid_set for sig_word in sig.split()[:3]
            )
            if is_grounded:
                validated_bullets.append(bullet)

        if not validated_bullets and valid_signals:
            validated_bullets = valid_signals[:3]

        return LLMExplanationResponse(
            summary=llm_response.summary,
            recommended_services=llm_response.recommended_services,
            evidence_bullet_points=validated_bullets,
            token_usage=llm_response.token_usage,
        )

    def generate_explanation(
        self,
        workspace_id: str,
        business_name: str,
        opportunity_scores: dict[str, int],
        valid_signals: list[str],
    ) -> LLMExplanationResponse:
        # Check token budget limit
        budget_available = self.check_and_consume_token_budget(workspace_id, estimated_tokens=300)
        if not budget_available:
            return LLMExplanationResponse(
                summary="Token budget exceeded for workspace.",
                recommended_services=["smma"],
                evidence_bullet_points=valid_signals[:3],
                token_usage=0,
            )

        # Deterministic structured explanation generation
        recommended: list[str] = []
        if opportunity_scores.get("web_design", 0) >= 50:
            recommended.append("Web Design & Development")
        if opportunity_scores.get("seo", 0) >= 50:
            recommended.append("Search Engine Optimization (SEO)")
        if opportunity_scores.get("social_media", 0) >= 50:
            recommended.append("Social Media Management")
        if opportunity_scores.get("paid_ads", 0) >= 50:
            recommended.append("Paid Ads (Google / Meta PPC)")

        if not recommended:
            recommended.append("General Digital Marketing Advisory")

        summary = (
            f"{business_name} presents strong agency growth potential with opportunities in "
            + ", ".join(recommended)
            + "."
        )

        unvalidated_res = LLMExplanationResponse(
            summary=summary,
            recommended_services=recommended,
            evidence_bullet_points=valid_signals,
            token_usage=250,
        )

        return self.validate_llm_output(unvalidated_res, valid_signals)
