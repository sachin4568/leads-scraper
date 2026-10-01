import uuid
import time
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.models import Base, ScrapeJob
from backend.app.orchestration.discovery_orchestrator import DiscoveryOrchestrator

def test_stale_connection():
    # Setup real sqlite file DB to simulate connections
    engine = create_engine("sqlite:///scratch/test_stale.db")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    
    job_id = uuid.uuid4()
    with SessionLocal() as db:
        job = ScrapeJob(
            id=job_id,
            workspace_id=uuid.uuid4(),
            niche="Test Stale",
            status="RUNNING",
            target_lead_count=10
        )
        db.add(job)
        db.commit()
        
    import backend.app.orchestration.discovery_orchestrator as orch_module
    orch_module.SessionLocal = SessionLocal
    
    orchestrator = DiscoveryOrchestrator(
        job_id=str(job_id),
        connectors={},
    )
    
    # We forcefully dispose the engine pool, rendering old connections stale
    print("Disposing engine pool to simulate stale connection...")
    engine.dispose()
    
    # Orchestrator should gracefully open a new connection and not crash
    orchestrator._update_job_progress(current_source="After Dispose", current_query="Recovery")
    
    with SessionLocal() as db:
        job = db.scalar(select(ScrapeJob).where(ScrapeJob.id == job_id))
        print(f"Recovered and updated! Current source: {job.current_source}")

if __name__ == '__main__':
    test_stale_connection()
