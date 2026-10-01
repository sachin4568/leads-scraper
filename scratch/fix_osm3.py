with open('backend/app/sources/osm_overpass.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    'self.seen_queries = set() or getattr(get_settings(), "osm_user_agent", DEFAULT_OSM_USER_AGENT)',
    'self.user_agent = user_agent or getattr(get_settings(), "osm_user_agent", DEFAULT_OSM_USER_AGENT)\n        self.seen_queries = set()'
)

with open('backend/app/sources/osm_overpass.py', 'w', encoding='utf-8') as f:
    f.write(text)
