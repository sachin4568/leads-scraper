with open('backend/app/orchestration/discovery_orchestrator.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('raw_sheet = self.db.get(app_models.RawLeadSheet', 'with SessionLocal() as db:\n            raw_sheet = db.get(app_models.RawLeadSheet')
text = text.replace('db.commit()\n            db.commit()', 'db.commit()')

with open('backend/app/orchestration/discovery_orchestrator.py', 'w', encoding='utf-8') as f:
    f.write(text)
