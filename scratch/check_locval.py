
with open('frontend/app/operations/page.tsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'const res = await api.startScrape' in line:
        for j in range(i-20, i):
            print(lines[j].rstrip())
        break

