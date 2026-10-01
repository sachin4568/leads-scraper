from backend.app.database import SessionLocal
from backend.app.models import ScrapeJob
import uuid

db = SessionLocal()
job = db.query(ScrapeJob).filter(ScrapeJob.id == 'edfcd295-e5a3-4e16-889b-74830dad7060').first()
if job:
    print(f"Status: {job.status}")
    print(f"Error: {job.error_message}")
    print(f"Target: {job.target_lead_count}")
    print(f"Scraped: {job.leads_scraped}")
    print(f"Completion Reason: {job.completion_reason}")
else:
    print("Not found")
