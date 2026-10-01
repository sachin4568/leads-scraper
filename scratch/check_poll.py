
with open('frontend/app/operations/page.tsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'const intervalId = setInterval(async () => {' in line:
        for j in range(i, i+50):
            print(lines[j].rstrip())
        break

