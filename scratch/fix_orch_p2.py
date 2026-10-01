import re

with open('backend/app/orchestration/discovery_orchestrator.py', 'r', encoding='utf-8') as f:
    text = f.read()

# I will just write a python script that replaces all self.db with db, and wraps the whole loops in with SessionLocal() as db:
# Wait, for Stage 1 (Raw Leads), there is a big block:
#                 # Immediately persist to RawLeadSheet
#                 raw_sheet = self.db.get(...)
text = re.sub(r'(# Immediately persist to RawLeadSheet.*?publish_job_progress\()', r'with SessionLocal() as db:\n                \1', text, flags=re.DOTALL)
text = text.replace('raw_sheet = self.db.get(app_models.RawLeadSheet', 'raw_sheet = db.get(app_models.RawLeadSheet')
text = text.replace('existing_raw_lead = self.db.scalar(', 'existing_raw_lead = db.scalar(')
text = text.replace('self.db.add(r_lead)', 'db.add(r_lead)\n                    db.commit()')

# Stage 4:
text = re.sub(r'(canonical_lead, obs, l_state = self\.resolver\.process_observation\(self\.db, raw_lead\).*?existing_raw_lead\.email = effective_email)', r'with SessionLocal() as db:\n                \1', text, flags=re.DOTALL)
text = text.replace('process_observation(self.db,', 'process_observation(db,')
text = text.replace('persisted_lead = self.db.scalar(', 'persisted_lead = db.scalar(')
text = text.replace('self.db.add(persisted_lead)', 'db.add(persisted_lead)')
text = text.replace('src_rec = self.db.scalar(', 'src_rec = db.scalar(')
text = text.replace('self.db.add(src_rec)', 'db.add(src_rec)')
text = text.replace('raw_sheet = self.db.get(', 'raw_sheet = db.get(')
text = text.replace('existing_raw_lead = self.db.scalar(', 'existing_raw_lead = db.scalar(')
text = text.replace('self.db.add(r_lead)', 'db.add(r_lead)\n                    db.commit()')

# ProviderExecutionLog
text = text.replace('self.db.add(exec_log)', 'with SessionLocal() as db:\n                db.add(exec_log)\n                db.commit()')

# EvidenceRecord
text = text.replace('ev = self.db.scalar(', 'with SessionLocal() as db:\n            ev = db.scalar(')
text = text.replace('self.db.add(ev)', 'db.add(ev)\n            db.commit()')

with open('backend/app/orchestration/discovery_orchestrator.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Done")
