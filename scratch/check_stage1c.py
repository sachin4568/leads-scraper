
with open('backend/app/orchestration/discovery_orchestrator.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'action_scope = target_loc_scope' in line:
        for j in range(i+30, i+90):
            if j < len(lines):
                print(lines[j].rstrip())
        break

