
with open("backend/app/orchestration/discovery_orchestrator.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if "class DiscoveryOrchestrator" in line:
        for j in range(i, i+50):
            print(lines[j].rstrip())
        break

