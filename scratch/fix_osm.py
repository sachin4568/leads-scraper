with open('backend/app/sources/osm_overpass.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
'''FALLBACK_OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
]''',
'''FALLBACK_OVERPASS_ENDPOINTS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
]'''
)

text = text.replace('timeout = httpx.Timeout(connect=5.0, read=45.0, write=10.0, pool=5.0)', 'timeout = httpx.Timeout(connect=4.0, read=25.0, write=10.0, pool=5.0)')

with open('backend/app/sources/osm_overpass.py', 'w', encoding='utf-8') as f:
    f.write(text)
