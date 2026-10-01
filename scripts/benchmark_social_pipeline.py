import uuid
from sqlalchemy import select
from datetime import datetime, UTC

from backend.app.database import SessionLocal
from backend.app.models import RawLead, EvidenceRecord, EnrichmentState, Workspace, RawLeadSheet
from backend.app.enrichment.social_pipeline import enrich_social_pipeline

def run_db_verification():
    print("Initializing Real-World Database Verification for Phase 4 Social Pipeline...")
    db = SessionLocal()
    
    # 1. Create a Workspace and Sheet
    ws_id = uuid.uuid4()
    ws = Workspace(id=ws_id, name="Phase 4 Real Verification Workspace")
    db.add(ws)
    db.flush()
    
    sheet_id = uuid.uuid4()
    sheet = RawLeadSheet(id=sheet_id, workspace_id=ws_id, name="Real Social Sheet", niche="tech", sheet_number=1)
    db.add(sheet)
    db.commit()

    cases = [
        {
            "code": "A",
            "name": "Real business with Instagram profile (Django Software Foundation)",
            "url": "https://www.djangoproject.com",
            "bname": "Django Software Foundation",
            "raw_data": {
                "ig_link": "https://www.instagram.com/djangoproject"
            }
        },
        {
            "code": "B",
            "name": "Real business with Facebook profile (FSF)",
            "url": "https://www.fsf.org",
            "bname": "Free Software Foundation",
            "raw_data": {
                "fb_link": "https://www.facebook.com/fsf.org"
            }
        },
        {
            "code": "C",
            "name": "Real business with both IG and FB (EFF)",
            "url": "https://www.eff.org",
            "bname": "Electronic Frontier Foundation",
            "raw_data": {
                "ig_link": "https://www.instagram.com/efforg",
                "fb_link": "https://www.facebook.com/eff.org"
            }
        },
        {
            "code": "D",
            "name": "Business with no discoverable social profile",
            "url": "https://example.com",
            "bname": "Acme Corp Example",
            "raw_data": {}
        },
        {
            "code": "E",
            "name": "Invalid post/reel URL",
            "url": "https://www.invalidpost.com",
            "bname": "Invalid Post Business",
            "raw_data": {
                "ig_link": "https://www.instagram.com/p/C123456789/"
            }
        },
        {
            "code": "F",
            "name": "Profile with insufficient identity evidence",
            "url": "https://www.smithplumbinguk.co.uk",
            "bname": "Smith Plumbing UK Limited",
            "raw_data": {
                "ig_link": "https://www.instagram.com/randomplumber99"
            }
        },
        {
            "code": "G",
            "name": "Platform access blocked / login redirect",
            "url": "https://www.privatebiz.com",
            "bname": "Private Business Ltd",
            "raw_data": {
                "ig_link": "https://www.instagram.com/accounts/login/"
            }
        }
    ]
    
    benchmark_reports = []
    
    for case in cases:
        print(f"\n==================================================")
        print(f"Executing Case [{case['code']}]: {case['name']}")
        
        # 1. Create RawLead
        lead_id = uuid.uuid4()
        lead = RawLead(
            id=lead_id,
            sheet_id=sheet_id,
            business_name=case["bname"],
            location="Benchmark City",
            phone="555-0199",
            raw_data=case["raw_data"]
        )
        db.add(lead)
        db.flush()
        
        # 2. Simulate Phase 2 Website Evidence
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

        # 3. Execute ACTUAL Production Task
        print(f"-> Calling enrich_social_pipeline for RawLead {lead_id}")
        enrich_social_pipeline(None, str(lead_id), str(ws_id))
        
        # 4. Read real DB persisted records
        db.expire_all()
        
        updated_state = db.scalar(select(EnrichmentState).where(EnrichmentState.raw_lead_id == lead_id))
        evidence_records = db.execute(
            select(EvidenceRecord)
            .where(EvidenceRecord.raw_lead_id == lead_id)
            .where(EvidenceRecord.evidence_type == 'SOCIAL_PROFILE')
        ).scalars().all()
        
        current_lead = db.scalar(select(RawLead).where(RawLead.id == lead_id))
        raw_lead_unchanged = (
            current_lead.business_name == case["bname"] and 
            current_lead.phone == "555-0199"
        )

        report_entry = {
            "code": case["code"],
            "business": case["bname"],
            "instagram_status": updated_state.instagram_status,
            "facebook_status": updated_state.facebook_status,
            "evidence_count": len(evidence_records),
            "evidence_details": [],
            "raw_lead_unchanged": raw_lead_unchanged
        }

        for ev in evidence_records:
            report_entry["evidence_details"].append({
                "field": ev.field_name,
                "evidence_type": ev.evidence_type,
                "classification": ev.classification,
                "status": ev.status,
                "source_url": ev.source, # Full complete source URL
                "source_len": len(ev.source),
                "details": ev.details
            })

        benchmark_reports.append(report_entry)
        
        print(f"-> State: IG={updated_state.instagram_status}, FB={updated_state.facebook_status}")
        print(f"-> EvidenceRecords Created: {len(evidence_records)}")
        print(f"-> RawLead Unchanged: {raw_lead_unchanged}")

    db.close()
    return benchmark_reports

if __name__ == "__main__":
    run_db_verification()
