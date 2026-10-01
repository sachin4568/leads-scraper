with open('backend/app/sources/__init__.py', 'r', encoding='utf-8') as f:
    text = f.read()

if 'NominatimConnector' not in text:
    text = text.replace(
        'from backend.app.sources.yelp import YelpConnector',
        'from backend.app.sources.yelp import YelpConnector\nfrom backend.app.sources.nominatim import NominatimConnector'
    )
    text = text.replace(
        '"yelp": YelpConnector(),',
        '"yelp": YelpConnector(),\n        "nominatim": NominatimConnector(),'
    )
    with open('backend/app/sources/__init__.py', 'w', encoding='utf-8') as f:
        f.write(text)
