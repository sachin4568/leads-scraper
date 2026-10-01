
with open('backend/app/sources/osm_overpass.py', 'r') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'def _build_overpass_query' in line:
        for j in range(i+30, i+45):
            print(lines[j].rstrip())
        break

