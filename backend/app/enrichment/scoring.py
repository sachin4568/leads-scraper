import logging
import uuid
from datetime import datetime, UTC
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.app.models import RawLead, EvidenceRecord, ServiceOpportunity
from backend.app.database import SessionLocal
from backend.app.worker import celery_app
from backend.app.enrichment.opportunity_engine import OpportunityEngine

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def evaluate_service_opportunities(self, raw_lead_id: str, workspace_id: str):
    """
    Phase 6 Service Opportunity & Lead Intelligence Engine task.
    Evaluates raw_lead_id across 4 services:
    - website_dev
    - website_seo
    - social_media_management
    - social_media_marketing
    """
    logger.info(f"Evaluating ServiceOpportunities for RawLead {raw_lead_id}")
    lead_uuid = uuid.UUID(raw_lead_id)
    
    # 1. DB Read Session
    db = SessionLocal()
    try:
        lead = db.scalar(select(RawLead).where(RawLead.id == lead_uuid))
        if not lead:
            logger.warning(f"RawLead {raw_lead_id} not found for opportunity evaluation.")
            return
            
        evidence_records = db.scalars(
            select(EvidenceRecord).where(EvidenceRecord.raw_lead_id == lead_uuid)
        ).all()
    finally:
        db.close()

    # 2. Pure Deterministic Evaluation (No DB Session Held)
    opportunity_results = OpportunityEngine.evaluate_all(lead, evidence_records)

    # 3. DB Persistence Session (Short-Lived Upsert)
    db = SessionLocal()
    try:
        for opp_data in opportunity_results:
            service_name = opp_data["service"]
            
            stmt = pg_insert(ServiceOpportunity).values(
                raw_lead_id=lead_uuid,
                service=service_name,
                status=opp_data["status"],
                opportunity_score=opp_data["opportunity_score"],
                confidence_score=opp_data["confidence_score"],
                priority=opp_data["priority"],
                reasons=opp_data["reasons"],
                signals=opp_data["signals"],
                missing_data=opp_data["missing_data"],
                evaluated_at=opp_data["evaluated_at"]
            )
            
            # Idempotent Upsert handling uq_raw_lead_service constraint
            update_dict = {
                "status": stmt.excluded.status,
                "opportunity_score": stmt.excluded.opportunity_score,
                "confidence_score": stmt.excluded.confidence_score,
                "priority": stmt.excluded.priority,
                "reasons": stmt.excluded.reasons,
                "signals": stmt.excluded.signals,
                "missing_data": stmt.excluded.missing_data,
                "evaluated_at": stmt.excluded.evaluated_at
            }
            
            upsert_stmt = stmt.on_conflict_do_update(
                constraint="uq_raw_lead_service",
                set_=update_dict
            )
            db.execute(upsert_stmt)

        db.commit()
        logger.info(f"Successfully persisted 4 ServiceOpportunities for RawLead {raw_lead_id}")
    except Exception as e:
        logger.error(f"Error persisting ServiceOpportunities for {raw_lead_id}: {e}")
        db.rollback()
    finally:
        db.close()
