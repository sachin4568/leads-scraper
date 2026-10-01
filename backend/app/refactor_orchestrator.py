import os

content = ''
with open('backend/app/orchestration/discovery_orchestrator.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add SessionLocal import
if 'SessionLocal' not in content:
    content = content.replace('from sqlalchemy.orm import Session\n', 'from sqlalchemy.orm import Session\nfrom backend.app.database import SessionLocal\n')

# Replace __init__ and add helper methods
init_pattern = '''    def __init__(
        self,
        db: Session,
        job: ScrapeJob,
        connectors: dict[str, SourceConnector],
        max_request_budget: int = 60,
    ) -> None:
        self.db = db
        self.job = job
        self.connectors = connectors'''

new_init = '''    def __init__(
        self,
        job_id: str,
        connectors: dict[str, SourceConnector],
        max_request_budget: int = 60,
    ) -> None:
        self.job_id = job_id
        self.connectors = connectors
        
        with SessionLocal() as db:
            from backend.app.models import ScrapeJob
            job = db.scalar(select(ScrapeJob).where(ScrapeJob.id == self.job_id))
            if not job:
                raise ValueError(f"Job {self.job_id} not found")
            self.job_state = {
                "id": job.id,
                "workspace_id": job.workspace_id,
                "niche": job.niche,
                "target_lead_count": job.target_lead_count,
                "country": job.country,
                "region": job.region,
                "state": job.state,
                "enrichments": job.enrichments,
                "sources": job.sources,
                "service": job.service,
                "leads_scraped": job.leads_scraped or 0,
                "progress_percent": job.progress_percent or 0.0,
                "status": job.status,
                "discovered_count": job.discovered_count or 0,
                "valid_count": job.valid_count or 0,
            }

    def _is_job_cancelled(self) -> bool:
        with SessionLocal() as db:
            from backend.app.models import ScrapeJob
            job = db.scalar(select(ScrapeJob).where(ScrapeJob.id == self.job_id))
            if job and job.status in ("STOPPED_SAVED", "CANCELLED"):
                return True
            return False

    def _update_job_progress(self, current_source: str = None, current_query: str = None) -> None:
        with SessionLocal() as db:
            from backend.app.models import ScrapeJob, RawLeadSheet
            job = db.scalar(select(ScrapeJob).where(ScrapeJob.id == self.job_id))
            if not job:
                return
            job.leads_scraped = self.job_state["leads_scraped"]
            job.progress_percent = self.job_state["progress_percent"]
            job.discovered_count = self.job_state["discovered_count"]
            job.valid_count = self.job_state["valid_count"]
            
            if current_source:
                job.current_source = current_source
            if current_query:
                job.current_query = current_query
                
            raw_sheet = db.get(RawLeadSheet, job.id)
            if raw_sheet:
                raw_sheet.leads_scraped = job.leads_scraped
                raw_sheet.discovered_count = job.discovered_count
                raw_sheet.valid_count = job.valid_count
                raw_sheet.progress_percent = job.progress_percent
                if current_source:
                    raw_sheet.current_source = current_source
                    
            db.commit()
            
            publish_job_progress(
                str(job.id),
                {
                    "event_type": "JOB_PROGRESS_UPDATE",
                    "job_id": str(job.id),
                    "status": job.status,
                    "leads_scraped": job.leads_scraped,
                    "target_lead_count": job.target_lead_count,
                    "progress_percent": job.progress_percent,
                    "discovered": job.discovered_count,
                    "valid": job.valid_count,
                },
            )'''

content = content.replace(init_pattern, new_init)

# Replace target = job.target_lead_count or 100
content = content.replace("target = job.target_lead_count or 100", "target = self.job_state.get('target_lead_count') or 100")

# Update references to self.job.xxx
# Example: self.job.workspace_id -> self.job_state['workspace_id']
# For safe replacement, we'll replace common properties used in Orchestrator.
job_props = [
    'workspace_id', 'niche', 'target_lead_count', 'country', 'region', 
    'state', 'enrichments', 'sources', 'service', 'leads_scraped', 
    'progress_percent', 'status', 'discovered_count', 'valid_count', 'id'
]
for prop in job_props:
    content = content.replace(f'self.job.{prop}', f'self.job_state["{prop}"]')

# Remove self.db.refresh(self.job)
content = content.replace('self.db.refresh(self.job_state["id"])', '') # won't match
content = content.replace('self.db.refresh(self.job)', '') # wait, the previous loop replaced self.job.id, not self.job!
# Actually, wait, there is `self.db.refresh(self.job)` in the code. We can just replace it.
content = content.replace('self.db.refresh(self.job)', '')

# Handle self.job.current_source and current_query updates which were directly modified.
# Example: self.job.current_source = f"Stage 1/4..." 
# We'll replace these with assignments to local vars and call _update_job_progress
# Wait, let's just make it simple. Keep it as string replace if possible.

with open('backend/app/orchestration/discovery_orchestrator.py', 'w', encoding='utf-8') as f:
    f.write(content)
