from backend.app.database import SessionLocal
from backend.app.models import ScrapeJob
from sqlalchemy import desc

db = SessionLocal()
latest = db.query(ScrapeJob).order_by(desc(ScrapeJob.created_at)).first()
if latest:
    print(f"Latest Job: {latest.id}")
    print(f"Status: {latest.status}")
    print(f"Error: {latest.error_message}")
    print(f"Target: {latest.target_lead_count}")
    print(f"Created: {latest.created_at}")
else:
    print("No jobs found")
