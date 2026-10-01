import uuid
from sqlalchemy import select
from datetime import datetime, UTC

from backend.app.database import SessionLocal
from backend.app.models import RawLead, EvidenceRecord, EnrichmentState, Workspace, RawLeadSheet
from backend.app.enrichment.email_pipeline import enrich_email_pipeline

def run_db_verification():
    print("Initializing Database test...")
    db = SessionLocal()
    
    # 1. Create a dummy Workspace and Sheet
    ws_id = uuid.uuid4()
    ws = Workspace(id=ws_id, name="Phase 3 Verification")
    db.add(ws)
    db.commit()
    
    sheet_id = uuid.uuid4()
    sheet = RawLeadSheet(id=sheet_id, workspace_id=ws_id, name="Test Sheet", niche="test", sheet_number=1)
    db.add(sheet)
    db.commit()

    cases = [
        {
            "name": "A. Business with public role-based email",
            "url": "https://www.djangoproject.com",
            "bname": "Django Project"
        },
        {
            "name": "B. Business with multiple emails",
            "url": "https://www.fsf.org",
            "bname": "Free Software Foundation"
        },
        {
            "name": "C. Business with generic-provider business email (e.g. Gmail/Yahoo)",
            "url": "https://www.berkeleyside.org", # Contains some public editors
            "bname": "Berkeleyside"
        },
        {
            "name": "D. Business with no public email",
            "url": "https://www.example.com",
            "bname": "Acme Corp"
        },
        {
            "name": "E. Website unavailable / access blocked",
            "url": "https://www.yelp.com",
            "bname": "Yelp"
        }
    ]
    
    for case in cases:
        print(f"\\n==================================================")
        print(f"Executing Case: {case['name']}")
        
        # 1. Create RawLead
        lead_id = uuid.uuid4()
        lead = RawLead(
            id=lead_id,
            sheet_id=sheet_id,
            business_name=case["bname"],
            location="Test Location",
            phone="555-0000"
        )
        db.add(lead)
        db.flush()
        
        # 2. Simulate Phase 2 Website Completion
        website_ev = EvidenceRecord(
            workspace_id=ws_id,
            raw_lead_id=lead_id,
            field_name="website",
            status="VERIFIED_BUSINESS_WEBSITE",
            evidence_type="WEBSITE",
            classification="VERIFIED_BUSINESS_WEBSITE",
            confidence_score=90,
            source=case["url"],
            details={"final_url": case["url"]}
        )
        db.add(website_ev)
        
        state = EnrichmentState(
            raw_lead_id=lead_id,
            website_status="COMPLETED"
        )
        db.add(state)
        db.commit()

        # 3. RUN ACTUAL PIPELINE TASK (Synchronous execution)
        print(f"-> Running enrich_email_pipeline for {lead_id} ({case['url']})")
        enrich_email_pipeline(None, str(lead_id), str(ws_id))
        
        # 4. Refresh DB and Verify
        db.expire_all()
        
        # Verify EnrichmentState
        updated_state = db.scalar(select(EnrichmentState).where(EnrichmentState.raw_lead_id == lead_id))
        print(f"-> EnrichmentState.email_status: {updated_state.email_status}")
        
        # Verify EvidenceRecords
        evidence_records = db.execute(
            select(EvidenceRecord)
            .where(EvidenceRecord.raw_lead_id == lead_id)
            .where(EvidenceRecord.evidence_type == 'EMAIL')
        ).scalars().all()
        
        print(f"-> Database EvidenceRecord rows created: {len(evidence_records)}")
        
        for idx, ev in enumerate(evidence_records):
            print(f"   [Row {idx+1}]")
            print(f"      email (from details): {ev.details.get('email', 'N/A') if ev.details else 'N/A'}")
            print(f"      evidence_type: {ev.evidence_type}")
            print(f"      classification: {ev.classification}")
            print(f"      source URL: {ev.source}")
            print(f"      domain_match: {ev.details.get('domain_match') if ev.details else 'N/A'}")
            print(f"      verification result (status): {ev.status}")
            print(f"      confidence_score: {ev.confidence_score}")
            print(f"      observed_at: {ev.details.get('observed_at') if ev.details else 'N/A'}")

        if len(evidence_records) > 0 and evidence_records[0].classification != "NO_PUBLIC_EMAIL_FOUND":
            primary = evidence_records[0]
            print(f"-> Primary email selection: {primary.details.get('email') if primary.details else 'N/A'} (Confidence {primary.confidence_score})")

        # Verify RawLead is unchanged
        current_lead = db.scalar(select(RawLead).where(RawLead.id == lead_id))
        is_unchanged = (
            current_lead.business_name == case["bname"] and 
            current_lead.phone == "555-0000" and
            current_lead.email is None
        )
        print(f"-> Confirmation that RawLead remained unchanged: {is_unchanged}")

    db.close()

if __name__ == "__main__":
    run_db_verification()



