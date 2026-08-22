from __future__ import annotations

import logging
import re

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SEOOpportunityResult(BaseModel):
    opportunity_score: int = Field(
        ..., ge=0, le=100, description="SEO agency sales opportunity score (0-100)"
    )
    missing_title: bool = Field(default=False, description="Missing or inadequate title tag flag")
    missing_meta_description: bool = Field(
        default=False, description="Missing meta description tag flag"
    )
    missing_h1: bool = Field(default=False, description="Missing H1 heading tag flag")
    missing_schema_org: bool = Field(
        default=False, description="Missing Schema.org structured data flag"
    )
    signals: list[str] = Field(default_factory=list, description="Detailed SEO opportunity signals")


class SEOOpportunityAnalyzer:
    def analyze(self, html_content: str | None) -> SEOOpportunityResult:
        if not html_content or not html_content.strip():
            return SEOOpportunityResult(
                opportunity_score=85,
                signals=["HTML content unavailable for SEO analysis."],
            )

        html_lower = html_content.lower()
        signals: list[str] = []
        score = 10
        missing_title = False
        missing_meta_description = False
        missing_h1 = False
        missing_schema_org = False

        # Title tag check
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html_lower, re.DOTALL)
        if not title_match or len(title_match.group(1).strip()) < 10:
            missing_title = True
            score += 25
            signals.append("Missing or inadequate HTML title tag (< 10 chars).")

        # Meta description check
        if 'name="description"' not in html_lower and "name='description'" not in html_lower:
            missing_meta_description = True
            score += 25
            signals.append("Missing meta description tag for search engine snippets.")

        # H1 heading check
        if "<h1" not in html_lower:
            missing_h1 = True
            score += 25
            signals.append("Missing main H1 heading tag for page hierarchy.")

        # Schema.org structured data check
        has_schema = (
            "application/ld+json" in html_lower
            or "schema.org" in html_lower
            or "itemtype=" in html_lower
        )
        if not has_schema:
            missing_schema_org = True
            score += 15
            signals.append("Lacks Schema.org structured data markup.")

        opportunity_score = min(100, max(0, score))

        return SEOOpportunityResult(
            opportunity_score=opportunity_score,
            missing_title=missing_title,
            missing_meta_description=missing_meta_description,
            missing_h1=missing_h1,
            missing_schema_org=missing_schema_org,
            signals=signals,
        )
