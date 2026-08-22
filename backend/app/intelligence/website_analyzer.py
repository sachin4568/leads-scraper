from __future__ import annotations

import logging

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class WebsiteOpportunityResult(BaseModel):
    has_website: bool = Field(..., description="Website presence indicator")
    opportunity_score: int = Field(
        ..., ge=0, le=100, description="Web design agency opportunity score (0-100)"
    )
    missing_ssl: bool = Field(default=False, description="Missing SSL security certificate flag")
    missing_mobile_viewport: bool = Field(
        default=False, description="Missing mobile viewport optimization flag"
    )
    missing_analytics: bool = Field(
        default=False, description="Missing analytics tracking tags flag"
    )
    signals: list[str] = Field(
        default_factory=list, description="Detailed web design opportunity signals"
    )


class WebsiteOpportunityAnalyzer:
    ANALYTICS_KEYWORDS: tuple[str, ...] = (
        "gtag",
        "google-analytics",
        "googletagmanager",
        "fbevents.js",
        "facebook-pixel",
        "clarity.ms",
        "hotjar",
    )

    def analyze(
        self, website_url: str | None, html_content: str | None = None
    ) -> WebsiteOpportunityResult:
        if not website_url or not website_url.strip():
            return WebsiteOpportunityResult(
                has_website=False,
                opportunity_score=95,
                signals=["No website found. High-value web development opportunity."],
            )

        clean_url = website_url.strip().lower()
        signals: list[str] = []
        base_score = 10
        missing_ssl = False
        missing_mobile_viewport = False
        missing_analytics = False

        # SSL Check
        if clean_url.startswith("http://"):
            missing_ssl = True
            base_score += 25
            signals.append("Website lacks SSL certificate security (HTTP instead of HTTPS).")

        if html_content:
            html_lower = html_content.lower()

            # Mobile Viewport Check
            if 'name="viewport"' not in html_lower and "name='viewport'" not in html_lower:
                missing_mobile_viewport = True
                base_score += 30
                signals.append("Website lacks mobile viewport optimization tag.")

            # Analytics Tags Check
            has_analytics = any(kw in html_lower for kw in self.ANALYTICS_KEYWORDS)
            if not has_analytics:
                missing_analytics = True
                base_score += 25
                signals.append(
                    "Website lacks analytics tracking pixels (Google Analytics / Meta Pixel)."
                )
        else:
            # When HTML is unavailable, assume potential optimization gaps
            signals.append("Website HTML content unverified.")

        opportunity_score = min(100, max(0, base_score))

        return WebsiteOpportunityResult(
            has_website=True,
            opportunity_score=opportunity_score,
            missing_ssl=missing_ssl,
            missing_mobile_viewport=missing_mobile_viewport,
            missing_analytics=missing_analytics,
            signals=signals,
        )
