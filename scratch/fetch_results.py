from backend.app.database import SessionLocal
from backend.app.models import RawLead, ServiceOpportunity, EvidenceRecord
from sqlalchemy import select

with SessionLocal() as db:
    leads = db.scalars(select(RawLead).order_by(RawLead.created_at.desc()).limit(2)).all()
    for l in leads:
        print(f"Lead: {l.business_name} (Email: {l.email})")
        opps = db.scalars(select(ServiceOpportunity).where(ServiceOpportunity.raw_lead_id == l.id)).all()
        for o in opps:
            print(f"  Opportunity: {o.service} - {o.status} ({o.opportunity_score}) - {o.reasons}")
            print(f"  Signals: {o.signals}")
        
        evs = db.scalars(select(EvidenceRecord).where(EvidenceRecord.raw_lead_id == l.id)).all()
        for e in evs:
            print(f"  Evidence: {e.field_name} - {e.status} - {e.details}")
