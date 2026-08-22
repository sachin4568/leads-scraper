from __future__ import annotations

import logging
from enum import Enum

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class GenuinenessOutcome(str, Enum):
    GENUINE = "GENUINE"
    NOT_GENUINE = "NOT_GENUINE"
    UNCERTAIN = "UNCERTAIN"


class ContactabilityOutcome(str, Enum):
    OWNER_CONTACT = "OWNER_CONTACT"
    DECISION_MAKER_CONTACT = "DECISION_MAKER_CONTACT"
    MANAGER_CONTACT = "MANAGER_CONTACT"
    RECEPTION_CONTACT = "RECEPTION_CONTACT"
    GENERIC_CONTACT = "GENERIC_CONTACT"
    PHONE_ONLY = "PHONE_ONLY"
    EMAIL_ONLY = "EMAIL_ONLY"
    PHONE_AND_EMAIL = "PHONE_AND_EMAIL"
    NO_VERIFIED_CONTACT = "NO_VERIFIED_CONTACT"
    UNKNOWN = "UNKNOWN"


class ProductivityOutcome(str, Enum):
    PRODUCTIVE = "PRODUCTIVE"
    UNPRODUCTIVE = "UNPRODUCTIVE"
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    UNKNOWN = "UNKNOWN"


class QualificationOutcome(str, Enum):
    QUALIFIED = "QUALIFIED"
    NOT_QUALIFIED = "NOT_QUALIFIED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    DUPLICATE = "DUPLICATE"
    WRONG_NICHE = "WRONG_NICHE"
    BAD_CONTACT = "BAD_CONTACT"
    WRONG_SERVICE_MATCH = "WRONG_SERVICE_MATCH"
    DO_NOT_PITCH = "DO_NOT_PITCH"


class ServiceOpportunityFlag(str, Enum):
    WEBSITE = "WEBSITE"
    SEO = "SEO"
    SMMA = "SMMA"
    ADS = "ADS"
    MULTIPLE_SERVICES = "MULTIPLE_SERVICES"
    NO_CLEAR_OPPORTUNITY = "NO_CLEAR_OPPORTUNITY"
    UNKNOWN = "UNKNOWN"


class WebsiteReviewState(str, Enum):
    NO_WEBSITE = "NO_WEBSITE"
    ACTIVE_GOOD = "ACTIVE_GOOD"
    ACTIVE_NEEDS_IMPROVEMENT = "ACTIVE_NEEDS_IMPROVEMENT"
    OUTDATED = "OUTDATED"
    BROKEN = "BROKEN"
    UNREACHABLE = "UNREACHABLE"
    PARKED = "PARKED"
    EXPIRED = "EXPIRED"
    REDIRECTING = "REDIRECTING"
    UNKNOWN = "UNKNOWN"


class FeedbackState(str, Enum):
    UNREVIEWED = "UNREVIEWED"
    REVIEWED = "REVIEWED"
    VALIDATED = "VALIDATED"
    REJECTED_FEEDBACK = "REJECTED_FEEDBACK"
    READY_FOR_TRAINING = "READY_FOR_TRAINING"
    USED_IN_DATASET_VERSION = "USED_IN_DATASET_VERSION"


class HumanOutcomeEventInput(BaseModel):
    canonical_lead_id: str
    prediction_id: str | None = None
    reviewer_id: str = "system_reviewer"

    genuineness_outcome: GenuinenessOutcome
    contactability_outcome: ContactabilityOutcome
    productivity_outcome: ProductivityOutcome
    qualification_outcome: QualificationOutcome
    service_opportunity_flags: list[ServiceOpportunityFlag] = Field(
        default_factory=lambda: [ServiceOpportunityFlag.UNKNOWN]
    )
    website_review_state: WebsiteReviewState = WebsiteReviewState.UNKNOWN

    reason_code: str | None = None
    free_text_notes: str | None = None
    evidence_reference: str | None = None


class FeedbackQualityValidator:
    """Enforces strict validation rules, multi-label checking, and non-contradiction guards."""

    @staticmethod
    def validate_feedback_input(
        feedback: HumanOutcomeEventInput,
    ) -> tuple[bool, str, FeedbackState]:
        # 1. NOT_GENUINE requires reason or evidence
        if feedback.genuineness_outcome == GenuinenessOutcome.NOT_GENUINE:
            if not feedback.reason_code and not feedback.evidence_reference:
                return (
                    False,
                    "NOT_GENUINE outcome requires a valid reason_code or evidence_reference.",
                    FeedbackState.REJECTED_FEEDBACK,
                )

        # 2. PRODUCTIVE separation check: GENUINE + UNPRODUCTIVE is valid, NOT_GENUINE + PRODUCTIVE is invalid
        if (
            feedback.genuineness_outcome == GenuinenessOutcome.NOT_GENUINE
            and feedback.productivity_outcome == ProductivityOutcome.PRODUCTIVE
        ):
            return (
                False,
                "Invalid feedback: NOT_GENUINE leads cannot be marked as PRODUCTIVE.",
                FeedbackState.REJECTED_FEEDBACK,
            )

        # 3. Multi-label Service Opportunity validation
        if not feedback.service_opportunity_flags:
            return (
                False,
                "Service opportunity flags list cannot be empty.",
                FeedbackState.REJECTED_FEEDBACK,
            )

        # 4. Success -> Mark as VALIDATED
        return True, "Feedback validation successful.", FeedbackState.VALIDATED
