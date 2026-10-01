import uuid
from datetime import datetime, UTC
from sqlalchemy import select
import logging
logger = logging.getLogger(__name__)

from backend.app.database import SessionLocal
from backend.app.models import RawLead, EvidenceRecord, EnrichmentState
from backend.app.worker import celery_app
from backend.app.enrichment.seo_analyzer import SEOAnalyzer

@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)
def enrich_seo_pipeline(self, raw_lead_id: str, workspace_id: str) -> None:
    db = SessionLocal()
    try:
        lead_id = uuid.UUID(raw_lead_id)
        ws_id = uuid.UUID(workspace_id)
        
        # 1. Fetch RawLead & Website Evidence
        lead = db.scalar(select(RawLead).where(RawLead.id == lead_id))
        if not lead:
            return
            
        website_evidences = db.execute(
            select(EvidenceRecord)
            .where(EvidenceRecord.raw_lead_id == lead_id)
            .where(EvidenceRecord.evidence_type == 'WEBSITE')
        ).scalars().all()
        
        state = db.scalar(select(EnrichmentState).where(EnrichmentState.raw_lead_id == lead_id))
        if not state:
            state = EnrichmentState(raw_lead_id=lead_id)
            db.add(state)
            
        # Determine verified target website URL
        target_url = None
        for ev in website_evidences:
            if ev.classification in ("VERIFIED_BUSINESS_WEBSITE", "LIKELY_BUSINESS_WEBSITE") and ev.source:
                target_url = ev.source
                break
                
        if not target_url and lead.website:
            target_url = lead.website
            
        if not target_url:
            state.seo_status = "NOT_APPLICABLE"
            db.commit()
            return
            
        state.seo_status = "RUNNING"
        db.commit()
        db.close()
        
        # 2. Network / Analysis Work (Outside DB Session)
        analyzer = SEOAnalyzer()
        findings = analyzer.audit_url(target_url)
        
        # 3. DB Persistence Session
        db = SessionLocal()
        
        ev_status = "VERIFIED" if findings.get("status") == "OBSERVED" else "UNAVAILABLE"
        seo_pipeline_state = "COMPLETED" if findings.get("status") == "OBSERVED" else "UNAVAILABLE"
        
        details = {
            "target_url": target_url,
            "findings": findings,
            "audited_at": datetime.now(UTC).isoformat()
        }
        
        ev = EvidenceRecord(
            workspace_id=ws_id,
            raw_lead_id=lead_id,
            field_name="seo",
            status=ev_status,
            evidence_type="SEO_AUDIT",
            classification="TECHNICAL_SEO_AUDIT",
            source=target_url, # Complete full URL (Text column)
            details=details
        )
        db.add(ev)
        
        final_state = db.scalar(select(EnrichmentState).where(EnrichmentState.raw_lead_id == lead_id))
        if final_state:
            final_state.seo_status = seo_pipeline_state
        db.commit()

    except Exception as e:
        logger.error(f"Error in enrich_seo_pipeline: {e}")
        db.rollback()
        final_state = db.scalar(select(EnrichmentState).where(EnrichmentState.raw_lead_id == lead_id))
        if final_state:
            final_state.seo_status = "FAILED"
            db.commit()
    finally:
        db.close()
