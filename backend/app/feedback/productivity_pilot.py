from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ProductivityPilotRecord:
    canonical_lead_id: str
    contact_attempted: bool
    contact_reached: bool
    decision_maker_reached: bool
    productivity_outcome: str  # PRODUCTIVE, UNPRODUCTIVE, NOT_ATTEMPTED
    reason_code: str | None
    timestamp: str


class ProductivityPilotEngine:
    """Manages controlled sales outreach pilot events and logs real productivity outcomes without altering genuineness labels."""

    def __init__(self) -> None:
        self.records: dict[str, ProductivityPilotRecord] = {}

    def log_outreach_event(
        self,
        canonical_lead_id: str,
        contact_attempted: bool,
        contact_reached: bool,
        decision_maker_reached: bool,
        productivity_outcome: str,
        reason_code: str | None = None,
    ) -> ProductivityPilotRecord:
        ts = datetime.datetime.now(datetime.UTC).isoformat()
        rec = ProductivityPilotRecord(
            canonical_lead_id=canonical_lead_id,
            contact_attempted=contact_attempted,
            contact_reached=contact_reached,
            decision_maker_reached=decision_maker_reached,
            productivity_outcome=productivity_outcome,
            reason_code=reason_code,
            timestamp=ts,
        )
        self.records[canonical_lead_id] = rec
        logger.info(
            f"[ProductivityPilotEngine] Logged outreach for {canonical_lead_id}: {productivity_outcome}"
        )
        return rec

    def get_summary_metrics(self, total_leads_count: int) -> dict[str, Any]:
        attempted = sum(1 for r in self.records.values() if r.contact_attempted)
        reached = sum(1 for r in self.records.values() if r.contact_reached)
        productive = sum(1 for r in self.records.values() if r.productivity_outcome == "PRODUCTIVE")
        unproductive = sum(
            1 for r in self.records.values() if r.productivity_outcome == "UNPRODUCTIVE"
        )
        not_attempted = total_leads_count - attempted

        return {
            "total_leads_in_batch": total_leads_count,
            "outreach_attempted_count": attempted,
            "contact_reached_count": reached,
            "productive_count": productive,
            "unproductive_count": unproductive,
            "not_attempted_count": not_attempted,
            "conversion_rate_pct": round(productive / attempted * 100.0, 2)
            if attempted > 0
            else 0.0,
        }
