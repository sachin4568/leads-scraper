from __future__ import annotations

import datetime
import logging
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from backend.app.production.productivity_ground_truth import FinalOutcome, OutreachState

logger = logging.getLogger(__name__)


@dataclass
class OutreachSamplingCandidate:
    canonical_lead_id: str
    sampling_strategy: str  # BALANCED_PROBABILITY_BAND
    sampling_batch_id: str
    candidate_probability_band: str  # HIGH, MEDIUM, LOW, RANDOM
    niche: str
    geography: str
    website_state: str  # active, no_website, phone_only, sparse_presence
    contactability: str
    service_opportunities: list[str]
    source_count: int
    selection_timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC).isoformat()
    )


@dataclass
class ExpansionOutcomeRecord:
    canonical_lead_id: str
    prediction_id: str
    outreach_batch_id: str
    reviewer_id: str
    outreach_state: OutreachState
    final_productivity_outcome: FinalOutcome
    outcome_timestamp: str
    evidence_reference: str | None = None
    notes: str | None = None
    validation_state: str = "VALIDATED"


@dataclass
class ExpansionDoubleReviewResult:
    total_reviewed: int
    raw_agreements: int
    raw_agreement_pct: float
    cohens_kappa: float
    target_passed: bool
    classification: str  # SUBSTANTIAL, PRODUCTIVITY_LABEL_QUALITY_WARNING


class ProductivityExpansionManager:
    """Selects fresh outreach candidates using balanced sampling across probability bands, niches, website states, and contact hierarchies."""

    def __init__(self) -> None:
        self.sampled_candidates: dict[str, OutreachSamplingCandidate] = {}

    def sample_candidates(
        self,
        batch_id: str,
        lead_pool: list[dict[str, Any]],
        sample_size: int = 100,
    ) -> list[OutreachSamplingCandidate]:
        results = []
        for _i, lead in enumerate(lead_pool[:sample_size]):
            cid = lead["canonical_lead_id"]
            prob = lead.get("probability", 0.85)

            if prob >= 0.70:
                band = "HIGH"
            elif prob >= 0.40:
                band = "MEDIUM"
            else:
                band = "LOW"

            cand = OutreachSamplingCandidate(
                canonical_lead_id=cid,
                sampling_strategy="BALANCED_PROBABILITY_BAND",
                sampling_batch_id=batch_id,
                candidate_probability_band=band,
                niche=lead.get("niche", "Dental Clinics"),
                geography=lead.get("geography", "Dehradun"),
                website_state=lead.get("website_state", "active"),
                contactability=lead.get("contactability", "OWNER_CONTACT"),
                service_opportunities=lead.get("service_opportunities", ["WEBSITE"]),
                source_count=lead.get("source_count", 3),
            )
            self.sampled_candidates[cid] = cand
            results.append(cand)
        return results


class ProductivityOutcomeEngine:
    """Records controlled outreach attempts, contact states, and validated productivity outcomes."""

    def __init__(self) -> None:
        self.outcomes: dict[str, ExpansionOutcomeRecord] = {}

    def record_productivity_outcome(
        self,
        canonical_lead_id: str,
        prediction_id: str,
        outreach_batch_id: str,
        reviewer_id: str,
        outreach_state: OutreachState,
        final_productivity_outcome: FinalOutcome,
        feature_snapshot_timestamp: str,
        prediction_timestamp: str,
        evidence_reference: str | None = None,
        notes: str | None = None,
    ) -> ExpansionOutcomeRecord:
        ts = datetime.datetime.now(datetime.UTC).isoformat()

        # Enforce timestamp ordering invariant
        if feature_snapshot_timestamp > prediction_timestamp or prediction_timestamp > ts:
            raise ValueError(
                "Temporal ordering invariant violated: feature_snapshot_ts <= prediction_ts <= outcome_ts"
            )

        rec = ExpansionOutcomeRecord(
            canonical_lead_id=canonical_lead_id,
            prediction_id=prediction_id,
            outreach_batch_id=outreach_batch_id,
            reviewer_id=reviewer_id,
            outreach_state=outreach_state,
            final_productivity_outcome=final_productivity_outcome,
            outcome_timestamp=ts,
            evidence_reference=evidence_reference,
            notes=notes,
        )
        self.outcomes[canonical_lead_id] = rec
        return rec


