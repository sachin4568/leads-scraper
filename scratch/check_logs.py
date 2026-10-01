from backend.app.database import SessionLocal
from backend.app.models import ScrapeJobExecutionLog
from sqlalchemy import select

with SessionLocal() as db:
    logs = db.scalars(select(ScrapeJobExecutionLog).order_by(ScrapeJobExecutionLog.created_at.desc()).limit(20)).all()
    for l in logs:
        print(f"{l.created_at} - {l.level}: {l.message_key} - {l.details}")
