from backend.app.database import SessionLocal
from backend.app.models import ScrapeJob
import uuid

db = SessionLocal()
job = db.query(ScrapeJob).filter(ScrapeJob.id == '851193ca-3448-4475-a152-1f41c0044f37').first()
if job:
    print(f"Status: {job.status}")
    print(f"Error: {job.error_message}")
