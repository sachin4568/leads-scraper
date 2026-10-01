from backend.app.database import SessionLocal
from backend.app.models import RawLeadSheet, RawLead

db = SessionLocal()
sheet = db.query(RawLeadSheet).filter(RawLeadSheet.id == 'f7c1c63e-f078-4c50-a6c2-dd236d7abe64').first()
leads = db.query(RawLead).filter(RawLead.sheet_id == 'f7c1c63e-f078-4c50-a6c2-dd236d7abe64').count()
if sheet:
    print(f"Sheet found! Discovered: {sheet.discovered_count} Scraped: {sheet.leads_scraped}")
    print(f"RawLead rows: {leads}")
    print(f"Status: {sheet.status}")
else:
    print("No sheet")
