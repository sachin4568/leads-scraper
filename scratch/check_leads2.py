from backend.app.database import SessionLocal
from backend.app.models import RawLeadSheet, RawLead

db = SessionLocal()
sheet = db.query(RawLeadSheet).filter(RawLeadSheet.id == '94b8262d-4b10-406f-a7ee-4fa9074fab49').first()
leads = db.query(RawLead).filter(RawLead.sheet_id == '94b8262d-4b10-406f-a7ee-4fa9074fab49').count()
if sheet:
    print(f"Sheet found! Discovered: {sheet.discovered_count} Scraped: {sheet.leads_scraped}")
    print(f"RawLead rows: {leads}")
    print(f"Status: {sheet.status}")
else:
    print("No sheet")
