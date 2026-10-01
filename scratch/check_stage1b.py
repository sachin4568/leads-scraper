
with open('backend/app/orchestration/discovery_orchestrator.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'action = self.action_queue.pop(0)' in line:
        for j in range(i, i+65):
            print(lines[j].rstrip())
        break

