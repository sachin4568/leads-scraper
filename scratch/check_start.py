
with open("backend/app/api.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if "def scrape_start_compat" in line:
        for j in range(i, i+50):
            if j < len(lines):
                print(lines[j].rstrip())
        break

