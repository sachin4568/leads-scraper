import re

with open('backend/app/orchestration/discovery_orchestrator.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace all occurrences of self.db.refresh(self.job) ... with if self._is_job_cancelled():
text = re.sub(
    r'self\.db\.refresh\(self\.job\)\s*if self\.job_state\["status"\] in \("STOPPED_SAVED", "CANCELLED"\):',
    r'if self._is_job_cancelled():',
    text
)
text = re.sub(
    r'self\.db\.refresh\(self\.job\)\s*if getattr\(self\.job, \'status\', None\) in \("STOPPED_SAVED", "CANCELLED"\):',
    r'if self._is_job_cancelled():',
    text
)

# 1. _record_enrichment_evidence
text = re.sub(
    r'ev = self\.db\.scalar\((.*?)\)\s+if not ev:\s+ev = EvidenceRecord\((.*?)\)\s+self\.db\.add\(ev\)',
    r'''with SessionLocal() as db:
            ev = db.scalar(\1)
            if not ev:
                ev = EvidenceRecord(\2)
                db.add(ev)
                db.commit()''',
    text,
    flags=re.DOTALL
)

# 2. AdaptiveDiscoveryEngine get_source_score
text = text.replace(
    'src_score = AdaptiveDiscoveryEngine.get_source_score(self.db, src)',
    '''with SessionLocal() as db:
                src_score = AdaptiveDiscoveryEngine.get_source_score(db, src)'''
)

# 3. AdaptiveDiscoveryEngine get_query_score
text = text.replace(
    'q_score = AdaptiveDiscoveryEngine.get_query_score(self.db, q_term)',
    '''with SessionLocal() as db:
                        q_score = AdaptiveDiscoveryEngine.get_query_score(db, q_term)'''
)

# 4. exec_log ProviderExecutionLog
text = re.sub(
    r'exec_log = ProviderExecutionLog\((.*?)\)\s+self\.db\.add\(exec_log\)',
    r'''exec_log = ProviderExecutionLog(\1)
            with SessionLocal() as db:
                db.add(exec_log)
                db.commit()''',
    text,
    flags=re.DOTALL
)

# 5. finalize_discovery db scalar
text = text.replace(
    '''persisted_count = self.db.scalar(
            select(func.count(Lead.id)).where(Lead.job_id == self.job_state["id"])
        ) or 0''',
    '''with SessionLocal() as db:
            persisted_count = db.scalar(
                select(func.count(Lead.id)).where(Lead.job_id == self.job_state["id"])
            ) or 0'''
)

# 6. finalize_discovery raw_sheet update
text = re.sub(
    r'raw_sheet = self\.db\.get\(app_models\.RawLeadSheet, self\.job_state\["id"\]\)\s+if raw_sheet:\s+raw_sheet\.status = self\.job_state\["status"\]\s+raw_sheet\.completion_reason = self\.job_state\["completion_reason"\]\s+self\.db\.commit\(\)',
    r'''with SessionLocal() as db:
            raw_sheet = db.get(app_models.RawLeadSheet, self.job_state["id"])
            if raw_sheet:
                raw_sheet.status = self.job_state["status"]
                raw_sheet.completion_reason = self.job_state["completion_reason"]
                db.commit()''',
    text,
    flags=re.DOTALL
)

with open('backend/app/orchestration/discovery_orchestrator.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Phase 1 done")
