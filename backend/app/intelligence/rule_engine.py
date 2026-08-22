from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from backend.app.intelligence.ads_analyzer import AdsOpportunityAnalyzer
from backend.app.intelligence.seo_analyzer import SEOOpportunityAnalyzer
from backend.app.intelligence.smma_analyzer import SMMAOpportunityAnalyzer
from backend.app.intelligence.social_analyzer import SocialSignalAnalyzer
from backend.app.intelligence.website_analyzer import (
    WebsiteOpportunityAnalyzer,
)
from backend.app.models import Lead, ServiceScore

logger = logging.getLogger(__name__)


class DeterministicRuleEngine:
    def __init__(self) -> None:
        self.web_analyzer = WebsiteOpportunityAnalyzer()
        self.seo_analyzer = SEOOpportunityAnalyzer()
        self.social_analyzer = SocialSignalAnalyzer()
        self.ads_analyzer = AdsOpportunityAnalyzer()
        self.smma_analyzer = SMMAOpportunityAnalyzer()

    def qualify_lead(
        self,
        db: Session,
        lead: Lead,
        html_content: str | None = None,
        meta_provenance_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        web_res = self.web_analyzer.analyze(lead.website, html_content)
        seo_res = self.seo_analyzer.analyze(html_content)
        social_res = self.social_analyzer.analyze(html_content)
        ads_res = self.ads_analyzer.analyze(html_content, meta_provenance_data)
        smma_res = self.smma_analyzer.analyze(web_res, seo_res, social_res, ads_res)

        # Save service score record
        score_record = ServiceScore(
            workspace_id=lead.workspace_id,
            lead_id=lead.id,
            service_type="smma",
            score=smma_res.overall_smma_score,
            priority=smma_res.priority_rank,
            breakdown={
                "web_design": web_res.opportunity_score,
                "seo": seo_res.opportunity_score,
                "social_media": social_res.opportunity_score,
                "paid_ads": ads_res.opportunity_score,
                "key_opportunities": smma_res.key_opportunities,
            },
        )
        db.add(score_record)
        db.commit()

        return {
            "lead_id": str(lead.id),
            "overall_smma_score": smma_res.overall_smma_score,
            "priority_rank": smma_res.priority_rank,
            "breakdown_scores": smma_res.breakdown_scores,
            "key_opportunities": smma_res.key_opportunities,
        }
