import uuid
from datetime import datetime, UTC
from sqlalchemy import select
import logging
logger = logging.getLogger(__name__)

from backend.app.database import SessionLocal
from backend.app.models import RawLead, EvidenceRecord, EnrichmentState
from backend.app.worker import celery_app
from backend.app.enrichment.social_providers import normalize_social_url, evaluate_social_identity, SocialScraper

@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)
def enrich_social_pipeline(self, raw_lead_id: str, workspace_id: str) -> None:
    db = SessionLocal()
    try:
        lead_id = uuid.UUID(raw_lead_id)
        ws_id = uuid.UUID(workspace_id)
        
        # 1. Fetch RawLead & Evidence
        lead = db.scalar(select(RawLead).where(RawLead.id == lead_id))
        if not lead:
            return
            
        website_evidences = db.execute(
            select(EvidenceRecord)
            .where(EvidenceRecord.raw_lead_id == lead_id)
            .where(EvidenceRecord.evidence_type == 'WEBSITE')
        ).scalars().all()
        
        website_urls = [ev.source for ev in website_evidences if ev.source]
        
        email_evidences = db.execute(
            select(EvidenceRecord)
            .where(EvidenceRecord.raw_lead_id == lead_id)
            .where(EvidenceRecord.evidence_type == 'EMAIL_DISCOVERY')
        ).scalars().all()
        
        email_addresses = [ev.source for ev in email_evidences if ev.source]
        
        state = db.scalar(select(EnrichmentState).where(EnrichmentState.raw_lead_id == lead_id))
        if not state:
            state = EnrichmentState(raw_lead_id=lead_id)
            db.add(state)
            
        state.instagram_status = "RUNNING"
        state.facebook_status = "RUNNING"
        db.commit()
        
        # Candidate generation (from raw_data or website parsing)
        candidates = []
        if lead.raw_data and isinstance(lead.raw_data, dict):
            for k, v in lead.raw_data.items():
                if isinstance(v, str) and ('instagram.com' in v or 'facebook.com' in v or 'fb.com' in v):
                    candidates.append(v)
        
        db.close()
        
        # 2. Extract & Normalize
        ig_cand = None
        fb_cand = None
        for c in candidates:
            plat, handle, norm_url = normalize_social_url(c)
            if plat == "instagram" and handle and not ig_cand:
                ig_cand = (handle, norm_url)
            elif plat == "facebook" and handle and not fb_cand:
                fb_cand = (handle, norm_url)
                
        scraper = SocialScraper()
        
        def process_platform(plat: str, cand: tuple | None, bname: str, w_urls: list, e_addrs: list) -> tuple[str, dict]:
            if not cand:
                return "NOT_FOUND", {"classification": "NOT_FOUND", "status": "NOT_FOUND"}
                
            handle, url = cand
            data = scraper.fetch_profile(plat, url)
            
            if data["status"] == "UNAVAILABLE":
                return "UNAVAILABLE", {"classification": "UNAVAILABLE", "status": "UNAVAILABLE", "source": url}
            elif data["status"] == "NOT_FOUND":
                return "NOT_FOUND", {"classification": "NOT_FOUND", "status": "NOT_FOUND", "source": url}
                
            classification = evaluate_social_identity(bname, handle, data, w_urls, e_addrs)
            
            details = {
                "platform": plat,
                "profile_url": url,
                "username": handle,
                "profile_name": data.get("profile_name"),
                "followers": data.get("followers"),
                "followers_status": data.get("followers_status", "UNKNOWN"),
                "identity_classification": classification,
                "observed_at": datetime.now(UTC).isoformat()
            }
            
            status = "VERIFIED" if classification == "VERIFIED_SOCIAL_PROFILE" else "UNVERIFIED"
            return "COMPLETED", {"classification": classification, "status": status, "source": url, "details": details}

        ig_pipeline_state, ig_res = process_platform("instagram", ig_cand, lead.business_name, website_urls, email_addresses)
        fb_pipeline_state, fb_res = process_platform("facebook", fb_cand, lead.business_name, website_urls, email_addresses)
        
        # 3. Write back
        db = SessionLocal()
        
        if ig_res.get("source"):
            ev = EvidenceRecord(
                workspace_id=ws_id,
                raw_lead_id=lead_id,
                field_name="instagram",
                status=ig_res["status"],
                evidence_type="SOCIAL_PROFILE",
                classification=ig_res["classification"],
                source=ig_res["source"], # Full URL without truncation!
                details=ig_res.get("details", {})
            )
            db.add(ev)
            
        if fb_res.get("source"):
            ev = EvidenceRecord(
                workspace_id=ws_id,
                raw_lead_id=lead_id,
                field_name="facebook",
                status=fb_res["status"],
                evidence_type="SOCIAL_PROFILE",
                classification=fb_res["classification"],
                source=fb_res["source"], # Full URL without truncation!
                details=fb_res.get("details", {})
            )
            db.add(ev)
            
        final_state = db.scalar(select(EnrichmentState).where(EnrichmentState.raw_lead_id == lead_id))
        final_state.instagram_status = ig_pipeline_state
        final_state.facebook_status = fb_pipeline_state
        db.commit()

    except Exception as e:
        logger.error(f"Error in enrich_social_pipeline: {e}")
        db.rollback()
        final_state = db.scalar(select(EnrichmentState).where(EnrichmentState.raw_lead_id == lead_id))
        if final_state:
            final_state.instagram_status = "FAILED"
            final_state.facebook_status = "FAILED"
            db.commit()
    finally:
        db.close()
