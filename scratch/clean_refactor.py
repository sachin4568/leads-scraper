import re

with open('backend/app/orchestration/discovery_orchestrator.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Imports
if 'from backend.app.database import SessionLocal' not in content:
    content = content.replace('from sqlalchemy.orm import Session\n', 'from sqlalchemy.orm import Session\nfrom backend.app.database import SessionLocal\n')

# 2. Add Helper Methods and Modify __init__
init_regex = r"def __init__\(\s*self,\s*db: Session,\s*job: ScrapeJob,\s*connectors: dict\[str, SourceConnector\],\s*max_request_budget: int = 60,\s*\) -> None:.*?self\.connectors = connectors"

new_init = """def __init__(
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
            if not job:
                return True
            return job.status in ("STOPPED_SAVED", "CANCELLED")

    def _update_job_progress(self, current_source=None, current_query=None, progress_percent=None, leads_scraped=None, status=None, completion_reason=None, error_message=None):
        from backend.app.models import ScrapeJob
        from backend.app.websockets import publish_job_progress
        with SessionLocal() as db:
            job = db.scalar(select(ScrapeJob).where(ScrapeJob.id == self.job_id))
            if not job:
                return
            if current_source: job.current_source = current_source
            if current_query: job.current_query = current_query
            if progress_percent is not None: job.progress_percent = progress_percent
            if leads_scraped is not None: job.leads_scraped = leads_scraped
            if status is not None: job.status = status
            if completion_reason is not None: job.completion_reason = completion_reason
            if error_message is not None: job.error_message = error_message
            
            job.discovered_count = self.metrics.fetched_count
            job.valid_count = self.metrics.validated_count
            job.duplicate_count = self.metrics.duplicate_count
            job.fetched_count = getattr(job, 'fetched_count', 0) + self.metrics.fetched_count
            
            db.commit()
            
            publish_job_progress(
                str(self.job_id),
                {
                    "event_type": f"JOB_{job.status}",
                    "job_id": str(self.job_id),
                    "status": job.status,
                    "leads_scraped": job.leads_scraped,
                    "target_lead_count": self.metrics.requested,
                    "progress_percent": job.progress_percent,
                    "discovered": job.discovered_count,
                    "valid": job.valid_count,
                    "duplicates": job.duplicate_count,
                },
            )
"""
content = re.sub(init_regex, new_init, content, flags=re.DOTALL)

# Replace target = job.target_lead_count or 100
content = content.replace("target = job.target_lead_count or 100", "target = self.job_state.get('target_lead_count') or 100")

# Replace self.job references
content = re.sub(r'self\.job\.([a-zA-Z0-9_]+)', r'self.job_state["\1"]', content)

# Remove progress updating scattered code since we will use _update_job_progress
content = re.sub(r'self\.db\.commit\(\)', '', content)
content = re.sub(r'self\.db\.flush\(\)', 'db.flush()', content)

with open('backend/app/orchestration/discovery_orchestrator.py', 'w', encoding='utf-8') as f:
    f.write(content)
