from __future__ import annotations

import logging
import re

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SocialSignalResult(BaseModel):
    opportunity_score: int = Field(
        ..., ge=0, le=100, description="Social media agency sales opportunity score (0-100)"
    )
    detected_profiles: dict[str, str] = Field(
        default_factory=dict, description="Map of platform to detected profile URL"
    )
    missing_facebook: bool = Field(default=False, description="Missing Facebook profile flag")
    missing_instagram: bool = Field(default=False, description="Missing Instagram profile flag")
    missing_linkedin: bool = Field(default=False, description="Missing LinkedIn profile flag")
    missing_x: bool = Field(default=False, description="Missing X/Twitter profile flag")
    signals: list[str] = Field(
        default_factory=list, description="Detailed social media opportunity signals"
    )


class SocialSignalAnalyzer:
    PLATFORM_PATTERNS: dict[str, str] = {
        "facebook": r"https?://(?:www\.)?facebook\.com/[A-Za-z0-9_.-]+",
        "instagram": r"https?://(?:www\.)?instagram\.com/[A-Za-z0-9_.-]+",
        "linkedin": r"https?://(?:www\.)?linkedin\.com/(?:company|in)/[A-Za-z0-9_.-]+",
        "x": r"https?://(?:www\.)?(?:twitter|x)\.com/[A-Za-z0-9_.-]+",
        "youtube": r"https?://(?:www\.)?youtube\.com/(?:c/|channel/|user/|@)?[A-Za-z0-9_.-]+",
    }

    def analyze(
        self, html_content: str | None, raw_social_links: list[str] | None = None
    ) -> SocialSignalResult:
        combined_text = (html_content or "") + " " + " ".join(raw_social_links or [])
        detected: dict[str, str] = {}

        for platform, pattern in self.PLATFORM_PATTERNS.items():
            match = re.search(pattern, combined_text, re.IGNORECASE)
            if match:
                detected[platform] = match.group(0)

        signals: list[str] = []
        score = 10

        missing_facebook = "facebook" not in detected
        missing_instagram = "instagram" not in detected
        missing_linkedin = "linkedin" not in detected
        missing_x = "x" not in detected

        if not detected:
            return SocialSignalResult(
                opportunity_score=90,
                detected_profiles={},
                missing_facebook=True,
                missing_instagram=True,
                missing_linkedin=True,
                missing_x=True,
                signals=["No social media profiles detected across major platforms."],
            )

        if missing_facebook:
            score += 20
            signals.append("Lacks Facebook business profile.")
        if missing_instagram:
            score += 20
            signals.append("Lacks Instagram profile for visual marketing.")
        if missing_linkedin:
            score += 15
            signals.append("Lacks LinkedIn company page.")
        if missing_x:
            score += 15
            signals.append("Lacks X/Twitter presence.")

        opportunity_score = min(100, max(0, score))

        return SocialSignalResult(
            opportunity_score=opportunity_score,
            detected_profiles=detected,
            missing_facebook=missing_facebook,
            missing_instagram=missing_instagram,
            missing_linkedin=missing_linkedin,
            missing_x=missing_x,
            signals=signals,
        )
