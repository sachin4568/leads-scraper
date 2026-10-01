from backend.app.sources.osm_overpass import OSMOverpassConnector
connector = OSMOverpassConnector()
bbox = [64.779636, 64.877948, -147.821053, -147.524124]

print("Medspa:")
print(connector._build_overpass_query("Medspa", bbox))

print("Medspas:")
print(connector._build_overpass_query("Medspas", bbox))

print("Medical Spa:")
print(connector._build_overpass_query("Medical Spa", bbox))
