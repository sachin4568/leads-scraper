
with open("backend/app/worker.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if "def execute_scrape_job" in line:
        for j in range(i, i+120):
            if j < len(lines):
                print(lines[j].rstrip())
        break

