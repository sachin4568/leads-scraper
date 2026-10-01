import uuid
from sqlalchemy import select
from datetime import datetime, UTC

from backend.app.database import SessionLocal
from backend.app.models import RawLead, EvidenceRecord, EnrichmentState, Workspace, RawLeadSheet
from backend.app.enrichment.seo_pipeline import enrich_seo_pipeline

def run_db_verification():
    print("Initializing Database Verification for Phase 5 SEO Pipeline...")
    db = SessionLocal()
    
    # 1. Create Workspace and Sheet
    ws_id = uuid.uuid4()
    ws = Workspace(id=ws_id, name="Phase 5 SEO Verification Workspace")
    db.add(ws)
    db.flush()
    
    sheet_id = uuid.uuid4()
    sheet = RawLeadSheet(id=sheet_id, workspace_id=ws_id, name="SEO Test Sheet", niche="tech", sheet_number=1)
    db.add(sheet)
    db.commit()

    cases = [
        {
            "code": "A",
            "name": "Real business website (Django Project)",
            "url": "https://www.djangoproject.com",
            "bname": "Django Software Foundation",
            "has_website_ev": True
        },
        {
            "code": "B",
            "name": "Real business website (FSF)",
            "url": "https://www.fsf.org",
            "bname": "Free Software Foundation",
            "has_website_ev": True
        },
        {
            "code": "C",
            "name": "Business with no website",
            "url": None,
            "bname": "No Website Plumbing Ltd",
            "has_website_ev": False
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
            location="London",
            phone="555-0100"
        )
        db.add(lead)
        db.flush()
        
        if case["has_website_ev"]:
            website_ev = EvidenceRecord(
                workspace_id=ws_id,
                raw_lead_id=lead_id,
                field_name="website",
                status="VERIFIED_BUSINESS_WEBSITE",
                evidence_type="WEBSITE",
                classification="VERIFIED_BUSINESS_WEBSITE",
                confidence_score=95,
                source=case["url"],
                details={"final_url": case["url"]}
            )
            db.add(website_ev)
            
        state = EnrichmentState(
            raw_lead_id=lead_id,
            website_status="COMPLETED" if case["has_website_ev"] else "NOT_FOUND"
        )
        db.add(state)
        db.commit()

        # 2. RUN ACTUAL PIPELINE TASK (Synchronous execution)
        print(f"-> Running enrich_seo_pipeline for {lead_id} ({case['url']})")
        enrich_seo_pipeline(None, str(lead_id), str(ws_id))
        
        # 3. Refresh DB and Verify
        db.expire_all()
        
        updated_state = db.scalar(select(EnrichmentState).where(EnrichmentState.raw_lead_id == lead_id))
        print(f"-> EnrichmentState.seo_status: {updated_state.seo_status}")
        
        evidence_records = db.execute(
            select(EvidenceRecord)
            .where(EvidenceRecord.raw_lead_id == lead_id)
            .where(EvidenceRecord.evidence_type == 'SEO_AUDIT')
        ).scalars().all()
        
        print(f"-> Database EvidenceRecord (SEO_AUDIT) rows created: {len(evidence_records)}")
        
        for idx, ev in enumerate(evidence_records):
            print(f"   [Row {idx+1}]")
            print(f"      field: {ev.field_name}")
            print(f"      evidence_type: {ev.evidence_type}")
            print(f"      classification: {ev.classification}")
            print(f"      source URL: {ev.source} (Length: {len(ev.source)})")
            print(f"      status: {ev.status}")
            if ev.details and "findings" in ev.details:
                f = ev.details["findings"]
                print(f"      Title: {f.get('title')}")
                print(f"      H1 Count: {f.get('h1_count')}")
                print(f"      Has Meta Desc: {f.get('has_meta_description')}")
                print(f"      Has Viewport: {f.get('has_viewport_tag')}")

        current_lead = db.scalar(select(RawLead).where(RawLead.id == lead_id))
        is_unchanged = (
            current_lead.business_name == case["bname"] and 
            current_lead.phone == "555-0100"
        )
        print(f"-> Confirmation that RawLead remained unchanged: {is_unchanged}")

    db.close()

if __name__ == "__main__":
    run_db_verification()