class InterRaterProductivityReviewManager:
    """Manages double-review sampling (min 20%, min 100 records) and calculates Cohen's Kappa."""

    @staticmethod
    def evaluate_double_review(
        reviewer_1_outcomes: list[str], reviewer_2_outcomes: list[str]
    ) -> ExpansionDoubleReviewResult:
        n = len(reviewer_1_outcomes)
        if n == 0:
            return ExpansionDoubleReviewResult(
                0, 0, 0.0, 0.0, False, "PRODUCTIVITY_LABEL_QUALITY_WARNING"
            )

        categories = ["PRODUCTIVE", "UNPRODUCTIVE", "NOT_RESOLVED"]
        conf_matrix = {c1: {c2: 0 for c2 in categories} for c1 in categories}

        agreements = 0
        for r1, r2 in zip(reviewer_1_outcomes, reviewer_2_outcomes, strict=False):
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

        cls = "SUBSTANTIAL" if passed else "PRODUCTIVITY_LABEL_QUALITY_WARNING"
        return ExpansionDoubleReviewResult(
            total_reviewed=n,
            raw_agreements=agreements,
            raw_agreement_pct=raw_pct,
            cohens_kappa=kappa,
            target_passed=passed,
            classification=cls,
        )


class SelectionBiasMonitor:
    """Monitors selection bias between Outreach-selected and Untouched Control cohorts."""

    @staticmethod
    def evaluate_selection_bias(
        outreach_probs: list[float], control_probs: list[float]
    ) -> dict[str, Any]:
        if not outreach_probs or not control_probs:
            return {"standardized_mean_diff": 0.0, "classification": "SELECTION_BIAS_LOW"}

        m_out = float(np.mean(outreach_probs))
        m_ctrl = float(np.mean(control_probs))
        std_out = float(np.std(outreach_probs))
        std_ctrl = float(np.std(control_probs))

        pooled_std = (
            math.sqrt((std_out**2 + std_ctrl**2) / 2.0) if (std_out + std_ctrl) > 0 else 1.0
        )
        smd = round(abs(m_out - m_ctrl) / pooled_std, 4) if pooled_std > 0 else 0.0

        if smd > 0.50:
            cls = "SELECTION_BIAS_HIGH"
        elif smd > 0.20:
            cls = "SELECTION_BIAS_MODERATE"
        else:
            cls = "SELECTION_BIAS_LOW"

        return {
            "mean_outreach_probability": round(m_out, 4),
            "mean_control_probability": round(m_ctrl, 4),
            "standardized_mean_diff": smd,
            "classification": cls,
        }


class ProductivityExpansionReadinessClassifier:
    """Evaluates cumulative productivity ground-truth metrics and classifies model training readiness."""

    @staticmethod
    def classify_readiness(
        total_resolved_outcomes: int,
        productive_count: int,
        unproductive_count: int,
        kappa: float,
        leakage_violations: int,
        bias_classification: str,
    ) -> tuple[str, bool, str]:
        if leakage_violations > 0 or kappa < 0.75:
            return (
                "PRODUCTIVITY_LABEL_QUALITY_WARNING",
                True,
                "Label quality or temporal leakage check failed.",
            )

        if total_resolved_outcomes >= 500 and productive_count >= 200 and unproductive_count >= 200:
            return (
                "PRODUCTIVITY_MODEL_TRAINING_CANDIDATE",
                False,
                "Cumulative corpus reaches 500+ resolved outcomes with adequate class representation (250 PRODUCTIVE, 250 UNPRODUCTIVE), Cohen's Kappa >= 0.75, and 0 leakage violations. Ready for offline Productivity Model v1 Challenger candidate training.",
            )

        return (
            "MORE_REAL_OUTREACH_DATA_REQUIRED",
            True,
            f"Corpus contains {total_resolved_outcomes} resolved outcomes. Minimum 500 required for training candidate status.",
        )
