from __future__ import annotations

import datetime
import logging
import math
from dataclasses import dataclass
from typing import Any

from backend.app.production.productivity_ground_truth import FinalOutcome

logger = logging.getLogger(__name__)


@dataclass
class FreshDoubleReviewResult:
    total_reviewed: int
    raw_agreements: int
    raw_agreement_pct: float
    cohens_kappa: float
    target_passed: bool


class FreshProductivityGroundTruthManager:
    """Manages ground-truth logging for 300 fresh validation records and 150-record double-review agreement."""

    def __init__(self) -> None:
        self.fresh_outcomes: dict[str, dict[str, Any]] = {}

    def log_fresh_outcome(
        self,
        canonical_lead_id: str,
        reviewer_1_id: str,
        reviewer_1_outcome: FinalOutcome,
        reviewer_2_id: str | None = None,
        reviewer_2_outcome: FinalOutcome | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        rec = {
            "canonical_lead_id": canonical_lead_id,
            "reviewer_1_id": reviewer_1_id,
            "reviewer_1_outcome": reviewer_1_outcome.value,
            "reviewer_2_id": reviewer_2_id,
            "reviewer_2_outcome": reviewer_2_outcome.value if reviewer_2_outcome else None,
            "final_outcome": reviewer_1_outcome.value,
            "notes": notes,
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        }
        self.fresh_outcomes[canonical_lead_id] = rec
        return rec

    def compute_double_review_kappa(self) -> FreshDoubleReviewResult:
        r1_list = []
        r2_list = []
        for r in self.fresh_outcomes.values():
            if r["reviewer_2_outcome"] is not None:
                r1_list.append(r["reviewer_1_outcome"])
                r2_list.append(r["reviewer_2_outcome"])

        n = len(r1_list)
        if n == 0:
            return FreshDoubleReviewResult(0, 0, 0.0, 0.0, False)

        categories = ["PRODUCTIVE", "UNPRODUCTIVE", "NOT_RESOLVED"]
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
            r1_c = sum(conf_matrix[c][c2] for c2 in categories)
            r2_c = sum(conf_matrix[c1][c] for c1 in categories)
            p_e += (r1_c / n) * (r2_c / n)

        kappa = 1.0 if math.isclose(p_e, 1.0) else (p_o - p_e) / (1.0 - p_e)
        kappa = round(max(-1.0, min(1.0, kappa)), 4)
        raw_pct = round(p_o * 100.0, 2)
        passed = kappa >= 0.75

        return FreshDoubleReviewResult(
            total_reviewed=n,
            raw_agreements=agreements,
            raw_agreement_pct=raw_pct,
            cohens_kappa=kappa,
            target_passed=passed,
        )
