from backend.app.database import SessionLocal
from backend.app.models import ScrapeJob

db = SessionLocal()
job = db.query(ScrapeJob).filter(ScrapeJob.id == 'dbd1474e-1554-4647-8822-d45a172a7e70').first()
if job:
    print(f"Status: {job.status}")
    print(f"Error: {job.error_message}")
