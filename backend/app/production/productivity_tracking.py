from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ProductivityStatus(str, Enum):
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    CONTACTED = "CONTACTED"
    OWNER_REACHED = "OWNER_REACHED"
    DECISION_MAKER_REACHED = "DECISION_MAKER_REACHED"
    PRODUCTIVE = "PRODUCTIVE"
    UNPRODUCTIVE = "UNPRODUCTIVE"
    UNKNOWN = "UNKNOWN"


@dataclass
class OutreachAttemptRecord:
    canonical_lead_id: str
    outreach_channel: str  # PHONE, EMAIL, LINKEDIN
    status: ProductivityStatus
    reason_code: str | None = None
    attempted_by: str = "sales_rep_1"
    timestamp: str = ""


class ProductivityOutcomeManager:
    """Manages sales outreach attempts and reconciles productivity outcomes while preserving GENUINENESS != PRODUCTIVITY separation."""

    def __init__(self) -> None:
        self.attempts: dict[str, OutreachAttemptRecord] = {}

    def record_outreach_attempt(
        self,
        canonical_lead_id: str,
        outreach_channel: str,
        status: ProductivityStatus,
        reason_code: str | None = None,
        attempted_by: str = "sales_rep_1",
    ) -> OutreachAttemptRecord:
        ts = datetime.datetime.now(datetime.UTC).isoformat()
        rec = OutreachAttemptRecord(
            canonical_lead_id=canonical_lead_id,
            outreach_channel=outreach_channel,
            status=status,
            reason_code=reason_code,
            attempted_by=attempted_by,
            timestamp=ts,
        )
        self.attempts[canonical_lead_id] = rec
        logger.info(
            f"[ProductivityOutcomeManager] Logged outreach for {canonical_lead_id}: {status.value}"
        )
        return rec

    def get_lead_status(self, canonical_lead_id: str) -> ProductivityStatus:
        rec = self.attempts.get(canonical_lead_id)
        return rec.status if rec else ProductivityStatus.NOT_ATTEMPTED

    def get_summary_accounting(self, total_batch_leads: int) -> dict[str, Any]:
        attempted = len(self.attempts)
        productive = sum(
            1 for r in self.attempts.values() if r.status == ProductivityStatus.PRODUCTIVE
        )
        unproductive = sum(
            1 for r in self.attempts.values() if r.status == ProductivityStatus.UNPRODUCTIVE
        )
        contacted = sum(
            1
            for r in self.attempts.values()
            if r.status
            in (
                ProductivityStatus.CONTACTED,
                ProductivityStatus.OWNER_REACHED,
                ProductivityStatus.DECISION_MAKER_REACHED,
            )
        )
        not_attempted = total_batch_leads - attempted

        return {
            "total_batch_leads": total_batch_leads,
            "outreach_attempted_count": attempted,
            "productive_count": productive,
            "unproductive_count": unproductive,
            "contacted_in_progress_count": contacted,
            "not_attempted_count": not_attempted,
            "dimension_separation": "GENUINENESS != PRODUCTIVITY strictly preserved",
        }
