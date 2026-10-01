with open('backend/app/sources/osm_overpass.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    'self.user_agent = user_agent or getattr(get_settings(), "osm_user_agent", DEFAULT_OSM_USER_AGENT)',
    'self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"'
)
with open('backend/app/sources/osm_overpass.py', 'w', encoding='utf-8') as f:
    f.write(text)
