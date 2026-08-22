from __future__ import annotations

import logging
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.models import Lead, EvidenceRecord

logger = logging.getLogger(__name__)


class CompletenessChecker:
    def __init__(self, required_fields: list[str] | None = None, min_confidence: int = 60) -> None:
        """Configurable completeness checker for Lead records."""
        self.required_fields = required_fields or ["business_name", "website", "phone"]
        self.min_confidence = min_confidence

    def check_completeness(self, lead: Lead, db_session: Session) -> bool:
        """Check if all required fields are present and verified with a high confidence score."""
        for field in self.required_fields:
            val = getattr(lead, field, None)
            if not val or not str(val).strip():
                logger.info(f"[Completeness] Lead {lead.id} is missing required field '{field}'")
                return False

        for field in self.required_fields:
            if field in ("website", "phone", "email"):
                ev = db_session.scalar(
                    select(EvidenceRecord).where(
                        EvidenceRecord.lead_id == lead.id,
                        EvidenceRecord.field_name == field,
                        EvidenceRecord.status == "VERIFIED",
                        EvidenceRecord.confidence_score >= self.min_confidence
                    )
                )
                if not ev:
                    logger.info(f"[Completeness] Lead {lead.id} lacks high-confidence evidence for '{field}'")
                    return False

        logger.info(f"[Completeness] Lead {lead.id} is fully complete and verified.")
        return True
