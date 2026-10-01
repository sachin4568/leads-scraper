
with open('frontend/app/operations/page.tsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'const restoreActiveJob = async () =>' in line:
        for j in range(i+50, i+100):
            print(lines[j].rstrip())
        break

