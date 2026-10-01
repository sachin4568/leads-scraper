from backend.app.database import SessionLocal
from backend.app.models import RawLeadSheet, ScrapeJob, RawLead, Workspace
from backend.app.worker import enrich_raw_lead_task
import uuid
import time
from datetime import datetime, UTC
from sqlalchemy import select

with SessionLocal() as db:
    job = db.scalar(select(ScrapeJob))
    sheet = db.scalar(select(RawLeadSheet))
    workspace = db.scalar(select(Workspace))
    if not sheet:
        print("No sheet found")
        # create one
        job = ScrapeJob(workspace_id=workspace.id, niche="Medspa", target_lead_count=5)
        db.add(job)
        db.commit()
        sheet = RawLeadSheet(workspace_id=workspace.id, name="Test", niche="Medspa")
        db.add(sheet)
        db.commit()

    lead_id_1 = uuid.uuid4()
    l1 = RawLead(
        id=lead_id_1,
        sheet_id=sheet.id,
        business_name="Fairbanks Medical Spa",
        website="https://www.google.com",
        email=None,
        phone="+1 907-555-0199",
        location="123 Main St, Fairbanks, AK",
        source="google_maps",
        created_at=datetime.now(UTC)
    )
    lead_id_2 = uuid.uuid4()
    l2 = RawLead(
        id=lead_id_2,
        sheet_id=sheet.id,
        business_name="Arctic Wellness No Web",
        website=None,
        email=None,
        phone="+1 907-555-0200",
        location="456 Elm St, Fairbanks, AK",
        source="google_maps",
        created_at=datetime.now(UTC)
    )
    db.add(l1)
    db.add(l2)
    db.commit()
    print(f"Added {lead_id_1} and {lead_id_2}")
    
    enrich_raw_lead_task.delay(str(lead_id_1), "website_dev")
    enrich_raw_lead_task.delay(str(lead_id_2), "website_dev")
    enrich_raw_lead_task.delay(str(lead_id_1), "website_seo")
    
    print("Enqueued!")
