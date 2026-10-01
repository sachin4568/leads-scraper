import httpx
q = '[out:json][timeout:35];(node["shop"="car_repair"](52.41,-1.87,52.49,-1.79););out center;'
headers1 = {'User-Agent': 'LeadIntelligence/1.0 (test)'}
headers2 = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 LeadIntelligence/1.0",
    "Accept": "*/*",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}

for i, h in enumerate([headers1, headers2]):
    res = httpx.post('https://overpass-api.de/api/interpreter', data={'data': q}, headers=h)
    print(f"Headers {i} - status: {res.status_code}")
