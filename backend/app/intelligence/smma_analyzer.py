from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from backend.app.intelligence.ads_analyzer import AdsOpportunityResult
from backend.app.intelligence.seo_analyzer import SEOOpportunityResult
from backend.app.intelligence.social_analyzer import SocialSignalResult
from backend.app.intelligence.website_analyzer import WebsiteOpportunityResult

logger = logging.getLogger(__name__)


class SMMAOpportunityResult(BaseModel):
    overall_smma_score: int = Field(
        ..., ge=0, le=100, description="Overall SMMA agency sales opportunity score (0-100)"
    )
    priority_rank: str = Field(..., description="Lead qualification priority: HIGH, MEDIUM, LOW")
    breakdown_scores: dict[str, int] = Field(
        ..., description="Individual opportunity score breakdown by agency service line"
    )
    key_opportunities: list[str] = Field(
        default_factory=list, description="Top strategic sales opportunity bullet points"
    )


class SMMAOpportunityAnalyzer:
    WEIGHT_WEBSITE: float = 0.25
    WEIGHT_SEO: float = 0.25
    WEIGHT_SOCIAL: float = 0.25
    WEIGHT_ADS: float = 0.25

    def analyze(
        self,
        website_res: WebsiteOpportunityResult,
        seo_res: SEOOpportunityResult,
        social_res: SocialSignalResult,
        ads_res: AdsOpportunityResult,
    ) -> SMMAOpportunityResult:
        breakdown = {
            "web_design": website_res.opportunity_score,
            "seo": seo_res.opportunity_score,
            "social_media": social_res.opportunity_score,
            "paid_ads": ads_res.opportunity_score,
        }

        weighted_sum = (
            (website_res.opportunity_score * self.WEIGHT_WEBSITE)
            + (seo_res.opportunity_score * self.WEIGHT_SEO)
            + (social_res.opportunity_score * self.WEIGHT_SOCIAL)
            + (ads_res.opportunity_score * self.WEIGHT_ADS)
        )

        overall_score = min(100, max(0, round(weighted_sum)))

        if overall_score >= 75:
            priority = "HIGH"
        elif overall_score >= 45:
            priority = "MEDIUM"
        else:
            priority = "LOW"

        opportunities: list[str] = []
        opportunities.extend(website_res.signals)
        opportunities.extend(seo_res.signals)
        opportunities.extend(social_res.signals)
        opportunities.extend(ads_res.signals)

        return SMMAOpportunityResult(
            overall_smma_score=overall_score,
            priority_rank=priority,
            breakdown_scores=breakdown,
            key_opportunities=opportunities,
        )
