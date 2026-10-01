from backend.app.orchestration.discovery_orchestrator import DiscoveryOrchestrator
from backend.app.models import ScrapeJob
from backend.app.database import SessionLocal
import uuid

db = SessionLocal()
job = ScrapeJob(id=uuid.uuid4(), niche='Medspa', state='Fairbanks', region='Alaska', country='United States', target_lead_count=5, workspace_id=uuid.uuid4())
db.add(job)
db.commit()

orc = DiscoveryOrchestrator(str(job.id))
orc._build_initial_action_queue()
for a in orc.action_queue:
    print(a.provider, a.query)
