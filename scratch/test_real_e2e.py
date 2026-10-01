from backend.app.database import SessionLocal
from backend.app.models import ScrapeJob
from backend.app.worker import execute_scrape_job
import uuid
import threading
import time

def run_real_e2e_test():
    db = SessionLocal()
    job_id = uuid.uuid4()
    job = ScrapeJob(
        id=job_id,
        workspace_id=uuid.uuid4(),
        niche="Medspa",
        country="United States",
        region="Alaska",
        state="Fairbanks",
        target_lead_count=5,
        sources=["osm_overpass"],
        status="RUNNING"
    )
    db.add(job)
    db.commit()
    db.close()
    
    print(f"Starting E2E test for job {job_id}")
    
    # Run in thread so we can simulate cancellation if we want
    def worker_thread():
        class DummyTask:
            request = None
            max_retries = 3
        execute_scrape_job(DummyTask(), str(job_id))
        
    t = threading.Thread(target=worker_thread)
    t.start()
    t.join()
    
    db = SessionLocal()
    finished_job = db.query(ScrapeJob).filter_by(id=job_id).first()
    print(f"Job finished with status: {finished_job.status}, leads: {finished_job.leads_scraped}, reason: {finished_job.completion_reason}")
    db.close()

if __name__ == '__main__':
    run_real_e2e_test()
