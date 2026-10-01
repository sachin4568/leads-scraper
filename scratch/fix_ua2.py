with open('backend/app/sources/osm_overpass.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    'self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"',
    'self.user_agent = "python-httpx/0.27.0"'
)
with open('backend/app/sources/osm_overpass.py', 'w', encoding='utf-8') as f:
    f.write(text)
