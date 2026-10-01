with open('backend/app/orchestration/discovery_orchestrator.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
indenting = False
for line in lines:
    if line.strip() == "with SessionLocal() as db:":
        if "Immediately persist" in "".join(lines): # we just check if it's the right place
            pass
    
    if line.startswith("                # Immediately persist to RawLeadSheet"):
        indenting = True
        
    if indenting:
        if line.startswith("                ") and not line.startswith("                    "):
            line = "    " + line
        if "db.commit()" in line and "    db.commit()" not in line: # actually db.commit() is indented
            pass
    if "publish_job_progress" in line and indenting:
        indenting = False
        
    new_lines.append(line)

with open('backend/app/orchestration/discovery_orchestrator.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
