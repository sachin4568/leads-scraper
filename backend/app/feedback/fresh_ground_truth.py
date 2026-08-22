from __future__ import annotations

import datetime
import logging
import math
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FreshGroundTruthRecord:
    canonical_lead_id: str
    reviewer_1_id: str
    reviewer_1_decision: str  # GENUINE, NOT_GENUINE, UNCERTAIN
    reviewer_2_id: str | None = None
    reviewer_2_decision: str | None = None  # GENUINE, NOT_GENUINE, UNCERTAIN
    final_ground_truth: str = "UNCERTAIN"  # GENUINE, NOT_GENUINE, UNCERTAIN
    evidence_reference: str | None = None
    timestamp: str | None = None


@dataclass
class ReviewerAgreementMetrics:
    total_double_reviewed: int
    raw_agreements: int
    raw_disagreements: int
    raw_agreement_pct: float
    cohens_kappa: float
    interpretation: str


class ReviewerAgreementCalculator:
    """Computes inter-rater agreement metrics including Cohen's Kappa coefficient."""

    @staticmethod
    def calculate_cohens_kappa(
        r1_decisions: list[str], r2_decisions: list[str]
    ) -> ReviewerAgreementMetrics:
        n = len(r1_decisions)
        if n == 0:
            return ReviewerAgreementMetrics(0, 0, 0, 0.0, 0.0, "NO_DATA")

        categories = ["GENUINE", "NOT_GENUINE", "UNCERTAIN"]
        conf_matrix = {c1: {c2: 0 for c2 in categories} for c1 in categories}

        agreements = 0
        for r1, r2 in zip(r1_decisions, r2_decisions, strict=False):
            if r1 in conf_matrix and r2 in conf_matrix[r1]:
                conf_matrix[r1][r2] += 1
            if r1 == r2:
                agreements += 1

        p_o = agreements / n

        # Expected Chance Agreement p_e
        p_e = 0.0
        for c in categories:
            r1_count = sum(conf_matrix[c][c2] for c2 in categories)
            r2_count = sum(conf_matrix[c1][c] for c1 in categories)
            p_e += (r1_count / n) * (r2_count / n)

        if math.isclose(p_e, 1.0):
            kappa = 1.0
        else:
            kappa = (p_o - p_e) / (1.0 - p_e)

        kappa = round(max(-1.0, min(1.0, kappa)), 4)
        raw_pct = round(p_o * 100.0, 2)

        if kappa >= 0.81:
            interp = "ALMOST_PERFECT"
        elif kappa >= 0.61:
            interp = "SUBSTANTIAL"
        elif kappa >= 0.41:
            interp = "MODERATE"
        else:
            interp = "FAIR_OR_POOR"

        return ReviewerAgreementMetrics(
            total_double_reviewed=n,
            raw_agreements=agreements,
            raw_disagreements=n - agreements,
            raw_agreement_pct=raw_pct,
            cohens_kappa=kappa,
            interpretation=interp,
        )


class FreshGroundTruthManager:
    """Manages ground-truth logging and double-review agreement calculations for fresh leads."""

    def __init__(self) -> None:
        self.records: dict[str, FreshGroundTruthRecord] = {}

    def log_ground_truth(
        self,
        canonical_lead_id: str,
        reviewer_1_id: str,
        reviewer_1_decision: str,
        reviewer_2_id: str | None = None,
        reviewer_2_decision: str | None = None,
        evidence_reference: str | None = None,
    ) -> FreshGroundTruthRecord:
        ts = datetime.datetime.now(datetime.UTC).isoformat()

        if reviewer_2_decision:
            if reviewer_1_decision == reviewer_2_decision:
                final_gt = reviewer_1_decision
            else:
                final_gt = "UNCERTAIN"
        else:
            final_gt = reviewer_1_decision

        rec = FreshGroundTruthRecord(
            canonical_lead_id=canonical_lead_id,
            reviewer_1_id=reviewer_1_id,
            reviewer_1_decision=reviewer_1_decision,
            reviewer_2_id=reviewer_2_id,
            reviewer_2_decision=reviewer_2_decision,
            final_ground_truth=final_gt,
            evidence_reference=evidence_reference,
            timestamp=ts,
        )
        self.records[canonical_lead_id] = rec
        return rec

    def compute_agreement_metrics(self) -> ReviewerAgreementMetrics:
        r1_list = []
        r2_list = []
        for r in self.records.values():
            if r.reviewer_2_decision is not None:
                r1_list.append(r.reviewer_1_decision)
                r2_list.append(r.reviewer_2_decision)

        return ReviewerAgreementCalculator.calculate_cohens_kappa(r1_list, r2_list)
