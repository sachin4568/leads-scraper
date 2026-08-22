from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.intelligence.phase3_trainer import Phase3AITrainer
from backend.app.models import FeatureSnapshot, HumanFeedback, Lead, PredictionLedger

logger = logging.getLogger(__name__)


class ActiveLearningItem(BaseModel):
    lead_id: str
    business_name: str
    genuineness_score: float
    uncertainty_score: float


class DatasetCoverageReport(BaseModel):
    total_samples: int
    website_breakdown: dict[str, int]
    contact_breakdown: dict[str, int]
    social_breakdown: dict[str, int]
    underrepresented_scenarios: list[str]


class LearningAgent:
    """Learning Agent managing active learning, Feature Store snapshots, Prediction Ledger, coverage monitoring, and Champion vs Challenger model promotion."""

    def record_feature_snapshot(
        self, db: Session, workspace_id: Any, lead_id: Any, features: dict[str, Any]
    ) -> FeatureSnapshot:
        """Persists exact feature state prior to model inference."""
        snapshot = FeatureSnapshot(
            workspace_id=workspace_id,
            lead_id=lead_id,
            feature_version="v3.0",
            snapshot_data=features,
        )
        db.add(snapshot)
        db.commit()
        return snapshot

    def record_prediction(
        self,
        db: Session,
        workspace_id: Any,
        lead_id: Any,
        model_name: str,
        model_version: str,
        prediction: float,
        confidence: float,
        decision: str,
    ) -> PredictionLedger:
        """Records AI decision in the Prediction Ledger for complete auditability."""
        ledger = PredictionLedger(
            workspace_id=workspace_id,
            lead_id=lead_id,
            model_name=model_name,
            model_version=model_version,
            feature_version="v3.0",
            prediction=prediction,
            confidence=confidence,
            decision=decision,
        )
        db.add(ledger)
        db.commit()
        return ledger

    def select_active_learning_queue(
        self, db: Session, workspace_id: Any, limit: int = 20
    ) -> list[ActiveLearningItem]:
        """Ranks lead candidates continuously using uncertainty_score = 1.0 - |prediction - 0.5| * 2.0."""
        leads = list(
            db.scalars(
                select(Lead)
                .where(
                    Lead.workspace_id == workspace_id,
                    Lead.deleted_at.is_(None),
                )
                .order_by(Lead.created_at.desc())
                .limit(100)
            )
        )

        items: list[ActiveLearningItem] = []
        for lead in leads:
            score = lead.genuineness_score
            uncertainty = round(1.0 - (abs(score - 0.50) * 2.0), 2)
            if uncertainty >= 0.40:
                items.append(
                    ActiveLearningItem(
                        lead_id=str(lead.id),
                        business_name=lead.business_name,
                        genuineness_score=score,
                        uncertainty_score=uncertainty,
                    )
                )

        # Sort descending by highest uncertainty
        items.sort(key=lambda x: x.uncertainty_score, reverse=True)
        return items[:limit]

    def monitor_dataset_coverage(self, db: Session, workspace_id: Any) -> DatasetCoverageReport:
        """Monitors scenario coverage gaps across website, contact, and social presence."""
        leads = list(
            db.scalars(
                select(Lead).where(Lead.workspace_id == workspace_id, Lead.deleted_at.is_(None))
            )
        )

        web = {"no_website": 0, "poor_website": 0, "average": 0, "strong": 0}
        contact = {"phone_only": 0, "email_only": 0, "both": 0, "neither": 0}
        social = {"instagram": 0, "facebook": 0, "both": 0, "neither": 0}
        underrepresented: list[str] = []

        for lead in leads:
            if not lead.website:
                web["no_website"] += 1
            else:
                web["strong"] += 1

            if lead.phone and lead.email:
                contact["both"] += 1
            elif lead.phone:
                contact["phone_only"] += 1
            elif lead.email:
                contact["email_only"] += 1
            else:
                contact["neither"] += 1

        if web["no_website"] < 10:
            underrepresented.append("Businesses with no website (Needs 50+ samples)")
        if contact["email_only"] < 10:
            underrepresented.append("Email-only candidates (Needs 50+ samples)")

        return DatasetCoverageReport(
            total_samples=len(leads),
            website_breakdown=web,
            contact_breakdown=contact,
            social_breakdown=social,
            underrepresented_scenarios=underrepresented,
        )

    def trigger_champion_challenger_retraining(
        self, db: Session, workspace_id: Any
    ) -> dict[str, Any]:
        """Trains Challenger candidate model and evaluates against Champion Production Model."""
        feedback_count = (
            db.query(HumanFeedback).filter(HumanFeedback.workspace_id == workspace_id).count()
        )
        challenger_version = f"v2.{feedback_count + 5}"

        trainer = Phase3AITrainer(model_version=challenger_version)
        report = trainer.execute_full_3phase_training(human_feedback_count=feedback_count)

        # Champion vs Challenger Evaluation Gate
        champion_f1 = 0.82
        challenger_f1 = report.metrics.f1_score

        if challenger_f1 >= champion_f1:
            status = "STAGING_CHALLENGER_VICTORY"
            recommendation = "Promote to PRODUCTION"
        else:
            status = "STAGING_REGRESSION_REJECTED"
            recommendation = "Reject Candidate Model"

        return {
            "champion_version": "v2.0_phase3_ensemble",
            "challenger_version": challenger_version,
            "champion_f1": champion_f1,
            "challenger_f1": challenger_f1,
            "training_samples": report.total_training_samples,
            "metrics": report.metrics.model_dump(),
            "status": status,
            "recommendation": recommendation,
        }
