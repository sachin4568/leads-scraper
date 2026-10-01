from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class OpportunityCategory(str, Enum):
    VERY_HIGH = "VERY_HIGH"  # Score >= 80
    HIGH = "HIGH"            # Score 65 - 79
    MEDIUM = "MEDIUM"        # Score 45 - 64
    LOW = "LOW"              # Score 25 - 44
    MINIMAL = "MINIMAL"      # Score < 25


@dataclass
class ServiceOpportunityBreakdown:
    service_name: str
    opportunity_score: float
    eligible: bool
    reasons: list[str] = field(default_factory=list)
    confidence: float = 0.85


@dataclass
class LeadIntelligenceReport:
    overall_opportunity_score: int
    opportunity_category: OpportunityCategory
    confidence_score: float
    contactability_score: int
    website_opportunity_score: int
    seo_opportunity_score: int
    digital_presence_gap_score: int
    top_reasons: list[str] = field(default_factory=list)
    service_opportunities: dict[str, ServiceOpportunityBreakdown] = field(default_factory=dict)
    has_conflict: bool = False
    conflict_details: dict[str, Any] = field(default_factory=dict)
    genuineness_score: float = 0.85
    evidence_summary: dict[str, Any] = field(default_factory=dict)


class LeadIntelligenceEngine:
    """Deterministic, explainable, ₹0 sales opportunity and intelligence scoring engine."""

    # Transparent Weights for Overall Opportunity Score
    WEIGHT_WEBSITE_OPP: float = 0.30
    WEIGHT_SEO_OPP: float = 0.25
    WEIGHT_DIGITAL_GAP: float = 0.20
    WEIGHT_CONTACTABILITY: float = 0.25

    @classmethod
    def calculate_contactability(
        cls,
        phone: str | None = None,
        email: str | None = None,
        whatsapp_links: list[str] | None = None,
        social_profiles: dict[str, str] | None = None,
        has_contact_page: bool = False,
    ) -> tuple[int, list[str]]:
        """Calculates contactability score (0-100) and produces human-readable reasons."""
        score = 0
        reasons: list[str] = []

        if phone and str(phone).strip():
            score += 35
            reasons.append("Verified direct phone number available (+35)")

        if email and str(email).strip():
            score += 30
            reasons.append("Direct email address available (+30)")

        if whatsapp_links and len(whatsapp_links) > 0:
            score += 20
            reasons.append("Direct WhatsApp chat channel detected (+20)")

        if has_contact_page:
            score += 10
            reasons.append("Dedicated contact page available (+10)")

        if social_profiles and len(social_profiles) > 0:
            score += 10
            platforms = ", ".join(social_profiles.keys())
            reasons.append(f"Direct messaging reachable on social profiles ({platforms}) (+10)")

        final_score = min(100, score)
        return final_score, reasons

    @classmethod
    def calculate_website_opportunity(
        cls,
        website: str | None = None,
        is_reachable: bool = True,
        is_https: bool = True,
        seo_score: int = 100,
        has_schema: bool = True,
        has_contact_path: bool = True,
    ) -> tuple[int, list[str]]:
        """Calculates website redesign / creation sales opportunity score (0-100)."""
        reasons: list[str] = []

        if not has_contact_path:
            return 0, ["No contact path available to pitch web development"]

        if not website or not str(website).strip():
            reasons.append("No website detected: Maximum web development sales opportunity (95)")
            return 95, reasons

        if not is_reachable:
            reasons.append("Website is unreachable or down: High redesign/rescue opportunity (90)")
            return 90, reasons

        score = 0
        if not is_https:
            score += 25
            reasons.append("Website lacks HTTPS/SSL security encryption (+25)")

        if seo_score < 70:
            score += 25
            reasons.append(f"Low SEO technical score ({seo_score}/100): High web optimization opportunity (+25)")
        elif seo_score < 85:
            score += 15
            reasons.append(f"Moderate SEO technical score ({seo_score}/100) (+15)")

        if not has_schema:
            score += 20
            reasons.append("Missing Schema.org LocalBusiness structured data (+20)")

        final_score = min(100, max(15, score))
        if final_score <= 25:
            reasons.append("Strong existing website health: Low website development opportunity")

        return final_score, reasons

    @classmethod
    def calculate_seo_opportunity(
        cls,
        seo_evidence: dict[str, Any] | None = None,
        has_website: bool = True,
        has_contact_path: bool = True,
    ) -> tuple[int, list[str]]:
        """Calculates SEO sales opportunity score (0-100)."""
        if not has_contact_path:
            return 0, ["No contact path available to pitch SEO services"]

        if not has_website:
            return 0, ["No website exists to optimize SEO (Pitch Website Development first)"]

        if not seo_evidence:
            return 60, ["Initial SEO audit required: Website lacks comprehensive metadata (60)"]

        score = 0
        reasons: list[str] = []

        title = seo_evidence.get("title")
        meta_desc = seo_evidence.get("meta_description")
        canonical = seo_evidence.get("canonical_url")
        h1_tags = seo_evidence.get("h1_tags") or []
        og_title = seo_evidence.get("og_title")

        if not title or len(str(title).strip()) < 10:
            score += 25
            reasons.append("Missing or weak HTML page title tag (+25)")

        if not meta_desc or len(str(meta_desc).strip()) < 20:
            score += 25
            reasons.append("Missing meta description snippet (+25)")

        if not h1_tags or len(h1_tags) == 0:
            score += 20
            reasons.append("Missing primary H1 heading tag (+20)")
        elif len(h1_tags) > 1:
            score += 10
            reasons.append("Multiple competing H1 heading tags detected (+10)")

        if not canonical:
            score += 15
            reasons.append("Missing canonical URL tag (+15)")

        if not og_title:
            score += 15
            reasons.append("Missing OpenGraph social preview tags (+15)")

        final_score = min(100, max(15, score))
        return final_score, reasons

    @classmethod
    def calculate_digital_presence_gap(
        cls,
        social_profiles: dict[str, str] | None = None,
        has_contact_path: bool = True,
    ) -> tuple[int, list[str]]:
        """Calculates digital presence & social media agency sales gap (0-100)."""
        if not has_contact_path:
            return 0, ["No contact path available to pitch social media management"]

        profiles = social_profiles or {}
        score = 0
        reasons: list[str] = []

        if "instagram" not in profiles:
            score += 25
            reasons.append("Lacks Instagram business profile for visual conversion (+25)")
        else:
            reasons.append("Active Instagram profile present")

        if "facebook" not in profiles:
            score += 25
            reasons.append("Lacks Facebook business page (+25)")
        else:
            reasons.append("Active Facebook page present")

        if "linkedin" not in profiles:
            score += 20
            reasons.append("Lacks LinkedIn company presence (+20)")

        if "x" not in profiles and "twitter" not in profiles:
            score += 15
            reasons.append("Lacks X/Twitter presence (+15)")

        if "youtube" not in profiles:
            score += 15
            reasons.append("Lacks YouTube video marketing presence (+15)")

        final_score = min(100, score)
        return final_score, reasons

    @classmethod
    def evaluate_lead(
        cls,
        business_name: str,
        website: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        category: str | None = None,
        genuineness_score: float = 0.85,
        website_health: dict[str, Any] | None = None,
        contacts_evidence: dict[str, Any] | None = None,
        seo_evidence: dict[str, Any] | None = None,
        social_evidence: dict[str, Any] | None = None,
        technologies_evidence: list[str] | None = None,
        conflicts_evidence: dict[str, Any] | None = None,
    ) -> LeadIntelligenceReport:
        """Evaluates complete multi-dimensional sales intelligence and outputs an explainable report."""
        top_reasons: list[str] = []

        # 1. Contactability
        wh_links = (contacts_evidence or {}).get("whatsapp_links", [])
        soc_map = (social_evidence or {}).get("profiles", {})
        contact_score, contact_reasons = cls.calculate_contactability(
            phone=phone,
            email=email,
            whatsapp_links=wh_links,
            social_profiles=soc_map,
            has_contact_page=bool((contacts_evidence or {}).get("addresses")),
        )
        has_any_contact = contact_score > 0 or bool(phone or email or website or soc_map or wh_links)

        # 2. Website Opportunity
        is_reach = (website_health or {}).get("is_reachable", True) if website else False
        is_sec = (website_health or {}).get("is_https", True) if website else False
        seo_sc = (seo_evidence or {}).get("seo_score", 100) if seo_evidence else (100 if website else 0)
        has_sch = bool((seo_evidence or {}).get("schema_types"))
        web_opp_score, web_opp_reasons = cls.calculate_website_opportunity(
            website=website,
            is_reachable=is_reach,
            is_https=is_sec,
            seo_score=seo_sc,
            has_schema=has_sch,
            has_contact_path=has_any_contact,
        )

        # 3. SEO Opportunity
        seo_opp_score, seo_opp_reasons = cls.calculate_seo_opportunity(
            seo_evidence=seo_evidence,
            has_website=bool(website),
            has_contact_path=has_any_contact,
        )

        # 4. Digital Presence Gap
        digital_gap_score, digital_reasons = cls.calculate_digital_presence_gap(
            social_profiles=soc_map,
            has_contact_path=has_any_contact,
        )

        # 5. Composite Opportunity Score (Weighted & Actionability Gated)
        if not has_any_contact or contact_score == 0:
            final_opp_score = 10
            category_enum = OpportunityCategory.MINIMAL
            top_reasons.append("Uncontactable candidate: Lacks actionable contact paths")
        else:
            raw_opp = (
                (web_opp_score * cls.WEIGHT_WEBSITE_OPP)
                + (seo_opp_score * cls.WEIGHT_SEO_OPP)
                + (digital_gap_score * cls.WEIGHT_DIGITAL_GAP)
                + (contact_score * cls.WEIGHT_CONTACTABILITY)
            )
            final_opp_score = min(100, max(10, int(round(raw_opp))))

            # 6. Quality Tiers with Strict Actionability and Verification Confidence Bounds
            if final_opp_score >= 80 and contact_score >= 40 and genuineness_score >= 0.75:
                category_enum = OpportunityCategory.VERY_HIGH
            elif final_opp_score >= 65 and contact_score >= 30 and genuineness_score >= 0.65:
                category_enum = OpportunityCategory.HIGH
            elif final_opp_score >= 45 and contact_score >= 20 and genuineness_score >= 0.50:
                category_enum = OpportunityCategory.MEDIUM
            elif final_opp_score >= 25:
                category_enum = OpportunityCategory.LOW
            else:
                category_enum = OpportunityCategory.MINIMAL

            # Explicit verification cap enforcement: qualification cannot exceed validation confidence
            if genuineness_score < 0.50:
                final_opp_score = min(final_opp_score, 35)
                category_enum = OpportunityCategory.LOW if final_opp_score >= 25 else OpportunityCategory.MINIMAL
                top_reasons.append(f"Unverified candidate confidence ({int(genuineness_score*100)}%): Opportunity capped to {category_enum.value}")
            elif genuineness_score < 0.65 and category_enum in (OpportunityCategory.VERY_HIGH, OpportunityCategory.HIGH):
                final_opp_score = min(final_opp_score, 60)
                category_enum = OpportunityCategory.MEDIUM
                top_reasons.append(f"Moderate verification confidence ({int(genuineness_score*100)}%): Opportunity tier bounded to MEDIUM")

        # 7. Aggregate Top Explanatory Reasons
        top_reasons.extend(web_opp_reasons[:2])
        top_reasons.extend(contact_reasons[:2])
        top_reasons.extend(seo_opp_reasons[:1])
        top_reasons.extend(digital_reasons[:1])

        # 8. Service Opportunities
        services: dict[str, ServiceOpportunityBreakdown] = {}

        # Website Development
        web_dev_score = web_opp_score
        services["WEBSITE_DEVELOPMENT"] = ServiceOpportunityBreakdown(
            service_name="WEBSITE_DEVELOPMENT",
            opportunity_score=web_dev_score,
            eligible=web_dev_score >= 50,
            reasons=web_opp_reasons,
            confidence=0.90 if not website else 0.80,
        )

        # SEO Optimization
        services["SEO"] = ServiceOpportunityBreakdown(
            service_name="SEO",
            opportunity_score=seo_opp_score,
            eligible=seo_opp_score >= 45 and bool(website),
            reasons=seo_opp_reasons,
            confidence=0.85,
        )

        # Social Media Marketing (SMMA)
        services["SMMA"] = ServiceOpportunityBreakdown(
            service_name="SMMA",
            opportunity_score=digital_gap_score,
            eligible=digital_gap_score >= 45,
            reasons=digital_reasons,
            confidence=0.85,
        )

        # 9. Conflict Handling
        has_conf = bool(conflicts_evidence)
        confidence_val = genuineness_score
        if has_conf:
            confidence_val = max(0.40, confidence_val - 0.15)
            top_reasons.append("DATA_CONFLICT detected between provider tags and website evidence (Confidence reduced)")

        return LeadIntelligenceReport(
            overall_opportunity_score=final_opp_score,
            opportunity_category=category_enum,
            confidence_score=round(confidence_val, 2),
            contactability_score=contact_score,
            website_opportunity_score=web_opp_score,
            seo_opportunity_score=seo_opp_score,
            digital_presence_gap_score=digital_gap_score,
            top_reasons=top_reasons,
            service_opportunities=services,
            has_conflict=has_conf,
            conflict_details=conflicts_evidence or {},
            genuineness_score=genuineness_score,
            evidence_summary={
                "technologies": technologies_evidence or [],
                "social_profiles": soc_map,
                "whatsapp_links": wh_links,
            },
        )
