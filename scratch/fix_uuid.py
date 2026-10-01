import re

with open('backend/app/orchestration/discovery_orchestrator.py', 'r', encoding='utf-8') as f:
    content = f.read()
    
# Change self.job_id = job_id to self.job_id = uuid.UUID(job_id) if isinstance(job_id, str) else job_id
# Or just self.job_id = uuid.UUID(str(job_id))
content = content.replace("self.job_id = job_id", "import uuid\n        self.job_id = uuid.UUID(str(job_id))")

with open('backend/app/orchestration/discovery_orchestrator.py', 'w', encoding='utf-8') as f:
    f.write(content)
