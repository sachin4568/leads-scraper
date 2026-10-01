
with open("backend/app/orchestration/discovery_orchestrator.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if "STAGE_1_CANDIDATE_DISCOVERED" in line:
        for j in range(i+10, i+60):
            if j < len(lines):
                print(lines[j].rstrip())
        break

