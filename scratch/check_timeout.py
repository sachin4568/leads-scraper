
with open('backend/app/sources/osm_overpass.py', 'r') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'with httpx.Client(timeout=timeout)' in line:
        for j in range(max(0, i-25), i):
            print(lines[j].rstrip())
        break

