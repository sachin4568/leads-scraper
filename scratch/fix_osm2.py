with open('backend/app/sources/osm_overpass.py', 'r', encoding='utf-8') as f:
    text = f.read()

if 'self.seen_queries' not in text:
    text = text.replace('self.user_agent = user_agent', 'self.user_agent = user_agent\n        self.seen_queries = set()')
    
    execute_query_patch = '''    def _execute_query(self, query: str, category: str = "unknown") -> dict[str, Any]:
        if query in self.seen_queries:
            logger.info(f"[OSM Overpass] Skipping identical query for category '{category}'")
            return {"elements": []}
        self.seen_queries.add(query)'''
    text = text.replace('    def _execute_query(self, query: str, category: str = "unknown") -> dict[str, Any]:', execute_query_patch)

with open('backend/app/sources/osm_overpass.py', 'w', encoding='utf-8') as f:
    f.write(text)
