
with open('backend/app/orchestration/discovery_orchestrator.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'def stage_1_discover_viable_candidates(self)' in line:
        for j in range(i, i+70):
            print(lines[j].rstrip())
        break

