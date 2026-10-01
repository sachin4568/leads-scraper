with open('backend/app/sources/osm_overpass.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    'timeout = httpx.Timeout(connect=4.0, read=25.0, write=10.0, pool=5.0)',
    'timeout = httpx.Timeout(10.0)'
)
with open('backend/app/sources/osm_overpass.py', 'w', encoding='utf-8') as f:
    f.write(text)
