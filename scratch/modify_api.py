with open('backend/app/api.py', 'r', encoding='utf-8') as f:
    text = f.read()

import_line = "from backend.app.schemas import ("
new_imports = "from backend.app.schemas import (\\n    ServiceOpportunityRead, RawLeadEvidenceRead, EnrichmentStatusResponse,"
if "ServiceOpportunityRead" not in text:
    text = text.replace(import_line, new_imports)

endpoints = '''

@router.get("/raw-leads/{raw_lead_id}/opportunities", response_model=list[ServiceOpportunityRead])
def get_raw_lead_opportunities(raw_lead_id: uuid.UUID, db: Session = Depends(get_db)):
    from backend.app.models import ServiceOpportunity
    return db.scalars(select(ServiceOpportunity).where(ServiceOpportunity.raw_lead_id == raw_lead_id)).all()

@router.get("/raw-leads/{raw_lead_id}/evidence", response_model=list[RawLeadEvidenceRead])
def get_raw_lead_evidence(raw_lead_id: uuid.UUID, db: Session = Depends(get_db)):
    from backend.app.models import EvidenceRecord
    return db.scalars(select(EvidenceRecord).where(EvidenceRecord.raw_lead_id == raw_lead_id)).all()

@router.get("/scrape-jobs/{job_id}/enrichment-status", response_model=EnrichmentStatusResponse)
def get_enrichment_status(job_id: uuid.UUID, db: Session = Depends(get_db)):
    from backend.app.models import EvidenceRecord, RawLead, ServiceOpportunity
    from sqlalchemy import func
    
    # Just basic counts for now
    subq = select(RawLead.id).where(RawLead.sheet_id == job_id)
    
    emails_found = db.scalar(
        select(func.count(EvidenceRecord.id))
        .where(EvidenceRecord.raw_lead_id.in_(subq), EvidenceRecord.field_name == "email")
    ) or 0
    
    websites_found = db.scalar(
        select(func.count(EvidenceRecord.id))
        .where(EvidenceRecord.raw_lead_id.in_(subq), EvidenceRecord.field_name == "website")
    ) or 0
    
    scored = db.scalar(
        select(func.count(ServiceOpportunity.id))
        .where(ServiceOpportunity.raw_lead_id.in_(subq))
    ) or 0
    
    return EnrichmentStatusResponse(
        emails_found=emails_found,
        websites_found=websites_found,
        opportunities_scored=scored
    )
'''
if "def get_raw_lead_opportunities" not in text:
    text += endpoints

with open('backend/app/api.py', 'w', encoding='utf-8') as f:
    f.write(text)
