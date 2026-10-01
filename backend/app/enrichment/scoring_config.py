"""
Centralized Scoring Configuration for Phase 6 Service Opportunity Engine.
All weights, priority thresholds, and signal parameters are defined here.
"""

SERVICES = [
    "website_dev",
    "website_seo",
    "social_media_management",
    "social_media_marketing"
]

PRIORITY_THRESHOLDS = {
    "HIGH": {"min_opp": 70, "min_conf": 60},
    "MEDIUM": {"min_opp": 45, "min_conf": 50},
    "LOW": {"max_opp": 44, "min_conf": 30},
    "UNKNOWN": {"max_conf": 29}
}

def derive_priority(opportunity_score: int, confidence_score: int) -> str:
    """
    Derives Priority ('HIGH', 'MEDIUM', 'LOW', 'UNKNOWN') from opportunity and confidence scores.
    """
    if confidence_score < 30:
        return "UNKNOWN"
    if opportunity_score >= 70 and confidence_score >= 60:
        return "HIGH"
    if opportunity_score >= 45 and confidence_score >= 50:
        return "MEDIUM"
    if opportunity_score < 45 or confidence_score < 50:
        return "LOW"
    return "UNKNOWN"
