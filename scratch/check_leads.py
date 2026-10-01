from backend.app.database import SessionLocal
from backend.app.models import RawLeadSheet, RawLead

db = SessionLocal()
sheet = db.query(RawLeadSheet).filter(RawLeadSheet.id == '851193ca-3448-4475-a152-1f41c0044f37').first()
leads = db.query(RawLead).filter(RawLead.sheet_id == '851193ca-3448-4475-a152-1f41c0044f37').count()
if sheet:
    print(f"Sheet found! Discovered: {sheet.discovered_count} Scraped: {sheet.leads_scraped}")
    print(f"RawLead rows: {leads}")
else:
    print("No sheet")
