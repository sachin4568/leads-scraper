
with open("backend/app/orchestration/discovery_orchestrator.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if "def execute_discovery_action" in line:
        for j in range(i, i+70):
            if j < len(lines):
                print(lines[j].rstrip())
        break

