from __future__ import annotations

import datetime
import logging
from collections import Counter

from sqlalchemy.orm import Session

from backend.app.models_phase3 import ActiveLearningCandidate, HumanOutcomeEvent

logger = logging.getLogger(__name__)


class ActiveLearningEngine:
    """Multi-factor Active Learning Engine optimizing uncertainty, model disagreement, novelty, diversity, and duplicate suppression."""

    def evaluate_and_enqueue_candidate(
        self,
        db: Session,
        canonical_lead_id: str,
        niche: str,
        city: str,
        prob_catboost: float,
        prob_lightgbm: float,
        identity_ambiguity: bool = False,
    ) -> ActiveLearningCandidate | None:
        # 1. Duplicate Candidate Control: Avoid re-enqueuing already reviewed leads
        already_reviewed = (
            db.query(HumanOutcomeEvent)
            .filter(HumanOutcomeEvent.canonical_lead_id == canonical_lead_id)
            .first()
        )
        if already_reviewed:
            logger.info(
                f"[Active Learning] Lead {canonical_lead_id} already reviewed. Suppressing duplicate candidate enqueue."
            )
            return None

        existing_cand = (
            db.query(ActiveLearningCandidate)
            .filter(ActiveLearningCandidate.canonical_lead_id == canonical_lead_id)
            .first()
        )
        if existing_cand:
            existing_cand.selection_count += 1
            existing_cand.last_selected_timestamp = datetime.datetime.utcnow()
            db.commit()
            return existing_cand

        # 2. Compute Multi-Factor Component Scores
        avg_p = (prob_catboost + prob_lightgbm) / 2.0
        uncertainty = round(1.0 - abs(avg_p - 0.5) * 2.0, 4)
        model_disagreement = round(abs(prob_catboost - prob_lightgbm), 4)

        # Diversity Quota Factor: Prefer under-represented niches and cities
        niche_count = (
            db.query(ActiveLearningCandidate).filter(ActiveLearningCandidate.niche == niche).count()
        )
        novelty_score = round(1.0 / (1.0 + niche_count), 4)

        ambiguity_bonus = 0.25 if identity_ambiguity else 0.0

        # Composite Multi-Factor Priority Score
        composite_score = round(
            (uncertainty * 0.40)
            + (model_disagreement * 0.25)
            + (novelty_score * 0.20)
            + (ambiguity_bonus * 0.15),
            4,
        )

        reason = (
            f"Uncertainty: {uncertainty}, Model Disagreement: {model_disagreement}, "
            f"Novelty Score: {novelty_score}, Identity Ambiguity: {identity_ambiguity}"
        )

        cand = ActiveLearningCandidate(
            canonical_lead_id=canonical_lead_id,
            niche=niche,
            city=city,
            uncertainty_score=uncertainty,
            model_disagreement_score=model_disagreement,
            identity_ambiguity_flag=identity_ambiguity,
            novelty_score=novelty_score,
            composite_priority_score=composite_score,
            priority_reason=reason,
        )
        db.add(cand)
        db.commit()
        return cand

    def get_prioritized_queue(
        self, db: Session, limit: int = 50, max_per_niche: int = 5
    ) -> list[ActiveLearningCandidate]:
        """Returns prioritized review queue enforcing niche diversity quotas."""
        candidates = (
            db.query(ActiveLearningCandidate)
            .filter(ActiveLearningCandidate.review_status == "UNREVIEWED")
            .order_by(ActiveLearningCandidate.composite_priority_score.desc())
            .all()
        )

        diverse_queue: list[ActiveLearningCandidate] = []
        niche_counts: Counter[str] = Counter()

        for cand in candidates:
            if niche_counts[cand.niche] < max_per_niche:
                diverse_queue.append(cand)
                niche_counts[cand.niche] += 1
            if len(diverse_queue) >= limit:
                break

        return diverse_queue
