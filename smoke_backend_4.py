
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.models import ScrapeJob, Workspace
import time
from backend.app.orchestration.discovery_orchestrator import DiscoveryOrchestrator

db = SessionLocal()
ws = db.query(Workspace).first()
client = TestClient(app)

print('--- TEST A: TARGET 5 ---')
payload = {'niche': 'Plumbers', 'city': 'Manchester', 'region': 'England', 'country': 'UK', 'target_lead_count': 5}
resp = client.post('/api/v1/scrape-jobs', json=payload, headers={'x-workspace-id': str(ws.id)})
job_id = resp.json()['id']
print('1. UI selected target: 5')
print('2. Actual POST payload:', payload)
print('3. Created job ID:', job_id)
job = db.query(ScrapeJob).filter_by(id=job_id).first()
print('4. Database target_lead_count:', job.target_lead_count)

orchestrator = DiscoveryOrchestrator(db, job, {})
print('5. Worker target:', job.target_lead_count)
print('6. Orchestrator requested target:', orchestrator.metrics.requested)

orchestrator.run_discovery()
db.refresh(job)
print('7. Number of candidates discovered:', job.discovered_count)
print('8. Number niche-valid:', job.valid_count)
print('9. Number location-valid:', getattr(job, 'location_valid_count', 'N/A'))
print('10. Number persisted:', job.leads_scraped)
print('11. Final database status:', job.status)
print('12. completion_reason:', job.completion_reason)

print('\n--- TEST B: CANCEL ---')
job2 = ScrapeJob(workspace_id=ws.id, niche='Plumbers', city='Manchester', country='UK', target_lead_count=5)
db.add(job2)
db.commit()
job2.status = 'CANCELLED'
db.commit()
print('Job 2 Status:', job2.status)

print('\n--- TEST C: MANUAL HVAC ---')
payload_c = {'niche': 'HVAC', 'city': 'Manchester', 'region': 'England', 'country': 'UK', 'target_lead_count': 5}
resp_c = client.post('/api/v1/scrape-jobs', json=payload_c, headers={'x-workspace-id': str(ws.id)})
job_c = db.query(ScrapeJob).filter_by(id=resp_c.json()['id']).first()
print('Job C Niche:', job_c.niche)

print('\n--- TEST D: TARGET 10 ---')
payload_d = {'niche': 'Plumbers', 'city': 'Manchester', 'region': 'England', 'country': 'UK', 'target_lead_count': 10}
resp_d = client.post('/api/v1/scrape-jobs', json=payload_d, headers={'x-workspace-id': str(ws.id)})
job_d = db.query(ScrapeJob).filter_by(id=resp_d.json()['id']).first()
orch_d = DiscoveryOrchestrator(db, job_d, {})
orch_d.run_discovery()
db.refresh(job_d)
print('Test D Target:', job_d.target_lead_count)
print('Test D Leads Scraped:', job_d.leads_scraped)
print('Test D Status:', job_d.status)
print('Test D Reason:', job_d.completion_reason)

