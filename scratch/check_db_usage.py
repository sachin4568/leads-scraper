
with open('backend/app/orchestration/discovery_orchestrator.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
count = 0
for line in lines:
    if 'self.db.' in line:
        count += 1
print(f'self.db is used {count} times.')

