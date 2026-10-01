
from backend.app.database import SessionLocal
from backend.app.models import ScrapeJob
from sqlalchemy import update

db = SessionLocal()
ghost_jobs = db.query(ScrapeJob).filter(ScrapeJob.status.in_(['RUNNING', 'PENDING'])).all()
for j in ghost_jobs:
    print(f'Ghost job: {j.id} / {j.niche}')
    j.status = 'FAILED'
    j.error_message = 'Ghost job cleaned up'
    j.completion_reason = 'UNKNOWN_ERROR'
db.commit()
print('Cleaned up ghost jobs.')

