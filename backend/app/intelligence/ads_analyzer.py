from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AdsOpportunityResult(BaseModel):
    opportunity_score: int = Field(
        ..., ge=0, le=100, description="PPC / Paid Ads agency sales opportunity score (0-100)"
    )
    is_running_meta_ads: bool = Field(default=False, description="Active Meta Ads campaign flag")
    is_running_google_ads: bool = Field(
        default=False, description="Active Google Ads campaign flag"
    )
    has_meta_pixel: bool = Field(default=False, description="Meta Pixel tracking installed flag")
    has_google_tag: bool = Field(
        default=False, description="Google Ads conversion tracking installed flag"
    )
    signals: list[str] = Field(
        default_factory=list, description="Detailed paid ads opportunity signals"
    )


class AdsOpportunityAnalyzer:
    META_PIXEL_PATTERNS: tuple[str, ...] = (
        "fbevents.js",
        "fbq('init'",
        'fbq("init"',
        "connect.facebook.net/en_us/fbevents.js",
    )
    GOOGLE_ADS_PATTERNS: tuple[str, ...] = (
        "google_conversion_id",
        "gtag('config', 'aw-",
        'gtag("config", "aw-',
        "google_ad_client",
    )

    def analyze(
        self,
        html_content: str | None,
        meta_provenance_data: dict[str, Any] | None = None,
        google_search_data: dict[str, Any] | None = None,
    ) -> AdsOpportunityResult:
        html_lower = (html_content or "").lower()

        has_meta_pixel = any(pat in html_lower for pat in self.META_PIXEL_PATTERNS)
        has_google_tag = any(pat in html_lower for pat in self.GOOGLE_ADS_PATTERNS)

        is_running_meta = False
        if meta_provenance_data:
            is_running_meta = bool(
                meta_provenance_data.get("is_running_ads")
                or meta_provenance_data.get("active_ad_count", 0) > 0
            )

        is_running_google = False
        if google_search_data:
            is_running_google = bool(google_search_data.get("is_running_google_ads"))

        signals: list[str] = []
        is_running_ads = is_running_meta or is_running_google

        if not is_running_ads and not has_meta_pixel and not has_google_tag:
            opportunity_score = 85
            signals.append(
                "No active advertising campaigns or tracking pixels detected. High PPC sales opportunity."
            )
        elif not is_running_ads and (has_meta_pixel or has_google_tag):
            opportunity_score = 75
            signals.append(
                "Tracking pixels installed but no active ad campaigns detected. Retargeting sales opportunity."
            )
        else:
            opportunity_score = 20
            signals.append("Business is actively running paid advertising campaigns.")

        return AdsOpportunityResult(
            opportunity_score=opportunity_score,
            is_running_meta_ads=is_running_meta,
            is_running_google_ads=is_running_google,
            has_meta_pixel=has_meta_pixel,
            has_google_tag=has_google_tag,
            signals=signals,
        )
