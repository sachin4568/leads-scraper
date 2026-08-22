from __future__ import annotations

import logging
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.models_phase2 import LeadObservation, HumanOutcomeEventRecord

logger = logging.getLogger(__name__)


class SourceConfidenceSystem:
    @staticmethod
    def get_source_acceptance_rate(db: Session, source_name: str) -> float:
        """Calculate historical correctness rate for a source based on human outcome logs or Redis cache."""
        from backend.app.worker_concurrency import _global_limiter
        r = _global_limiter._redis_client
        if r:
            try:
                total = int(r.hget(f"source_feedback:{source_name}", "total") or 0)
                accepted = int(r.hget(f"source_feedback:{source_name}", "accepted") or 0)
                if total > 0:
                    score = accepted / total
                    logger.info(f"[SourceConfidence] Cache rate for '{source_name}': {score:.2f}")
                    return score
            except Exception as e:
                logger.debug(f"Redis lookup error for source_feedback: {e}")

        # Fallback to querying DB logs
        try:
            obs_ids = db.scalars(
                select(LeadObservation.canonical_lead_id).where(LeadObservation.source_name == source_name)
            ).all()
            
            if not obs_ids:
                return 1.0  # Default to high confidence for untested source
                
            outcomes = db.scalars(
                select(HumanOutcomeEventRecord.human_outcome).where(
                    HumanOutcomeEventRecord.canonical_lead_id.in_(obs_ids)
                )
            ).all()
            
            if not outcomes:
                return 1.0
                
            accepted = sum(1 for o in outcomes if o.lower() in ("accepted", "good", "excellent", "good_lead"))
            score = accepted / len(outcomes)
            logger.info(f"[SourceConfidence] DB rate for '{source_name}': {score:.2f} (based on {len(outcomes)} reviews)")
            return score
        except Exception as e:
            logger.warning(f"Error querying source acceptance rate: {e}")
            return 1.0

    @classmethod
    def calculate_field_confidence(
        cls,
        db: Session,
        field_name: str,
        field_value: str | None,
        observations: list[LeadObservation],
        validation_passed: bool = False,
        validation_score: int = 0
    ) -> int:
        """Calculate dynamic field confidence score based on multi-signal evidence."""
        if not field_value or not str(field_value).strip():
            return 0
            
        sources_observing = [
            obs for obs in observations 
            if str(getattr(obs, f"observed_{field_name}", None)).strip().lower() == str(field_value).strip().lower()
        ]
        
        if not sources_observing:
            return 50  # Default baseline if not matched in direct raw observation
            
        source_rates = [cls.get_source_acceptance_rate(db, obs.source_name) for obs in sources_observing]
        avg_source_rate = sum(source_rates) / len(source_rates)
        
        # Base confidence starts at avg_source_rate (scaled to 0-80)
        confidence = avg_source_rate * 80.0
        
        # Cross-source agreement bonus (+10 per additional distinct source confirming lead)
        distinct_sources = {obs.source_name for obs in sources_observing}
        concurrence_bonus = max(0, (len(distinct_sources) - 1) * 10)
        confidence += concurrence_bonus
        
        # Validation score contribution
        if validation_passed:
            confidence += 15
            confidence += (validation_score / 100.0) * 10
        else:
            confidence -= 10
            
        return min(100, max(0, round(confidence)))
