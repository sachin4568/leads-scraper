import uuid
from backend.app.database import SessionLocal
from backend.app.models import ScrapeJob, Workspace
from backend.app.worker import execute_scrape_job

db = SessionLocal()
ws = db.query(Workspace).first()
if not ws:
    ws = Workspace(name="Test Workspace")
    db.add(ws)
    db.commit()
    db.refresh(ws)

# Create a test scrape job for HVAC in New York City with target=3
job = ScrapeJob(
    workspace_id=ws.id,
    niche="HVAC",
    country="United States",
    region="New York",
    state="New York City",
    target_lead_count=3,
    sources=["google_maps"],
    status="PENDING",
)
db.add(job)
db.commit()
db.refresh(job)

print(f"Created Test Job {job.id}. Starting execution...")
execute_scrape_job(None, str(job.id))

db.refresh(job)
print("=== JOB EXECUTION FINISHED ===")
print("Final Status:", job.status)
print("Error Message:", job.error_message)
print("Completion Reason:", job.completion_reason)
print("Leads Scraped:", job.leads_scraped)
print("Discovered:", job.discovered_count)
print("Valid:", job.valid_count)
