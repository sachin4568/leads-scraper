
with open("backend/app/orchestration/discovery_orchestrator.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if "def stage_1_discover_viable_candidates" in line:
        for j in range(i, i+150):
            if "self.action_queue.append(" in lines[j] or "while (" in lines[j] or "action = self.action_queue.pop" in lines[j]:
                print(f"{j}: {lines[j].rstrip()}")

