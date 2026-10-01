from backend.app.database import SessionLocal
from backend.app.models import ScrapeJob

db = SessionLocal()
jobs = db.query(ScrapeJob).filter(ScrapeJob.error_message == 'Ghost job cleaned up').all()
for j in jobs:
    print(f"Job: {j.id}, Created: {j.created_at}")
