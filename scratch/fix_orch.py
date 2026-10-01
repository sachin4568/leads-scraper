import re

filepath = 'backend/app/orchestration/discovery_orchestrator.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Replace remaining self.db.commit() usages directly
content = re.sub(r'self\.db\.commit\(\)', '', content)
content = re.sub(r'self\.db\.flush\(\)', 'db.flush()', content)

# 2. Fix self.job references
content = re.sub(r'self\.job\.current_source = (.*?)\n', r'self._update_job_progress(current_source=\1)\n', content)
content = re.sub(r'self\.job\.current_query = (.*?)\n', r'self._update_job_progress(current_query=\1)\n', content)
content = re.sub(r'self\.job\.progress_percent = (.*?)\n', r'self._update_job_progress(progress_percent=\1)\n', content)
content = re.sub(r'self\.job\.leads_scraped = (.*?)\n', r'self._update_job_progress(leads_scraped=\1)\n', content)

# 3. Replace self.db usage in stage 4 
content = content.replace("self.db.add(persisted_lead)", "db.add(persisted_lead)")
content = content.replace("self.db.scalar(", "db.scalar(")
content = content.replace("self.db.get(", "db.get(")
content = content.replace("self.db.add(", "db.add(")

# Fix process_observation
content = content.replace("process_observation(self.db,", "process_observation(db,")
content = content.replace("get_source_score(self.db,", "get_source_score(db,")
content = content.replace("get_query_score(self.db,", "get_query_score(db,")

# 4. Wrap stage 4 in a db transaction
content = content.replace('''
        for idx, item in enumerate(qualified_candidates):
            
            if self.job_state["status"] in ("STOPPED_SAVED", "CANCELLED"):
                return
''', '''
        with SessionLocal() as db:
            for idx, item in enumerate(qualified_candidates):
                if self._is_job_cancelled(): return
''')

# Write back
with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
