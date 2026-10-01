import httpx
q = '[out:json][timeout:35];(node["name"~"Mechanic", i](52.41,-1.87,52.49,-1.79););out center;'
res = httpx.post('https://overpass-api.de/api/interpreter', data={'data': q})
print("With , i:", res.status_code)

q2 = '[out:json][timeout:35];(node["name"~"Mechanic",i](52.41,-1.87,52.49,-1.79););out center;'
res2 = httpx.post('https://overpass-api.de/api/interpreter', data={'data': q2})
print("With ,i:", res2.status_code)

q3 = '[out:json][timeout:35];(node["name"~"Mechanic"](52.41,-1.87,52.49,-1.79););out center;'
res3 = httpx.post('https://overpass-api.de/api/interpreter', data={'data': q3})
print("Without i:", res3.status_code)
