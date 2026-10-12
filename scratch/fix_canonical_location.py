with open('backend/app/ingestion/canonical_location.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add NYC and other major cities to ADMIN_LOCALITY_SETS
old_target = """    ("delhi", "IN"): {
        "in_boundary": {
            "delhi", "new delhi", "central delhi", "north delhi", "south delhi",
            "east delhi", "west delhi", "north east delhi", "north west delhi",
            "south east delhi", "south west delhi", "shahdara", "dwarka", "rohini",
            "narela", "connaught place", "saket", "karol bagh", "hauz khas",
        },
        "out_boundary_neighbors": {
            "noida", "greater noida", "gurgaon", "gurugram", "faridabad",
            "ghaziabad", "sonipat", "bahadurgarh",
        },
        "metro_counties": {"national capital region", "ncr", "delhi"},
    },
}"""

new_target = """    ("delhi", "IN"): {
        "in_boundary": {
            "delhi", "new delhi", "central delhi", "north delhi", "south delhi",
            "east delhi", "west delhi", "north east delhi", "north west delhi",
            "south east delhi", "south west delhi", "shahdara", "dwarka", "rohini",
            "narela", "connaught place", "saket", "karol bagh", "hauz khas",
        },
        "out_boundary_neighbors": {
            "noida", "greater noida", "gurgaon", "gurugram", "faridabad",
            "ghaziabad", "sonipat", "bahadurgarh",
        },
        "metro_counties": {"national capital region", "ncr", "delhi"},
    },
    ("new york city", "US"): {
        "in_boundary": {
            "new york", "new york city", "nyc", "manhattan", "brooklyn", "queens",
            "the bronx", "bronx", "staten island", "long island city", "astoria",
            "flushing", "jamaica", "midtown", "downtown", "upper east side",
            "upper west side", "harlem", "williamsburg", "bushwick", "dumbo",
            "greenpoint", "bay ridge", "sunset park", "crown heights", "park slope",
            "coney island", "staten island", "riverdale", "soho", "tribeca", "chelsea",
        },
        "out_boundary_neighbors": {
            "jersey city", "hoboken", "newark", "yonkers", "white plains", "stamford",
        },
        "metro_counties": {"new york", "kings", "queens", "bronx", "richmond", "new york county", "kings county", "queens county", "bronx county", "richmond county"},
    },
    ("new york", "US"): {
        "in_boundary": {
            "new york", "new york city", "nyc", "manhattan", "brooklyn", "queens",
            "the bronx", "bronx", "staten island", "long island city", "astoria",
            "flushing", "jamaica", "midtown", "downtown", "upper east side",
            "upper west side", "harlem", "williamsburg", "bushwick", "dumbo",
            "greenpoint", "bay ridge", "sunset park", "crown heights", "park slope",
            "coney island", "staten island", "riverdale", "soho", "tribeca", "chelsea",
        },
        "out_boundary_neighbors": {
            "jersey city", "hoboken", "newark", "yonkers", "white plains", "stamford",
        },
        "metro_counties": {"new york", "kings", "queens", "bronx", "richmond"},
    },
    ("boston", "US"): {
        "in_boundary": {
            "boston", "back bay", "beacon hill", "south boston", "east boston",
            "charlestown", "dorchester", "roxbury", "mattapan", "jamaica plain",
            "allston", "brighton", "hyde park", "west roxbury", "roslindale",
            "south end", "fenway", "kenmore", "north end", "chinatown",
        },
        "out_boundary_neighbors": {
            "cambridge", "somerville", "quincy", "brookline", "newton", "watertown",
            "chelsea", "revere", "everett", "malden", "medford", "waltham",
        },
        "metro_counties": {"suffolk", "suffolk county", "middlesex", "norfolk"},
    },
    ("los angeles", "US"): {
        "in_boundary": {
            "los angeles", "la", "downtown los angeles", "dtla", "hollywood",
            "west hollywood", "silver lake", "echo park", "venice", "playa del rey",
            "koreatown", "brentwood", "westwood", "bel air", "encino", "van nuys",
            "north hollywood", "sherman oaks", "studio city", "woodland hills",
        },
        "out_boundary_neighbors": {
            "santa monica", "beverly hills", "culver city", "pasadena", "burbank",
            "glendale", "long beach", "torrance", "inglewood", "compton",
        },
        "metro_counties": {"los angeles", "los angeles county"},
    },
}"""

content = content.replace(old_target, new_target)

# 2. Relax in-boundary match to recognize address containing city name or sub-string city match
old_check = """                # 3C. In-Boundary Locality Check
                if res_city_norm == req_city_norm or res_city_norm in in_boundary_set or res_locality_norm in in_boundary_set:"""

new_check = """                # 3C. In-Boundary Locality Check
                addr_str = str(address or "").lower()
                req_first_word = req_city_norm.split()[0] if req_city_norm else ""
                city_in_address = (
                    req_city_norm in addr_str
                    or (req_first_word and len(req_first_word) >= 4 and req_first_word in addr_str)
                )
                if (
                    res_city_norm == req_city_norm
                    or res_city_norm in in_boundary_set
                    or res_locality_norm in in_boundary_set
                    or (req_city_norm and req_city_norm in res_city_norm)
                    or (res_city_norm and res_city_norm in req_city_norm)
                    or city_in_address
                ):"""

content = content.replace(old_check, new_check)

with open('backend/app/ingestion/canonical_location.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("canonical_location.py updated successfully!")
