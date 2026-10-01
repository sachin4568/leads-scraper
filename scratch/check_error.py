from backend.app.database import SessionLocal
from backend.app.models import ScrapeJob
import uuid

db = SessionLocal()
job = db.query(ScrapeJob).filter(ScrapeJob.id == '4b64d54b-7d6c-4027-b3b9-00043962b1f8').first()
if job:
    print(f"Status: {job.status}")
    print(f"Error: {job.error_message}")
    print(f"Target: {job.target_lead_count}")
