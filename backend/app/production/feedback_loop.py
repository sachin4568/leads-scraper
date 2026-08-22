from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models_phase3 import HumanOutcomeEvent

logger = logging.getLogger(__name__)


@dataclass
class FeedbackQualityGate:
    min_evidence_length: int = 5
    require_reviewer_id: bool = True

    def validate_feedback(self, reviewer_id: str, evidence: str | None) -> bool:
        if self.require_reviewer_id and not reviewer_id.strip():
            return False
        if evidence and len(evidence.strip()) < self.min_evidence_length:
            return False
        return True


class TrainingCandidateQueue:
    """Collects human-validated outcome events for future model retraining candidates without automatic promotion."""

    def __init__(self) -> None:
        self.candidates: list[dict[str, Any]] = []

    def enqueue_candidate(
        self, canonical_lead_id: str, human_genuineness: str, evidence: str | None
    ) -> None:
        self.candidates.append(
            {
                "canonical_lead_id": canonical_lead_id,
                "human_genuineness": human_genuineness,
                "evidence": evidence,
                "enqueued_at": datetime.datetime.now(datetime.UTC).isoformat(),
            }
        )
        logger.info(
            f"[TrainingCandidateQueue] Enqueued lead {canonical_lead_id} ({human_genuineness}) for future retraining."
        )


class ProductionFeedbackCollector:
    """Logs human ground-truth feedback as immutable HumanOutcomeEvent without altering historical predictions."""

    def __init__(self) -> None:
        self.quality_gate = FeedbackQualityGate()
        self.candidate_queue = TrainingCandidateQueue()

    def record_human_outcome(
        self,
        db: Session,
        canonical_lead_id: str,
        reviewer_id: str,
        genuineness_outcome: str,
        evidence: str | None = None,
    ) -> HumanOutcomeEvent:
        if not self.quality_gate.validate_feedback(reviewer_id, evidence):
            raise ValueError(f"Invalid feedback submission by reviewer '{reviewer_id}'.")

        event = HumanOutcomeEvent(
            canonical_lead_id=canonical_lead_id,
            reviewer_id=reviewer_id,
            genuineness_outcome=genuineness_outcome,
            contactability_outcome="OWNER_CONTACT",
            productivity_outcome="NOT_ATTEMPTED",
            qualification_outcome="QUALIFIED",
            service_opportunity_flags='["WEBSITE"]',
            free_text_notes=evidence,
            evidence_reference=evidence,
            human_outcome_timestamp=datetime.datetime.now(datetime.UTC),
        )
        db.add(event)
        db.commit()

        self.candidate_queue.enqueue_candidate(canonical_lead_id, genuineness_outcome, evidence)
        logger.info(
            f"[ProductionFeedbackCollector] Recorded HumanOutcomeEvent for lead {canonical_lead_id}: {genuineness_outcome}"
        )
        return event
