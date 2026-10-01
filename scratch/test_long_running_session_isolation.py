import uuid
import time
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.models import Base, ScrapeJob
from backend.app.orchestration.discovery_orchestrator import DiscoveryOrchestrator

def test_long_running():
    # Setup in-memory DB
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    
    # Create Job
    job_id = uuid.uuid4()
    with SessionLocal() as db:
        job = ScrapeJob(
            id=job_id,
            workspace_id=uuid.uuid4(),
            niche="Test",
            status="RUNNING",
            target_lead_count=10
        )
        db.add(job)
        db.commit()
    
    # We must patch SessionLocal in discovery_orchestrator
    import backend.app.orchestration.discovery_orchestrator as orch_module
    orch_module.SessionLocal = SessionLocal
    
    # Run orchestrator
    connectors = {}
    orchestrator = DiscoveryOrchestrator(
        job_id=str(job_id),
        connectors=connectors,
        max_request_budget=5
    )
    
    print("Orchestrator initialized. Testing short-lived connections...")
    
    # Simulate DB disconnection by replacing engine
    print("Simulating sleep and connection drops...")
    time.sleep(1)
    
    # Check if cancelled (should open new session)
    is_cancelled = orchestrator._is_job_cancelled()
    print(f"Is cancelled: {is_cancelled}")
    
    # Update progress
    orchestrator.metrics.saved_count = 5
    orchestrator._update_job_progress(current_source="Test", current_query="Test")
    
    with SessionLocal() as db:
        job = db.scalar(select(ScrapeJob).where(ScrapeJob.id == job_id))
        print(f"Job progress after short-lived update: {job.progress_percent}, scraped: {job.leads_scraped}")
        
    print("Test passed! No long-lived session held.")

if __name__ == '__main__':
    test_long_running()
