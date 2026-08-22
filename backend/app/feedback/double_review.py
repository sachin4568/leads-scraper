from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DoubleReviewAnnotation:
    canonical_lead_id: str
    reviewer_id: str
    genuineness_outcome: str  # GENUINE, NOT_GENUINE, UNCERTAIN
    reason_code: str | None = None
    evidence_reference: str | None = None
    annotation_timestamp: float = 0.0


@dataclass
class InterRaterAgreementReport:
    total_double_reviewed: int
    raw_agreement_count: int
    raw_agreement_pct: float
    disagreement_count: int
    unresolved_disagreements: int
    agreement_matrix: dict[str, int]
    cohens_kappa: float | None
    interpretation: str


class DoubleReviewManager:
    """Manages blind independent double reviews and computes Cohen's Kappa inter-rater agreement statistics."""

    def __init__(self) -> None:
        self.annotations_r1: dict[str, DoubleReviewAnnotation] = {}
        self.annotations_r2: dict[str, DoubleReviewAnnotation] = {}

    def submit_annotation(self, annotation: DoubleReviewAnnotation) -> None:
        if annotation.reviewer_id == "reviewer_1":
            self.annotations_r1[annotation.canonical_lead_id] = annotation
        elif annotation.reviewer_id == "reviewer_2":
            self.annotations_r2[annotation.canonical_lead_id] = annotation

    def calculate_inter_rater_agreement(self) -> InterRaterAgreementReport:
        overlapping_ids = set(self.annotations_r1.keys()).intersection(
            set(self.annotations_r2.keys())
        )
        total_overlap = len(overlapping_ids)

        if total_overlap == 0:
            return InterRaterAgreementReport(
                total_double_reviewed=0,
                raw_agreement_count=0,
                raw_agreement_pct=0.0,
                disagreement_count=0,
                unresolved_disagreements=0,
                agreement_matrix={},
                cohens_kappa=None,
                interpretation="INTER-RATER AGREEMENT INSUFFICIENT",
            )

        matrix = {
            "GENUINE/GENUINE": 0,
            "GENUINE/NOT_GENUINE": 0,
            "NOT_GENUINE/GENUINE": 0,
            "NOT_GENUINE/NOT_GENUINE": 0,
            "UNCERTAIN_COMBINATION": 0,
        }

        agree_count = 0
        disagree_count = 0

        for lead_id in overlapping_ids:
            r1 = self.annotations_r1[lead_id].genuineness_outcome
            r2 = self.annotations_r2[lead_id].genuineness_outcome

            key = f"{r1}/{r2}"
            if key in matrix:
                matrix[key] += 1
            else:
                matrix["UNCERTAIN_COMBINATION"] += 1

            if r1 == r2:
                agree_count += 1
            else:
                disagree_count += 1

        raw_pct = round(agree_count / total_overlap * 100.0, 2)

        # Cohen's Kappa Calculation
        # p_o = agree_count / total_overlap
        # Chance agreement calculation:
        r1_gen = sum(
            1
            for lead_id in overlapping_ids
            if self.annotations_r1[lead_id].genuineness_outcome == "GENUINE"
        )
        r2_gen = sum(
            1
            for lead_id in overlapping_ids
            if self.annotations_r2[lead_id].genuineness_outcome == "GENUINE"
        )

        p_r1_gen = r1_gen / total_overlap
        p_r2_gen = r2_gen / total_overlap
        p_r1_not = 1.0 - p_r1_gen
        p_r2_not = 1.0 - p_r2_gen

        p_e = (p_r1_gen * p_r2_gen) + (p_r1_not * p_r2_not)
        p_o = agree_count / total_overlap

        if p_e == 1.0:
            kappa = 1.0
        else:
            kappa = round((p_o - p_e) / (1.0 - p_e), 4)

        interp = "SUBSTANTIAL_AGREEMENT" if kappa >= 0.70 else "MODERATE_AGREEMENT"

        return InterRaterAgreementReport(
            total_double_reviewed=total_overlap,
            raw_agreement_count=agree_count,
            raw_agreement_pct=raw_pct,
            disagreement_count=disagree_count,
            unresolved_disagreements=disagree_count,
            agreement_matrix=matrix,
            cohens_kappa=kappa,
            interpretation=interp,
        )
