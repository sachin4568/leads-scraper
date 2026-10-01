
from backend.app.database import SessionLocal
from backend.app.models import ScrapeJob
from backend.app.orchestration.discovery_orchestrator import DiscoveryOrchestrator
from backend.app.worker import get_connectors

db = SessionLocal()
job = db.query(ScrapeJob).filter_by(id='0c1afd9b-3d9e-4bb8-8698-66a3f4af7de0').first()
if job:
    connectors = get_connectors()
    orchestrator = DiscoveryOrchestrator(db=db, job=job, connectors=connectors, max_request_budget=60)
    orchestrator.run_discovery()
else:
    print('Job not found.')

