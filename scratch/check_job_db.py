from backend.app.database import SessionLocal
from backend.app.models import ScrapeJob
from sqlalchemy import select
db = SessionLocal()
job = db.scalar(select(ScrapeJob).where(ScrapeJob.id == '9b8161dd-f619-4048-9c14-8864bb5d725e'))
print(f"Status in DB: {job.status}")
print(f"Reason: {job.completion_reason}")
