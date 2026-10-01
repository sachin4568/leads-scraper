import uuid
from sqlalchemy import select
from datetime import datetime, UTC

from backend.app.database import SessionLocal
from backend.app.models import RawLead, EvidenceRecord, ServiceOpportunity, EnrichmentState, Workspace, RawLeadSheet
from backend.app.enrichment.scoring import evaluate_service_opportunities

def run_db_verification():
    print("Initializing Real Database Verification for Phase 6 Opportunity Engine...")
    db = SessionLocal()
    
    # 1. Create Workspace and Sheet
    ws_id = uuid.uuid4()
    ws = Workspace(id=ws_id, name="Phase 6 Opportunity Verification Workspace")
    db.add(ws)
    db.flush()
    
    sheet_id = uuid.uuid4()
    sheet = RawLeadSheet(id=sheet_id, workspace_id=ws_id, name="Phase 6 Sheet", niche="tech", sheet_number=1)
    db.add(sheet)
    db.commit()

    cases = [
        {
            "code": "A",
            "name": "Verified Website + SEO + Email/Social Evidence",
            "bname": "Django Software Foundation",
            "url": "https://www.djangoproject.com",
            "phone": "555-0101",
            "email": "info@djangoproject.com",
            "evidences": [
                {"type": "WEBSITE", "field": "website", "class": "VERIFIED_BUSINESS_WEBSITE", "status": "VERIFIED", "source": "https://www.djangoproject.com"},
                {"type": "EMAIL_DISCOVERY", "field": "email", "class": "VERIFIED_BUSINESS_EMAIL", "status": "VERIFIED", "source": "info@djangoproject.com"},
                {"type": "SOCIAL_PROFILE", "field": "instagram", "class": "VERIFIED_SOCIAL_PROFILE", "status": "VERIFIED", "source": "https://instagram.com/djangoproject"},
                {"type": "SEO_AUDIT", "field": "seo", "class": "TECHNICAL_SEO_AUDIT", "status": "VERIFIED", "source": "https://www.djangoproject.com", "details": {"findings": {"has_title": True, "title_length": 45, "has_meta_description": False, "h1_count": 1, "has_viewport_tag": True, "has_jsonld_schema": False}}}
            ]
        },
        {
            "code": "B",
            "name": "No Website + Email/Contact Evidence",
            "bname": "No Website Local Plumbing",
            "url": None,
            "phone": "555-0102",
            "email": "contact@nowebsiteplumbing.co.uk",
            "evidences": [
                {"type": "WEBSITE", "field": "website", "class": "NO_WEBSITE", "status": "NO_WEBSITE", "source": "NO_WEBSITE"},
                {"type": "EMAIL_DISCOVERY", "field": "email", "class": "VERIFIED_BUSINESS_EMAIL", "status": "VERIFIED", "source": "contact@nowebsiteplumbing.co.uk"}
            ]
        },
        {
            "code": "C",
            "name": "Social Evidence + Limited Metrics",
            "bname": "Social First Cafe",
            "url": "https://www.socialfirstcafe.com",
            "phone": "555-0103",
            "email": None,
            "evidences": [
                {"type": "WEBSITE", "field": "website", "class": "VERIFIED_BUSINESS_WEBSITE", "status": "VERIFIED", "source": "https://www.socialfirstcafe.com"},
                {"type": "SOCIAL_PROFILE", "field": "facebook", "class": "LIKELY_SOCIAL_PROFILE", "status": "VERIFIED", "source": "https://facebook.com/socialfirstcafe"}
            ]
        },
        {
            "code": "D",
            "name": "Provider / Social Unavailable",
            "bname": "Blocked Social Business",
            "url": "https://www.blockedsocial.com",
            "phone": "555-0104",
            "email": None,
            "evidences": [
                {"type": "WEBSITE", "field": "website", "class": "VERIFIED_BUSINESS_WEBSITE", "status": "VERIFIED", "source": "https://www.blockedsocial.com"},
                {"type": "SOCIAL_PROFILE", "field": "instagram", "class": "UNAVAILABLE", "status": "UNAVAILABLE", "source": "https://instagram.com/blockedsocial"}
            ]
        },
        {
            "code": "E",
            "name": "Mixed Signals (Broken Website + Active Social)",
            "bname": "Broken Web Active Social Ltd",
            "url": "https://www.brokenweb.com",
            "phone": "555-0105",
            "email": "admin@brokenweb.com",
            "evidences": [
                {"type": "WEBSITE", "field": "website", "class": "BROKEN", "status": "BROKEN", "source": "https://www.brokenweb.com"},
                {"type": "SOCIAL_PROFILE", "field": "instagram", "class": "VERIFIED_SOCIAL_PROFILE", "status": "VERIFIED", "source": "https://instagram.com/brokenweb"}
            ]
        }
    ]
    
    for case in cases:
        print(f"\n==================================================")
        print(f"Executing Case [{case['code']}]: {case['name']}")
        
        lead_id = uuid.uuid4()
        lead = RawLead(
            id=lead_id,
            sheet_id=sheet_id,
            business_name=case["bname"],
            website=case["url"],
            phone=case["phone"],
            email=case["email"]
        )
        db.add(lead)
        db.flush()
        
        for ev_data in case["evidences"]:
            ev = EvidenceRecord(
                workspace_id=ws_id,
                raw_lead_id=lead_id,
                field_name=ev_data["field"],
                status=ev_data["status"],
                evidence_type=ev_data["type"],
                classification=ev_data["class"],
                source=ev_data["source"],
                details=ev_data.get("details", {})
            )
            db.add(ev)
            
        state = EnrichmentState(
            raw_lead_id=lead_id,
            website_status="COMPLETED",
            email_status="COMPLETED",
            instagram_status="COMPLETED",
            facebook_status="COMPLETED",
            seo_status="COMPLETED"
        )
        db.add(state)
        db.commit()

        # Execute Phase 6 Evaluation Task
        print(f"-> Calling evaluate_service_opportunities for RawLead {lead_id}")
        evaluate_service_opportunities(None, str(lead_id), str(ws_id))
        
        # Read real DB persisted records
        db.expire_all()
        
        opp_records = db.execute(
            select(ServiceOpportunity)
            .where(ServiceOpportunity.raw_lead_id == lead_id)
        ).scalars().all()
        
        print(f"-> Persisted ServiceOpportunity Rows Count: {len(opp_records)} (Expected: 4)")
        
        for opp in opp_records:
            print(f"   Service: [{opp.service}]")
            print(f"      Status: {opp.status}")
            print(f"      Opportunity Score: {opp.opportunity_score}")
            print(f"      Confidence Score: {opp.confidence_score}")
            print(f"      Priority: {opp.priority}")
            print(f"      Reasons: {opp.reasons}")
            print(f"      Signals: {opp.signals}")
            print(f"      Missing Data: {opp.missing_data}")

        current_lead = db.scalar(select(RawLead).where(RawLead.id == lead_id))
        is_unchanged = (
            current_lead.business_name == case["bname"] and 
            current_lead.phone == case["phone"] and
            current_lead.email == case["email"]
        )
        print(f"-> Confirmation that RawLead remained unchanged: {is_unchanged}")

    db.close()

if __name__ == "__main__":
    run_db_verification()
