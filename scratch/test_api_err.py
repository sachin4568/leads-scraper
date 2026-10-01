
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.models import Workspace
db = SessionLocal()
ws = db.query(Workspace).first()
client = TestClient(app)
payload = {'niche': 'Medspa', 'city': 'Manchester', 'country': 'UK', 'target_lead_count': 5}
resp = client.post('/api/v1/scrape-jobs', json=payload, headers={'x-workspace-id': str(ws.id)})
print(resp.json())

