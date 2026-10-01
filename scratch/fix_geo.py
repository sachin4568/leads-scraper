with open('backend/app/sources/geo_utils.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    'query_str = f"{location}, {region}, {country_code}" if region else f"{location}, {country_code}"',
    '''query_parts = [location]
            if region: query_parts.append(region)
            if country_code: query_parts.append(country_code)
            query_str = ", ".join(query_parts)'''
)

with open('backend/app/sources/geo_utils.py', 'w', encoding='utf-8') as f:
    f.write(text)
