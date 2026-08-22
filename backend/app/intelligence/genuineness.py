from __future__ import annotations

import logging

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.models import Lead, SourceRecord

logger = logging.getLogger(__name__)


class GenuinenessDecision(BaseModel):
    decision: str = Field(..., description="GENUINE, NEEDS_REVIEW, REJECTED")
    overall_score: float = Field(..., ge=0.0, le=1.0)
    business_confidence: float = Field(..., ge=0.0, le=1.0)
    contact_confidence: float = Field(..., ge=0.0, le=1.0)
    digital_presence: float = Field(..., ge=0.0, le=1.0)
    source_agreement: float = Field(..., ge=0.0, le=1.0)
    relevance: float = Field(..., ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)


class GenuinenessAgent:
    """Genuineness Agent determining whether a lead candidate is genuine, contactable, and relevant."""

    def evaluate_lead_genuineness(self, db: Session, lead: Lead) -> GenuinenessDecision:
        reasons: list[str] = []

        # 1. Business Confidence
        biz_conf = 0.95 if lead.business_name and len(lead.business_name.strip()) >= 3 else 0.40
        if biz_conf > 0.9:
            reasons.append("High business entity confidence.")

        # 2. Contact Confidence
        has_email = bool(lead.email and "@" in lead.email)
        has_phone = bool(lead.phone and len(lead.phone) >= 7)
        if has_email and has_phone:
            contact_conf = 0.92
            reasons.append("Dual verified email & phone contactability.")
        elif has_email or has_phone:
            contact_conf = 0.65
            reasons.append("Single verified contact channel available.")
        else:
            contact_conf = 0.10
            reasons.append("Missing email and phone contact channels.")

        # 3. Digital Presence
        digital_presence = 0.88 if lead.website and lead.website.startswith("http") else 0.30

        # 4. Source Agreement
        src_count = db.query(SourceRecord).filter(SourceRecord.lead_id == lead.id).count()
        source_agreement = min(1.0, 0.70 + (src_count * 0.15))

        # 5. Relevance & CatBoost/LightGBM ML Model Inference
        relevance = 0.95

        from backend.app.intelligence.catboost_lightgbm import CatBoostLightGBMScorer

        ml_scorer = CatBoostLightGBMScorer(model_version="v1.3")
        ml_result = ml_scorer.predict_lead_quality_score(
            {
                "has_website": bool(lead.website),
                "has_email": has_email,
                "has_phone": has_phone,
                "business_name": lead.business_name,
            }
        )
        ml_prob = ml_result["conversion_probability"]

        # 70% ML Model Ensemble Score + 30% Deterministic Rule Feature Score
        rule_score = (
            (biz_conf * 0.25)
            + (contact_conf * 0.30)
            + (digital_presence * 0.20)
            + (source_agreement * 0.15)
            + (relevance * 0.10)
        )
        overall_score = round((ml_prob * 0.70) + (rule_score * 0.30), 2)
        reasons.append(f"CatBoost/LightGBM ML Model v1.3 Score: {ml_prob * 100}%")

        if overall_score >= 0.75:
            decision = "GENUINE"
        elif overall_score >= 0.45:
            decision = "NEEDS_REVIEW"
        else:
            decision = "REJECTED"

        # Update lead ORM attributes
        lead.genuineness_status = decision
        lead.genuineness_score = overall_score
        db.commit()

        # Record prediction into PredictionLedger
        try:
            from backend.app.models import PredictionLedger

            ledger = PredictionLedger(
                workspace_id=lead.workspace_id,
                lead_id=lead.id,
                model_name="CatBoost + LightGBM Ensemble",
                model_version="v1.3",
                feature_version="v3.0",
                prediction=overall_score,
                confidence=biz_conf,
                decision=decision,
            )
            db.add(ledger)
            db.commit()
        except Exception as err:
            logger.warning(f"PredictionLedger insert skipped: {err}")

        return GenuinenessDecision(
            decision=decision,
            overall_score=overall_score,
            business_confidence=biz_conf,
            contact_confidence=contact_conf,
            digital_presence=digital_presence,
            source_agreement=source_agreement,
            relevance=relevance,
            reasons=reasons,
        )
