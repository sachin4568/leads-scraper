
with open('backend/app/orchestration/discovery_orchestrator.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'def run_discovery(self)' in line:
        for j in range(i, i+100):
            print(lines[j].rstrip())
        break

