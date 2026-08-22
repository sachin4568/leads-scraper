from __future__ import annotations

import datetime
import logging
import math
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class OutreachState(str, Enum):
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    CONTACTED = "CONTACTED"
    OWNER_REACHED = "OWNER_REACHED"
    DECISION_MAKER_REACHED = "DECISION_MAKER_REACHED"


class FinalOutcome(str, Enum):
    PRODUCTIVE = "PRODUCTIVE"
    UNPRODUCTIVE = "UNPRODUCTIVE"
    UNKNOWN = "UNKNOWN"
    NOT_RESOLVED = "NOT_RESOLVED"


@dataclass
class ProductivityGroundTruthRecord:
    canonical_lead_id: str
    is_control_cohort: bool
    outreach_state: OutreachState
    final_outcome: FinalOutcome
    reviewer_1_id: str
    reviewer_1_outcome: FinalOutcome
    reviewer_2_id: str | None = None
    reviewer_2_outcome: FinalOutcome | None = None
    evidence_notes: str | None = None
    timestamp: str = ""


@dataclass
class DoubleReviewAgreementMetrics:
    total_double_reviewed: int
    raw_agreements: int
    raw_agreement_pct: float
    cohens_kappa: float
    target_passed: bool
    interpretation: str


class ProductivityGroundTruthManager:
    """Manages behavioral sales outreach tracking, unambiguous productivity accounting, and double-review agreement validation."""

    def __init__(self) -> None:
        self.records: dict[str, ProductivityGroundTruthRecord] = {}

    def log_outreach_record(
        self,
        canonical_lead_id: str,
        is_control_cohort: bool,
        outreach_state: OutreachState,
        final_outcome: FinalOutcome,
        reviewer_1_id: str,
        reviewer_1_outcome: FinalOutcome,
        reviewer_2_id: str | None = None,
        reviewer_2_outcome: FinalOutcome | None = None,
        evidence_notes: str | None = None,
    ) -> ProductivityGroundTruthRecord:
        ts = datetime.datetime.now(datetime.UTC).isoformat()
        rec = ProductivityGroundTruthRecord(
            canonical_lead_id=canonical_lead_id,
            is_control_cohort=is_control_cohort,
            outreach_state=outreach_state,
            final_outcome=final_outcome,
            reviewer_1_id=reviewer_1_id,
            reviewer_1_outcome=reviewer_1_outcome,
            reviewer_2_id=reviewer_2_id,
            reviewer_2_outcome=reviewer_2_outcome,
            evidence_notes=evidence_notes,
            timestamp=ts,
        )
        self.records[canonical_lead_id] = rec
        return rec

    def compute_double_review_kappa(self) -> DoubleReviewAgreementMetrics:
        r1_list = []
        r2_list = []
        for r in self.records.values():
            if r.reviewer_2_outcome is not None:
                r1_list.append(r.reviewer_1_outcome.value)
                r2_list.append(r.reviewer_2_outcome.value)

        n = len(r1_list)
        if n == 0:
            return DoubleReviewAgreementMetrics(0, 0, 0.0, 0.0, False, "NO_DATA")

        categories = ["PRODUCTIVE", "UNPRODUCTIVE", "UNKNOWN", "NOT_RESOLVED"]
        conf_matrix = {c1: {c2: 0 for c2 in categories} for c1 in categories}

        agreements = 0
        for r1, r2 in zip(r1_list, r2_list, strict=False):
            if r1 in conf_matrix and r2 in conf_matrix[r1]:
                conf_matrix[r1][r2] += 1
            if r1 == r2:
                agreements += 1

        p_o = agreements / n
        p_e = 0.0
        for c in categories:
            r1_count = sum(conf_matrix[c][c2] for c2 in categories)
            r2_count = sum(conf_matrix[c1][c] for c1 in categories)
            p_e += (r1_count / n) * (r2_count / n)

        kappa = 1.0 if math.isclose(p_e, 1.0) else (p_o - p_e) / (1.0 - p_e)
        kappa = round(max(-1.0, min(1.0, kappa)), 4)
        raw_pct = round(p_o * 100.0, 2)
        passed = kappa >= 0.75

        return DoubleReviewAgreementMetrics(
            total_double_reviewed=n,
            raw_agreements=agreements,
            raw_agreement_pct=raw_pct,
            cohens_kappa=kappa,
            target_passed=passed,
            interpretation="SUBSTANTIAL" if kappa >= 0.75 else "POOR",
        )

    def get_cohort_accounting_summary(self, total_cohort_leads: int) -> dict[str, Any]:
        control_count = sum(1 for r in self.records.values() if r.is_control_cohort)
        outreach_count = sum(1 for r in self.records.values() if not r.is_control_cohort)

        productive = sum(
            1 for r in self.records.values() if r.final_outcome == FinalOutcome.PRODUCTIVE
        )
        unproductive = sum(
            1 for r in self.records.values() if r.final_outcome == FinalOutcome.UNPRODUCTIVE
        )
        not_resolved = sum(
            1
            for r in self.records.values()
            if r.final_outcome in (FinalOutcome.NOT_RESOLVED, FinalOutcome.UNKNOWN)
        )

        return {
            "total_cohort_leads": total_cohort_leads,
            "control_cohort_untouched_count": control_count,
            "outreach_cohort_attempted_count": outreach_count,
            "outcomes": {
                "productive_count": productive,
                "unproductive_count": unproductive,
                "not_resolved_count": not_resolved,
            },
            "unambiguous_accounting_invariant_verified": (
                control_count + outreach_count == total_cohort_leads
            ),
        }
