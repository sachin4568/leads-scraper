from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy.orm import Session

from backend.app.models_phase2 import HumanOutcomeEventRecord

logger = logging.getLogger(__name__)


class ContactRole(str, Enum):
    OWNER = "OWNER"
    FOUNDER = "FOUNDER"
    CEO = "CEO"
    DIRECTOR = "DIRECTOR"
    DECISION_MAKER = "DECISION_MAKER"
    MARKETING_MANAGER = "MARKETING_MANAGER"
    OPERATIONS_MANAGER = "OPERATIONS_MANAGER"
    DEPARTMENT_CONTACT = "DEPARTMENT_CONTACT"
    FRONT_DESK = "FRONT_DESK"
    RECEPTION = "RECEPTION"
    GENERIC = "GENERIC"


CONTACT_PRIORITY_MAP: dict[ContactRole, int] = {
    ContactRole.OWNER: 1,
    ContactRole.FOUNDER: 1,
    ContactRole.CEO: 1,
    ContactRole.DIRECTOR: 2,
    ContactRole.DECISION_MAKER: 2,
    ContactRole.MARKETING_MANAGER: 3,
    ContactRole.OPERATIONS_MANAGER: 3,
    ContactRole.DEPARTMENT_CONTACT: 4,
    ContactRole.FRONT_DESK: 5,
    ContactRole.RECEPTION: 5,
    ContactRole.GENERIC: 7,
}


class BusinessMaturityCategory(str, Enum):
    MICRO_SOLO = "MICRO_SOLO"
    SMALL_BUSINESS = "SMALL_BUSINESS"
    STARTUP = "STARTUP"
    GROWING_SMB = "GROWING_SMB"
    MID_MARKET = "MID_MARKET"
    ENTERPRISE = "ENTERPRISE"
    MULTI_LOCATION_CHAIN = "MULTI_LOCATION_CHAIN"
    UNKNOWN = "UNKNOWN"


class WebsiteIntelligenceState(str, Enum):
    NO_WEBSITE = "NO_WEBSITE"
    WEBSITE_ACTIVE = "WEBSITE_ACTIVE"
    WEBSITE_UNREACHABLE = "WEBSITE_UNREACHABLE"
    WEBSITE_BROKEN = "WEBSITE_BROKEN"
    WEBSITE_REDIRECTING = "WEBSITE_REDIRECTING"
    WEBSITE_PARKED = "WEBSITE_PARKED"
    WEBSITE_EXPIRED = "WEBSITE_EXPIRED"
    WEBSITE_WEAK = "WEBSITE_WEAK"
    WEBSITE_STRONG = "WEBSITE_STRONG"
    UNKNOWN = "UNKNOWN"


@dataclass
class WebsiteAuditEvidence:
    """Objective website evidence storage."""

    state: WebsiteIntelligenceState = WebsiteIntelligenceState.UNKNOWN
    http_status: int | None = None
    ssl_valid: bool | None = None
    response_time_ms: float | None = None
    audit_timestamp: str = field(
        default_factory=lambda: datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    )


@dataclass
class NicheProfile:
    """Configurable data-driven niche profile."""

    niche_id: str
    display_name: str
    relevant_services: list[str]
    opportunity_signals: list[str]


class NicheProfileRegistry:
    """Extensible 15-niche profile registry."""

    def __init__(self) -> None:
        self.profiles: dict[str, NicheProfile] = {}
        self._load_default_15_niches()

    def _load_default_15_niches(self) -> None:
        niches = [
            (
                "dental_clinics",
                "Dental Clinics",
                ["Website Redesign", "SEO", "Google Ads"],
                ["missing_website", "low_reviews"],
            ),
            (
                "plumbing_contractors",
                "Plumbing Contractors",
                ["Local SEO", "PPC Ads"],
                ["no_ssl", "missing_phone"],
            ),
            (
                "hvac_services",
                "HVAC Services",
                ["Service Ads", "Website Upgrade"],
                ["expired_domain"],
            ),
            (
                "roofing_specialists",
                "Roofing Specialists",
                ["Leads Campaign", "SMMA"],
                ["broken_website"],
            ),
            (
                "restaurants_cafes",
                "Restaurants & Cafes",
                ["Instagram SMMA", "Google Maps SEO"],
                ["low_rating"],
            ),
            ("solar_installers", "Solar Installers", ["High Ticket PPC", "SEO"], ["missing_mx"]),
            ("ecommerce_brands", "E-commerce Brands", ["Meta Ads", "CRO"], ["slow_load"]),
            ("legal_services", "Legal Services", ["Search Ads", "SEO"], ["no_ssl"]),
            ("medical_clinics", "Medical Clinics", ["Local SEO", "Reputation"], ["low_reviews"]),
            (
                "automotive_services",
                "Automotive Services",
                ["Google Maps SEO", "PPC"],
                ["missing_website"],
            ),
            ("saas_companies", "SaaS Companies", ["Content Marketing", "PPC"], ["no_ssl"]),
            ("real_estate_agencies", "Real Estate Agencies", ["Meta Ads", "SMMA"], ["low_rating"]),
            ("fitness_gyms", "Fitness Gyms", ["SMMA", "Google Ads"], ["missing_phone"]),
            ("accounting_firms", "Accounting Firms", ["Local SEO", "Website Upgrade"], ["no_ssl"]),
            ("digital_agencies", "Digital Agencies", ["White Label SEO", "PPC"], ["slow_load"]),
        ]
        for nid, name, svcs, sigs in niches:
            self.profiles[nid] = NicheProfile(
                niche_id=nid, display_name=name, relevant_services=svcs, opportunity_signals=sigs
            )

    def get_profile(self, niche_id: str) -> NicheProfile | None:
        return self.profiles.get(niche_id.lower().replace(" ", "_"))


class HumanFeedbackManager:
    """Manages human feedback preservation without overwriting original ML predictions."""

    @staticmethod
    def record_feedback(
        db: Session,
        canonical_lead_id: str,
        original_prediction: str,
        original_probability: float,
        model_version: str,
        human_outcome: str,
        reason: str | None = None,
    ) -> HumanOutcomeEventRecord:
        record = HumanOutcomeEventRecord(
            canonical_lead_id=canonical_lead_id,
            original_prediction=original_prediction,
            original_probability=original_probability,
            original_model_version=model_version,
            human_outcome=human_outcome,
            reason=reason,
        )
        db.add(record)
        db.commit()
        logger.info(
            f"[Human Feedback] Recorded outcome '{human_outcome}' for lead {canonical_lead_id}"
        )
        return record
