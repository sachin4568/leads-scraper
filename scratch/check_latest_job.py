
from backend.app.database import SessionLocal
from backend.app.models import ScrapeJob, ScrapeJobExecutionLog
from sqlalchemy import desc

db = SessionLocal()
latest_job = db.query(ScrapeJob).order_by(desc(ScrapeJob.created_at)).first()
if latest_job:
    print(f'Job ID: {latest_job.id}, Status: {latest_job.status}, Niche: {latest_job.niche}, Target: {latest_job.target_lead_count}')
    logs = db.query(ScrapeJobExecutionLog).filter_by(job_id=latest_job.id).order_by(ScrapeJobExecutionLog.created_at).all()
    for l in logs:
        print(f'[{l.created_at}] {l.event_type}: {l.message}')
else:
    print('No jobs found.')

