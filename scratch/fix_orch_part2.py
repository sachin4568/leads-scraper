import re
with open('backend/app/orchestration/discovery_orchestrator.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    # For _record_enrichment_evidence
    if "ev = self.db.scalar(" in line:
        line = line.replace("self.db.scalar", "db.scalar")
        if "with SessionLocal() as db:" not in ''.join(lines[i-5:i]):
            line = "        with SessionLocal() as db:\n    " + line
    
    if "self.db.add(ev)" in line:
        line = line.replace("self.db.add(ev)", "db.add(ev)\n                db.commit()")
        
    if "src_score = AdaptiveDiscoveryEngine.get_source_score(self.db, src)" in line:
        line = "            with SessionLocal() as db:\n                src_score = AdaptiveDiscoveryEngine.get_source_score(db, src)\n"
    if "q_score = AdaptiveDiscoveryEngine.get_query_score(self.db, q_term)" in line:
        line = "                    with SessionLocal() as db:\n                        q_score = AdaptiveDiscoveryEngine.get_query_score(db, q_term)\n"
        
    if "self.db.add(exec_log)" in line:
        line = "            with SessionLocal() as db:\n                db.add(exec_log)\n                db.commit()\n"
        
    if "raw_sheet = self.db.get(app_models.RawLeadSheet, self.job_state[\"id\"])" in line:
        line = "                with SessionLocal() as db:\n                    raw_sheet = db.get(app_models.RawLeadSheet, self.job_state[\"id\"])\n"
    
    if "self.db.scalar(" in line:
        line = line.replace("self.db.scalar(", "db.scalar(")
    if "self.db.add(" in line:
        line = line.replace("self.db.add(", "db.add(")
        
    if "canonical_lead, obs, l_state = self.resolver.process_observation(self.db, raw_lead)" in line:
        line = line.replace("self.db", "db")
        if "with SessionLocal() as db:" not in ''.join(lines[i-15:i]):
            line = "            with SessionLocal() as db:\n    " + line

    if "raw_sheet = self.db.get(" in line:
        line = line.replace("self.db.get", "db.get")
        
    new_lines.append(line)

with open('backend/app/orchestration/discovery_orchestrator.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print("done")
