
from backend.app.database import SessionLocal
from backend.app.models import ScrapeJob
from sqlalchemy import desc

db = SessionLocal()
jobs = db.query(ScrapeJob).order_by(desc(ScrapeJob.created_at)).limit(5).all()
for j in jobs:
    print(f'Job ID: {j.id}, Status: {j.status}, Niche: {j.niche}, Leads: {j.leads_scraped}, Discovered: {j.discovered_count}, Target: {j.target_lead_count}, Error: {j.error_message}, Reason: {j.completion_reason}')

