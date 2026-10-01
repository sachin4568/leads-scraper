from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ============================================================================
# 1. CANONICAL GEOGRAPHIC DATA STRUCTURES
# ============================================================================

@dataclass
class CanonicalLocation:
    """Structured, authoritative representation of a geographic entity."""
    country: str = "United States"
    country_code: str = "US"
    region: str | None = None
    region_code: str | None = None
    county: str | None = None
    city: str | None = None
    locality: str | None = None
    postal_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    formatted_address: str | None = None
    raw_query: str = ""
    source: str = "internal"
    location_scope: str = "EXACT_CITY"  # EXACT_CITY | METRO_AREA | REGION | COUNTRY

    def to_dict(self) -> dict[str, Any]:
        return {
            "country": self.country,
            "country_code": self.country_code,
            "region": self.region,
            "region_code": self.region_code,
            "county": self.county,
            "city": self.city,
            "locality": self.locality,
            "postal_code": self.postal_code,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "formatted_address": self.formatted_address,
            "raw_query": self.raw_query,
            "source": self.source,
            "location_scope": self.location_scope,
        }

    @property
    def formatted_location(self) -> str:
        parts = []
        if self.city:
            parts.append(self.city)
        if self.region and self.region != self.city:
            parts.append(self.region)
        if self.country:
            parts.append(self.country)
        return ", ".join(parts) if parts else self.country


@dataclass
class LocationValidationResult:
    """Detailed result of a geographic validation check against requested scope."""
    status: str  # "VALID", "INVALID", "AMBIGUOUS", "INSUFFICIENT_EVIDENCE"
    is_valid: bool
    country_match: bool
    region_match: bool | None = None
    city_match: bool | None = None
    coordinate_match: bool | None = None
    boundary_match: bool | None = None
    confidence: float = 0.0
    location_scope: str = "EXACT_CITY"
    requested_scope: dict[str, Any] = field(default_factory=dict)
    resolved_location: dict[str, Any] = field(default_factory=dict)
    rejection_reason: str | None = None
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "is_valid": self.is_valid,
            "country_match": self.country_match,
            "region_match": self.region_match,
            "city_match": self.city_match,
            "coordinate_match": self.coordinate_match,
            "boundary_match": self.boundary_match,
            "confidence": self.confidence,
            "location_scope": self.location_scope,
            "requested_scope": self.requested_scope,
            "resolved_location": self.resolved_location,
            "rejection_reason": self.rejection_reason,
            "evidence": self.evidence,
        }


# ============================================================================
# 2. GEOGRAPHIC KNOWLEDGE BASE
# ============================================================================

# Deterministic ISO 3166-1 alpha-2 country lookup
COUNTRY_ALIASES: dict[str, tuple[str, str]] = {
    # United Kingdom
    "united kingdom": ("United Kingdom", "GB"),
    "uk": ("United Kingdom", "GB"),
    "great britain": ("United Kingdom", "GB"),
    "gb": ("United Kingdom", "GB"),
    "gbr": ("United Kingdom", "GB"),
    "britain": ("United Kingdom", "GB"),
    "england": ("United Kingdom", "GB"),
    "scotland": ("United Kingdom", "GB"),
    "wales": ("United Kingdom", "GB"),
    "northern ireland": ("United Kingdom", "GB"),

    # United States
    "united states": ("United States", "US"),
    "united states of america": ("United States", "US"),
    "usa": ("United States", "US"),
    "us": ("United States", "US"),
    "u.s.": ("United States", "US"),
    "u.s.a.": ("United States", "US"),

    # Canada
    "canada": ("Canada", "CA"),
    "ca": ("Canada", "CA"),
    "can": ("Canada", "CA"),

    # Australia
    "australia": ("Australia", "AU"),
    "au": ("Australia", "AU"),
    "aus": ("Australia", "AU"),

    # India
    "india": ("India", "IN"),
    "in": ("India", "IN"),
    "ind": ("India", "IN"),
    "bharat": ("India", "IN"),

    # Germany
    "germany": ("Germany", "DE"),
    "de": ("Germany", "DE"),
    "deu": ("Germany", "DE"),
    "deutschland": ("Germany", "DE"),

    # France
    "france": ("France", "FR"),
    "fr": ("France", "FR"),
    "fra": ("France", "FR"),
}

# Regions / States by Country
UK_NATIONS: dict[str, str] = {
    "england": "England",
    "scotland": "Scotland",
    "wales": "Wales",
    "northern ireland": "Northern Ireland",
}

UK_COUNTIES: dict[str, str] = {
    # Greater Manchester & North West
    "greater manchester": "England",
    "manchester": "England",
    "merseyside": "England",
    "liverpool": "England",
    "lancashire": "England",
    "cheshire": "England",
    "cumbria": "England",

    # Yorkshire
    "west yorkshire": "England",
    "leeds": "England",
    "south yorkshire": "England",
    "sheffield": "England",
    "north yorkshire": "England",
    "york": "England",
    "east riding of yorkshire": "England",

    # Midlands
    "west midlands": "England",
    "birmingham": "England",
    "east midlands": "England",
    "nottinghamshire": "England",
    "derbyshire": "England",
    "leicestershire": "England",
    "staffordshire": "England",
    "warwickshire": "England",
    "worcestershire": "England",

    # London & South East
    "greater london": "England",
    "london": "England",
    "surrey": "England",
    "kent": "England",
    "essex": "England",
    "hertfordshire": "England",
    "berkshire": "England",
    "buckinghamshire": "England",
    "oxfordshire": "England",
    "hampshire": "England",
    "sussex": "England",
    "west sussex": "England",
    "east sussex": "England",

    # South West
    "bristol": "England",
    "devon": "England",
    "cornwall": "England",
    "somerset": "England",
    "gloucestershire": "England",
    "dorset": "England",
    "wiltshire": "England",

    # North East
    "tyne and wear": "England",
    "newcastle": "England",
    "durham": "England",
    "northumberland": "England",

    # Scotland
    "glasgow": "Scotland",
    "city of glasgow": "Scotland",
    "edinburgh": "Scotland",
    "city of edinburgh": "Scotland",
    "aberdeenshire": "Scotland",
    "aberdeen": "Scotland",
    "dundee": "Scotland",
    "highland": "Scotland",
    "fife": "Scotland",
    "lanarkshire": "Scotland",
    "lothian": "Scotland",

    # Wales
    "cardiff": "Wales",
    "swansea": "Wales",
    "newport": "Wales",
    "glamorgan": "Wales",
    "gwent": "Wales",
    "gwynedd": "Wales",
    "clwyd": "Wales",
    "dyfed": "Wales",
    "powys": "Wales",

    # Northern Ireland
    "antrim": "Northern Ireland",
    "county antrim": "Northern Ireland",
    "belfast": "Northern Ireland",
    "armagh": "Northern Ireland",
    "county armagh": "Northern Ireland",
    "down": "Northern Ireland",
    "county down": "Northern Ireland",
    "fermanagh": "Northern Ireland",
    "county fermanagh": "Northern Ireland",
    "derry": "Northern Ireland",
    "londonderry": "Northern Ireland",
    "county londonderry": "Northern Ireland",
    "tyrone": "Northern Ireland",
    "county tyrone": "Northern Ireland",
    "lisburn": "Northern Ireland",
    "newry": "Northern Ireland",
}

US_STATES: dict[str, str] = {
    "alabama": "Alabama", "al": "Alabama",
    "alaska": "Alaska", "ak": "Alaska",
    "arizona": "Arizona", "az": "Arizona",
    "arkansas": "Arkansas", "ar": "Arkansas",
    "california": "California", "ca": "California",
    "colorado": "Colorado", "co": "Colorado",
    "connecticut": "Connecticut", "ct": "Connecticut",
    "delaware": "Delaware", "de": "Delaware",
    "florida": "Florida", "fl": "Florida",
    "georgia": "Georgia", "ga": "Georgia",
    "hawaii": "Hawaii", "hi": "Hawaii",
    "idaho": "Idaho", "id": "Idaho",
    "illinois": "Illinois", "il": "Illinois",
    "indiana": "Indiana", "in": "Indiana",
    "iowa": "Iowa", "ia": "Iowa",
    "kansas": "Kansas", "ks": "Kansas",
    "kentucky": "Kentucky", "ky": "Kentucky",
    "louisiana": "Louisiana", "la": "Louisiana",
    "maine": "Maine", "me": "Maine",
    "maryland": "Maryland", "md": "Maryland",
    "massachusetts": "Massachusetts", "ma": "Massachusetts",
    "michigan": "Michigan", "mi": "Michigan",
    "minnesota": "Minnesota", "mn": "Minnesota",
    "mississippi": "Mississippi", "ms": "Mississippi",
    "missouri": "Missouri", "mo": "Missouri",
    "montana": "Montana", "mt": "Montana",
    "nebraska": "Nebraska", "ne": "Nebraska",
    "nevada": "Nevada", "nv": "Nevada",
    "new hampshire": "New Hampshire", "nh": "New Hampshire",
    "new jersey": "New Jersey", "nj": "New Jersey",
    "new mexico": "New Mexico", "nm": "New Mexico",
    "new york": "New York", "ny": "New York",
    "north carolina": "North Carolina", "nc": "North Carolina",
    "north dakota": "North Dakota", "nd": "North Dakota",
    "ohio": "Ohio", "oh": "Ohio",
    "oklahoma": "Oklahoma", "ok": "Oklahoma",
    "oregon": "Oregon", "or": "Oregon",
    "pennsylvania": "Pennsylvania", "pa": "Pennsylvania",
    "rhode island": "Rhode Island", "ri": "Rhode Island",
    "south carolina": "South Carolina", "sc": "South Carolina",
    "south dakota": "South Dakota", "sd": "South Dakota",
    "tennessee": "Tennessee", "tn": "Tennessee",
    "texas": "Texas", "tx": "Texas",
    "utah": "Utah", "ut": "Utah",
    "vermont": "Vermont", "vt": "Vermont",
    "virginia": "Virginia", "va": "Virginia",
    "washington": "Washington", "wa": "Washington",
    "west virginia": "West Virginia", "wv": "West Virginia",
    "wisconsin": "Wisconsin", "wi": "Wisconsin",
    "wyoming": "Wyoming", "wy": "Wyoming",
    "district of columbia": "District of Columbia", "dc": "District of Columbia",
}

CANADIAN_PROVINCES: dict[str, str] = {
    "ontario": "Ontario", "on": "Ontario",
    "quebec": "Quebec", "qc": "Quebec",
    "british columbia": "British Columbia", "bc": "British Columbia",
    "alberta": "Alberta", "ab": "Alberta",
    "manitoba": "Manitoba", "mb": "Manitoba",
    "saskatchewan": "Saskatchewan", "sk": "Saskatchewan",
    "nova scotia": "Nova Scotia", "ns": "Nova Scotia",
    "new brunswick": "New Brunswick", "nb": "New Brunswick",
    "newfoundland and labrador": "Newfoundland and Labrador", "nl": "Newfoundland and Labrador",
    "prince edward island": "Prince Edward Island", "pe": "Prince Edward Island", "pei": "Prince Edward Island",
    "northwest territories": "Northwest Territories", "nt": "Northwest Territories",
    "nunavut": "Nunavut", "nu": "Nunavut",
    "yukon": "Yukon", "yt": "Yukon",
}

AUSTRALIAN_STATES: dict[str, str] = {
    "new south wales": "New South Wales", "nsw": "New South Wales",
    "victoria": "Victoria", "vic": "Victoria",
    "queensland": "Queensland", "qld": "Queensland",
    "western australia": "Western Australia", "wa": "Western Australia",
    "south australia": "South Australia", "sa": "South Australia",
    "tasmania": "Tasmania", "tas": "Tasmania",
    "australian capital territory": "Australian Capital Territory", "act": "Australian Capital Territory",
    "northern territory": "Northern Territory", "nt": "Northern Territory",
}

INDIAN_STATES: dict[str, str] = {
    "delhi": "Delhi", "nct of delhi": "Delhi", "national capital territory of delhi": "Delhi",
    "maharashtra": "Maharashtra", "mh": "Maharashtra",
    "karnataka": "Karnataka", "ka": "Karnataka",
    "tamil nadu": "Tamil Nadu", "tn": "Tamil Nadu",
    "gujarat": "Gujarat", "gj": "Gujarat",
    "uttar pradesh": "Uttar Pradesh", "up": "Uttar Pradesh",
    "west bengal": "West Bengal", "wb": "West Bengal",
    "telangana": "Telangana", "ts": "Telangana",
    "andhra pradesh": "Andhra Pradesh", "ap": "Andhra Pradesh",
    "kerala": "Kerala", "kl": "Kerala",
    "rajasthan": "Rajasthan", "rj": "Rajasthan",
    "punjab": "Punjab", "pb": "Punjab",
    "haryana": "Haryana", "hr": "Haryana",
    "bihar": "Bihar", "br": "Bihar",
    "madhya pradesh": "Madhya Pradesh", "mp": "Madhya Pradesh",
    "odisha": "Odisha", "orissa": "Odisha",
    "assam": "Assam",
    "jharkhand": "Jharkhand",
    "chhattisgarh": "Chhattisgarh",
    "uttarakhand": "Uttarakhand",
    "himachal pradesh": "Himachal Pradesh",
    "goa": "Goa",
    "jammu and kashmir": "Jammu and Kashmir",
    "ladakh": "Ladakh",
    "chandigarh": "Chandigarh",
    "puducherry": "Puducherry",
}

# Contextual Disambiguation Map for well-known ambiguous cities
# (city_name, country_code) -> (canonical_city, canonical_region, canonical_country)
DISAMBIGUATION_MAP: dict[tuple[str, str], dict[str, Any]] = {
    # Manchester
    ("manchester", "GB"): {
        "city": "Manchester",
        "region": "England",
        "county": "Greater Manchester",
        "country": "United Kingdom",
        "country_code": "GB",
        "bbox": [53.3335, 53.593, -2.333, -2.133],
    },
    ("manchester", "US"): {
        "city": "Manchester",
        "region": "Connecticut",
        "country": "United States",
        "country_code": "US",
    },

    # Birmingham
    ("birmingham", "GB"): {
        "city": "Birmingham",
        "region": "England",
        "county": "West Midlands",
        "country": "United Kingdom",
        "country_code": "GB",
        "bbox": [52.381, 52.608, -2.033, -1.727],
    },
    ("birmingham", "US"): {
        "city": "Birmingham",
        "region": "Alabama",
        "country": "United States",
        "country_code": "US",
        "bbox": [33.398, 33.649, -86.953, -86.634],
    },

    # London
    ("london", "GB"): {
        "city": "London",
        "region": "England",
        "county": "Greater London",
        "country": "United Kingdom",
        "country_code": "GB",
        "bbox": [51.28676, 51.69187, -0.510375, 0.3340155],
    },
    ("london", "CA"): {
        "city": "London",
        "region": "Ontario",
        "county": "Middlesex County",
        "country": "Canada",
        "country_code": "CA",
        "bbox": [42.868, 43.076, -81.396, -81.127],
    },

    # Delhi
    ("delhi", "IN"): {
        "city": "Delhi",
        "region": "Delhi",
        "country": "India",
        "country_code": "IN",
        "bbox": [28.40, 28.88, 76.84, 77.35],
    },
    ("new delhi", "IN"): {
        "city": "New Delhi",
        "region": "Delhi",
        "country": "India",
        "country_code": "IN",
        "bbox": [28.40, 28.88, 76.84, 77.35],
    },
    ("delhi", "US"): {
        "city": "Delhi",
        "region": "New York",
        "country": "United States",
        "country_code": "US",
    },

    # Leeds
    ("leeds", "GB"): {
        "city": "Leeds",
        "region": "England",
        "county": "West Yorkshire",
        "country": "United Kingdom",
        "country_code": "GB",
        "bbox": [53.743, 53.928, -1.683, -1.411],
    },

    # Liverpool
    ("liverpool", "GB"): {
        "city": "Liverpool",
        "region": "England",
        "county": "Merseyside",
        "country": "United Kingdom",
        "country_code": "GB",
        "bbox": [53.330, 53.480, -3.050, -2.850],
    },

    # Belfast
    ("belfast", "GB"): {
        "city": "Belfast",
        "region": "Northern Ireland",
        "county": "County Antrim",
        "country": "United Kingdom",
        "country_code": "GB",
        "bbox": [54.540, 54.670, -6.040, -5.820],
    },

    # Glasgow
    ("glasgow", "GB"): {
        "city": "Glasgow",
        "region": "Scotland",
        "country": "United Kingdom",
        "country_code": "GB",
        "bbox": [55.770, 55.930, -4.380, -4.130],
    },

    # Edinburgh
    ("edinburgh", "GB"): {
        "city": "Edinburgh",
        "region": "Scotland",
        "country": "United Kingdom",
        "country_code": "GB",
        "bbox": [55.880, 56.000, -3.350, -3.100],
    },

    # Cardiff
    ("cardiff", "GB"): {
        "city": "Cardiff",
        "region": "Wales",
        "country": "United Kingdom",
        "country_code": "GB",
        "bbox": [51.440, 51.560, -3.270, -3.100],
    },
}

# Country Bounding Boxes for Coordinate Sanity Checks
COUNTRY_BOUNDING_BOXES: dict[str, list[float]] = {
    # [lat_min, lat_max, lon_min, lon_max]
    "GB": [49.8, 60.9, -8.6, 1.8],
    "US": [24.5, 49.4, -125.0, -66.9],  # Contiguous US
    "CA": [41.6, 83.1, -141.0, -52.6],
    "AU": [-43.6, -10.0, 113.3, 153.6],
    "IN": [6.7, 37.1, 68.1, 97.4],
    "DE": [47.2, 55.1, 5.8, 15.0],
    "FR": [41.3, 51.1, -5.1, 9.6],
}


# ============================================================================
# AUTHORITATIVE ADMINISTRATIVE CITY BOUNDARY POLYGONS
# (lat, lon) vertices tracing administrative boundaries of target cities
# ============================================================================

ADMIN_POLYGONS: dict[tuple[str, str], list[tuple[float, float]]] = {
    # City of Manchester (local authority boundary, ONS E08000003)
    ("manchester", "GB"): [
        (53.535, -2.250),  # Heaton Park / Blackley North
        (53.525, -2.190),  # Moston North
        (53.505, -2.170),  # Newton Heath East
        (53.480, -2.160),  # Clayton / Openshaw East
        (53.450, -2.155),  # Gorton / Fairfield East
        (53.435, -2.175),  # Levenshulme East
        (53.415, -2.205),  # Burnage East
        (53.400, -2.235),  # Didsbury South-East
        (53.385, -2.245),  # Northenden / River Mersey
        (53.360, -2.250),  # Sharston / Wythenshawe East
        (53.345, -2.270),  # Manchester Airport / Ringway South
        (53.355, -2.290),  # Woodhouse Park West
        (53.380, -2.275),  # Baguley / Wythenshawe West
        (53.410, -2.270),  # Chorlton South-West
        (53.435, -2.275),  # Chorlton-cum-Hardy West (Border with Trafford)
        (53.455, -2.260),  # Whalley Range / Moss Side West
        (53.475, -2.255),  # Castlefield / Deansgate West (River Irwell border with Salford)
        (53.490, -2.250),  # Strangeways / Cheetham Hill West (Border with Salford)
        (53.515, -2.245),  # Crumpsall West (Border with Bury/Prestwich)
        (53.535, -2.250),  # Close loop
    ],
    # Birmingham City Council
    ("birmingham", "GB"): [
        (52.570, -1.830), (52.540, -1.750), (52.480, -1.740),
        (52.420, -1.820), (52.390, -1.930), (52.420, -2.010),
        (52.480, -2.000), (52.540, -1.950), (52.570, -1.830),
    ],
    # Leeds City Council
    ("leeds", "GB"): [
        (53.930, -1.600), (53.900, -1.350), (53.750, -1.350),
        (53.700, -1.550), (53.750, -1.720), (53.880, -1.720), (53.930, -1.600),
    ],
    # Greater London
    ("london", "GB"): [
        (51.690, -0.150), (51.650, 0.200), (51.500, 0.330),
        (51.350, 0.150), (51.290, -0.080), (51.320, -0.350),
        (51.480, -0.500), (51.620, -0.450), (51.690, -0.150),
    ],
}

# ============================================================================
# ADMINISTRATIVE LOCALITY KNOWLEDGE BASE
# Maps target cities to exact internal districts vs neighboring administrative areas
# ============================================================================

ADMIN_LOCALITY_SETS: dict[tuple[str, str], dict[str, set[str]]] = {
    ("manchester", "GB"): {
        "in_boundary": {
            "manchester", "manchester city centre", "ancoats", "ardwick", "baguley",
            "benchill", "blackley", "bradford", "burnage", "cheetham hill", "cheetham",
            "chorlton-cum-hardy", "chorlton", "clayton", "collyhurst", "crumpsall",
            "didsbury", "east didsbury", "west didsbury", "fallowfield", "gorton",
            "harpurhey", "hulme", "levenshulme", "longsight", "miles platting",
            "moss side", "moston", "newall green", "newton heath", "northenden",
            "northern quarter", "openshaw", "peel hall", "ringway", "rusholme",
            "sharston", "whalley range", "withington", "woodhouse park", "wythenshawe",
        },
        "out_boundary_neighbors": {
            "salford", "stretford", "old trafford", "failsworth", "stockport",
            "bolton", "bury", "rochdale", "oldham", "altrincham", "sale", "eccles",
            "swinton", "ashton-under-lyne", "denton", "droylsden", "hyde", "cheadle",
            "cheadle hulme", "bramhall", "prestwich", "radcliffe", "whitefield",
            "middleton", "heywood", "chadderton", "royton", "shaw", "westhoughton",
            "farnworth", "horwich", "wigan", "leigh", "ashton-in-makerfield",
            "hindley", "standish", "atherton", "tyldesley", "urmston", "partington",
            "trafford",
        },
        "metro_counties": {"greater manchester"},
    },
    ("birmingham", "GB"): {
        "in_boundary": {
            "birmingham", "edgbaston", "aston", "erdington", "handsworth",
            "harborne", "moseley", "kings heath", "selly oak", "sutton coldfield",
            "perry barr", "ladywood", "hall green", "yardley", "northfield",
            "bournville", "digbeth", "jewellery quarter", "sparkbrook", "sparkhill",
            "acocks green", "great barr", "kingstanding", "nechells", "bordesley",
        },
        "out_boundary_neighbors": {
            "solihull", "wolverhampton", "dudley", "walsall", "west bromwich",
            "smethwick", "sutton", "halesowen", "stourbridge", "tamworth", "bromsgrove",
            "redditon", "redditch", "cannock", "lichfield", "oldbury",
        },
        "metro_counties": {"west midlands"},
    },
    ("leeds", "GB"): {
        "in_boundary": {
            "leeds", "headingley", "horsforth", "pudsey", "otley", "wetherby",
            "morley", "rothwell", "garforth", "yeadon", "guiseley", "chapel allerton",
            "roundhay", "moortown", "kirkstall", "harehills", "beeston", "armley",
            "bramley", "holbeck", "hunslet", "seacroft", "cross gates", "alwoodley",
            "meanwood", "burley", "woodhouse", "hyde park", "oakwood",
        },
        "out_boundary_neighbors": {
            "bradford", "wakefield", "harrogate", "castleford", "pontefract",
            "dewsbury", "batley", "halifax", "huddersfield", "keighley", "ilkley",
            "cleckheaton", "heckmondwike", "mirfield", "brighouse",
        },
        "metro_counties": {"west yorkshire"},
    },
    ("london", "GB"): {
        "in_boundary": {
            "london", "city of london", "westminster", "camden", "islington",
            "hackney", "tower hamlets", "greenwich", "lewisham", "southwark",
            "lambeth", "wandsworth", "hammersmith and fulham", "kensington and chelsea",
            "brent", "ealing", "hounslow", "richmond upon thames", "kingston upon thames",
            "merton", "sutton", "croydon", "bromley", "bexley", "havering",
            "barking and dagenham", "redbridge", "newham", "waltham forest",
            "haringey", "enfield", "barnet", "harrow", "hillingdon",
            "stratford", "canary wharf", "brixton", "shoreditch", "peckham", "clapham",
            "chelsea", "kensington", "paddington", "soho", "mayfair", "whitechapel",
        },
        "out_boundary_neighbors": {
            "watford", "dartford", "epsom", "st albans", "slough", "brentwood",
            "loughton", "esher", "weybridge", "sevenoaks", "potters bar",
            "rickmansworth", "chigwell", "borehamwood", "leatherhead", "gravesend",
        },
        "metro_counties": {"greater london"},
    },
    ("delhi", "IN"): {
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
}


def is_point_in_polygon(lat: float, lon: float, polygon: list[tuple[float, float]]) -> bool:
    """Ray casting point-in-polygon algorithm for fast boundary testing."""
    if not polygon or len(polygon) < 3:
        return False
    inside = False
    n = len(polygon)
    p1_lat, p1_lon = polygon[0]
    for i in range(1, n + 1):
        p2_lat, p2_lon = polygon[i % n]
        if lon > min(p1_lon, p2_lon):
            if lon <= max(p1_lon, p2_lon):
                if lat <= max(p1_lat, p2_lat):
                    if p1_lon != p2_lon:
                        lat_inters = (lon - p1_lon) * (p2_lat - p1_lat) / (p2_lon - p1_lon) + p1_lat
                    if p1_lat == p2_lat or lat <= lat_inters:
                        inside = not inside
        p1_lat, p1_lon = p2_lat, p2_lon
    return inside


# ============================================================================
# 3. LOCATION VALIDATOR ENGINE
# ============================================================================

class LocationValidator:
    """Production-grade Location Integrity and Geographic Validation Engine."""

    @classmethod
    def normalize_country(cls, country_str: str | None) -> tuple[str, str] | None:
        """Deterministically normalizes country input to (Canonical Name, ISO Code)."""
        if not country_str or not str(country_str).strip():
            return None
        clean = str(country_str).lower().strip()
        clean = re.sub(r"[^a-z\s.]", "", clean)
        return COUNTRY_ALIASES.get(clean)

    @classmethod
    def normalize_region(cls, region_str: str | None, country_code: str | None = None) -> tuple[str, str | None] | None:
        """Deterministically normalizes a region/state based on country context."""
        if not region_str or not str(region_str).strip():
            return None
        clean = str(region_str).lower().strip()

        # UK Region / Nation / County
        if country_code == "GB":
            if clean in UK_NATIONS:
                return UK_NATIONS[clean], None
            if clean in UK_COUNTIES:
                return UK_COUNTIES[clean], None
            return None

        # US State
        if country_code == "US":
            if clean in US_STATES:
                return US_STATES[clean], None
            return None

        # Canadian Province
        if country_code == "CA":
            if clean in CANADIAN_PROVINCES:
                return CANADIAN_PROVINCES[clean], None
            return None

        # Australian State
        if country_code == "AU":
            if clean in AUSTRALIAN_STATES:
                return AUSTRALIAN_STATES[clean], None
            return None

        # Indian State
        if country_code == "IN":
            if clean in INDIAN_STATES:
                return INDIAN_STATES[clean], None
            return None

        if not country_code:
            if clean in UK_NATIONS:
                return UK_NATIONS[clean], None
            if clean in UK_COUNTIES:
                return UK_COUNTIES[clean], None
            if clean in US_STATES:
                return US_STATES[clean], None
            if clean in CANADIAN_PROVINCES:
                return CANADIAN_PROVINCES[clean], None
            if clean in AUSTRALIAN_STATES:
                return AUSTRALIAN_STATES[clean], None
            if clean in INDIAN_STATES:
                return INDIAN_STATES[clean], None

        return region_str.strip().title(), None

    @classmethod
    def validate_requested_configuration(
        cls,
        country: str | None,
        region: str | None,
        city: str | None,
        locations: list[str] | None = None,
        location_scope: str = "EXACT_CITY",
    ) -> tuple[bool, str | None, CanonicalLocation | None]:
        """Validates that requested Country, Region, and City/Locations are geographically consistent.
        Rejects impossible combinations before scraping starts (e.g. UK + Northern Ireland + Manchester).
        DOES NOT silently mutate user input.
        """
        # 1. Normalize Country
        c_tuple = cls.normalize_country(country)
        if not c_tuple:
            return False, f"Invalid or unrecognized country: '{country}'. Please provide a valid country.", None

        canonical_country, country_code = c_tuple

        # Gather target cities to validate
        cities_to_check: list[str] = []
        if locations and isinstance(locations, list):
            cities_to_check.extend([str(loc).strip() for loc in locations if str(loc).strip()])
        elif city and str(city).strip():
            cities_to_check.append(str(city).strip())

        # 2. Validate Region if provided
        canonical_region = None
        if region and str(region).strip():
            r_norm = cls.normalize_region(region, country_code)
            if r_norm:
                canonical_region = r_norm[0]
            else:
                canonical_region = region.strip().title()

        # 3. Disambiguate and check cross-region coherence for each city
        for target_city in cities_to_check:
            city_lower = target_city.lower().strip()

            # Check Disambiguation Map
            disambig = DISAMBIGUATION_MAP.get((city_lower, country_code))
            if disambig:
                expected_country = disambig["country"]
                expected_region = disambig.get("region")

                if expected_country != canonical_country:
                    return (
                        False,
                        f"Location mismatch: '{target_city}' is located in {expected_country}, not {canonical_country}.",
                        None,
                    )

                # Check UK Nations / Region contradiction (e.g., Manchester is in England, user chose Northern Ireland)
                if country_code == "GB" and canonical_region:
                    if expected_region and canonical_region != expected_region:
                        return (
                            False,
                            f"Location mismatch: {target_city} is in {expected_region}, not {canonical_region}. "
                            f"Please select a location within {canonical_region} or change the region to {expected_region}.",
                            None,
                        )

            # Check UK County database if country is UK
            if country_code == "GB" and city_lower in UK_COUNTIES:
                county_nation = UK_COUNTIES[city_lower]
                if canonical_region and canonical_region in UK_NATIONS.values() and canonical_region != county_nation:
                    return (
                        False,
                        f"Location mismatch: {target_city} is in {county_nation}, not {canonical_region}. "
                        f"Please select a location within {canonical_region} or change the region to {county_nation}.",
                        None,
                    )

            # Check US State database if country is US and city was given with state
            if country_code == "US" and canonical_region:
                if "," in target_city:
                    parts = [p.strip().lower() for p in target_city.split(",")]
                    if len(parts) >= 2 and parts[1] in US_STATES:
                        state_in_city = US_STATES[parts[1]]
                        if state_in_city != canonical_region:
                            return (
                                False,
                                f"Location mismatch: '{target_city}' belongs to {state_in_city}, not {canonical_region}.",
                                None,
                            )

        # Build clean canonical scope
        primary_city = cities_to_check[0] if cities_to_check else (city if city and str(city).strip() else None)
        scope = CanonicalLocation(
            country=canonical_country,
            country_code=country_code,
            region=canonical_region,
            city=primary_city,
            raw_query=f"{primary_city or ''}, {canonical_region or ''}, {canonical_country}".strip(", "),
            location_scope=location_scope or "EXACT_CITY",
        )
        return True, None, scope

    @classmethod
    def resolve_candidate_location(
        cls,
        candidate_address: str | None,
        candidate_phone: str | None = None,
        candidate_website: str | None = None,
        candidate_coords: tuple[float, float] | None = None,
        candidate_city: str | None = None,
        candidate_region: str | None = None,
        candidate_country: str | None = None,
        raw_place_data: dict[str, Any] | None = None,
        requested_country_code: str | None = None,
    ) -> CanonicalLocation:
        """Extracts structured geographic components from source candidate data without mutating locality."""
        raw_place = raw_place_data or {}

        detected_country = None
        detected_country_code = None
        detected_region = None
        detected_county = None
        detected_locality = None
        detected_postal_town = None
        detected_city = None
        detected_postal_code = None
        lat, lon = candidate_coords or (None, None)
        formatted_address = candidate_address

        # 1. Google Places (New) addressComponents structure
        address_components = raw_place.get("addressComponents") or raw_place.get("address_components")
        if address_components and isinstance(address_components, list):
            for comp in address_components:
                types = comp.get("types", [])
                long_text = comp.get("longText") or comp.get("long_name") or ""
                short_text = comp.get("shortText") or comp.get("short_name") or ""

                if "country" in types:
                    norm_c = cls.normalize_country(short_text or long_text)
                    if norm_c:
                        detected_country, detected_country_code = norm_c
                elif "administrative_area_level_1" in types:
                    norm_r = cls.normalize_region(long_text, detected_country_code or requested_country_code)
                    if norm_r:
                        detected_region = norm_r[0]
                    else:
                        detected_region = long_text
                elif "administrative_area_level_2" in types:
                    detected_county = long_text
                elif "locality" in types or "sublocality" in types:
                    if not detected_locality:
                        detected_locality = long_text
                elif "postal_town" in types:
                    detected_postal_town = long_text
                elif "postal_code" in types:
                    detected_postal_code = short_text or long_text

            # Exact locality is primary, fallback to postal town
            detected_city = detected_locality or detected_postal_town

        # 2. Google Places Coordinates
        if not lat or not lon:
            loc_obj = raw_place.get("location") or raw_place.get("geometry", {}).get("location")
            if isinstance(loc_obj, dict):
                lat = float(loc_obj.get("latitude") or loc_obj.get("lat") or 0.0) or None
                lon = float(loc_obj.get("longitude") or loc_obj.get("lng") or 0.0) or None

        # 3. OpenStreetMap Address Tags
        osm_tags = raw_place.get("tags", {})
        if osm_tags:
            if "addr:country" in osm_tags:
                norm_c = cls.normalize_country(osm_tags["addr:country"])
                if norm_c:
                    detected_country, detected_country_code = norm_c
            if "addr:state" in osm_tags:
                norm_r = cls.normalize_region(osm_tags["addr:state"], detected_country_code or requested_country_code)
                if norm_r:
                    detected_region = norm_r[0]
            if "addr:city" in osm_tags and not detected_city:
                detected_city = osm_tags["addr:city"]
            if "addr:suburb" in osm_tags and not detected_locality:
                detected_locality = osm_tags["addr:suburb"]
                if not detected_city:
                    detected_city = detected_locality
            if "addr:postcode" in osm_tags:
                detected_postal_code = osm_tags["addr:postcode"]

        if not lat and "lat" in raw_place:
            try:
                lat = float(raw_place["lat"])
            except (ValueError, TypeError):
                pass
        if not lon and "lon" in raw_place:
            try:
                lon = float(raw_place["lon"])
            except (ValueError, TypeError):
                pass

        # 4. Use candidate fields if provided and not yet detected
        if not detected_city and candidate_city:
            detected_city = candidate_city
            if not detected_locality:
                detected_locality = candidate_city

        if not detected_region and candidate_region:
            norm_r = cls.normalize_region(candidate_region, detected_country_code or requested_country_code)
            detected_region = norm_r[0] if norm_r else candidate_region

        if not detected_country and candidate_country:
            norm_c = cls.normalize_country(candidate_country)
            if norm_c:
                detected_country, detected_country_code = norm_c
            else:
                detected_country = candidate_country

        # 5. Fallback text parsing if structured components are missing
        if candidate_address and (not detected_country or not detected_city or not detected_region):
            addr_str = str(candidate_address).strip()
            parts = [p.strip() for p in re.split(r"[,;]+", addr_str) if p.strip()]

            for p in reversed(parts):
                p_clean = p.lower().strip()
                if not detected_country:
                    norm_c = cls.normalize_country(p_clean)
                    if norm_c:
                        detected_country, detected_country_code = norm_c
                        continue

                # Check Canadian/US/UK postal codes
                if not detected_postal_code:
                    ca_pc = re.search(r"\b[A-Z]\d[A-Z]\s*\d[A-Z]\d\b", p, re.IGNORECASE)
                    uk_pc = re.search(r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b", p, re.IGNORECASE)
                    us_pc = re.search(r"\b\d{5}(-\d{4})?\b", p)
                    if ca_pc:
                        detected_postal_code = ca_pc.group(0).upper()
                        if not detected_country:
                            detected_country = "Canada"
                            detected_country_code = "CA"
                    elif uk_pc:
                        detected_postal_code = uk_pc.group(0).upper()
                        if not detected_country:
                            detected_country = "United Kingdom"
                            detected_country_code = "GB"
                    elif us_pc:
                        detected_postal_code = us_pc.group(0)

                # Check region/state without postal code token
                p_no_pc = re.sub(r"\b[A-Z]\d[A-Z]\s*\d[A-Z]\d\b|\b\d{5}(-\d{4})?\b|\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b", "", p_clean, flags=re.IGNORECASE).strip()
                if p_no_pc and not detected_region and (detected_country_code or requested_country_code):
                    norm_r = cls.normalize_region(p_no_pc, detected_country_code or requested_country_code)
                    if norm_r:
                        detected_region = norm_r[0]
                        continue

                if not detected_city and p_no_pc and p_clean != (detected_country or "").lower() and p_clean != (detected_region or "").lower():
                    clean_city = p_no_pc
                    if clean_city and len(clean_city) > 1 and not re.match(r"^\d+$", clean_city):
                        detected_city = clean_city.title()

        # 6. Infer country from phone country code if country not yet found
        if not detected_country and candidate_phone:
            clean_phone = re.sub(r"[^0-9+]", "", str(candidate_phone))
            if clean_phone.startswith("+44"):
                detected_country = "United Kingdom"
                detected_country_code = "GB"
            elif clean_phone.startswith("+1"):
                detected_country = "United States"
                detected_country_code = "US"
            elif clean_phone.startswith("+91"):
                detected_country = "India"
                detected_country_code = "IN"

        # Disambiguate city if country known
        if detected_city and detected_country_code:
            disambig_key = (detected_city.lower().strip(), detected_country_code)
            if disambig_key in DISAMBIGUATION_MAP:
                d_info = DISAMBIGUATION_MAP[disambig_key]
                if not detected_region:
                    detected_region = d_info.get("region")
                if not detected_country:
                    detected_country = d_info.get("country")
                if not detected_county:
                    detected_county = d_info.get("county")

        # Fallback to requested country code if still unknown
        if not detected_country_code and requested_country_code:
            detected_country_code = requested_country_code
            if requested_country_code == "GB":
                detected_country = "United Kingdom"
            elif requested_country_code == "US":
                detected_country = "United States"

        return CanonicalLocation(
            country=detected_country or "Unknown",
            country_code=detected_country_code or "UNKNOWN",
            region=detected_region,
            county=detected_county,
            city=detected_city,
            locality=detected_locality,
            postal_code=detected_postal_code,
            latitude=lat,
            longitude=lon,
            formatted_address=formatted_address,
            raw_query=candidate_address or "",
            source="source_parsed",
        )

    @classmethod
    def evaluate_candidate(
        cls,
        candidate: NormalizedLeadRecord,
        requested_scope: CanonicalLocation,
    ) -> LocationValidationResult:
        """Evaluates whether a discovered candidate lead strictly belongs to the requested geographic scope.
        Implements deterministic validation across 4 hierarchical rules with explicit location_scope.
        """
        # Resolve candidate structured location
        cand_address = getattr(candidate, "address", None) or getattr(candidate, "formatted_address", None)
        cand_phone = getattr(candidate, "phone", None)
        cand_website = getattr(candidate, "website", None)
        cand_lat = getattr(candidate, "latitude", None)
        cand_lon = getattr(candidate, "longitude", None)
        cand_city = getattr(candidate, "city", None)
        cand_region = getattr(candidate, "region", None) or getattr(candidate, "state", None)
        cand_country = getattr(candidate, "country", None)
        cand_raw = getattr(candidate, "raw_data", None) or {}

        resolved = cls.resolve_candidate_location(
            candidate_address=cand_address,
            candidate_phone=cand_phone,
            candidate_website=cand_website,
            candidate_coords=(cand_lat, cand_lon) if cand_lat is not None and cand_lon is not None else None,
            candidate_city=cand_city,
            candidate_region=cand_region,
            candidate_country=cand_country,
            raw_place_data=cand_raw,
            requested_country_code=requested_scope.country_code,
        )

        req_country = requested_scope.country
        req_country_code = requested_scope.country_code
        req_region = requested_scope.region
        req_city = requested_scope.city
        scope_mode = (getattr(requested_scope, "location_scope", None) or "EXACT_CITY").upper()

        evidence: list[str] = []
        address = cand_address or ""
        phone = cand_phone or ""

        # ---------------------------------------------------------------------
        # RULE 1: HARD COUNTRY ENFORCEMENT & COUNTRY BOUNDING BOX
        # ---------------------------------------------------------------------
        country_match = False

        # Check explicit address string for foreign country tokens
        if address:
            addr_lower = str(address).lower()
            if req_country_code == "GB":
                if "usa" in addr_lower or "united states" in addr_lower or re.search(r",\s*(us|usa)\b", addr_lower):
                    return LocationValidationResult(
                        status="INVALID",
                        is_valid=False,
                        country_match=False,
                        confidence=1.0,
                        location_scope=scope_mode,
                        requested_scope=requested_scope.to_dict(),
                        resolved_location=resolved.to_dict(),
                        rejection_reason="LOCATION_COUNTRY_MISMATCH",
                        evidence=[f"Address '{address}' explicitly indicates United States when UK was requested."],
                    )
                if "canada" in addr_lower or "australia" in addr_lower or "india" in addr_lower:
                    return LocationValidationResult(
                        status="INVALID",
                        is_valid=False,
                        country_match=False,
                        confidence=1.0,
                        location_scope=scope_mode,
                        requested_scope=requested_scope.to_dict(),
                        resolved_location=resolved.to_dict(),
                        rejection_reason="LOCATION_COUNTRY_MISMATCH",
                        evidence=[f"Address '{address}' indicates foreign country when UK was requested."],
                    )
            elif req_country_code == "US":
                if "united kingdom" in addr_lower or re.search(r",\s*uk\b", addr_lower) or "canada" in addr_lower or "india" in addr_lower:
                    return LocationValidationResult(
                        status="INVALID",
                        is_valid=False,
                        country_match=False,
                        confidence=1.0,
                        location_scope=scope_mode,
                        requested_scope=requested_scope.to_dict(),
                        resolved_location=resolved.to_dict(),
                        rejection_reason="LOCATION_COUNTRY_MISMATCH",
                        evidence=[f"Address '{address}' indicates foreign country when US was requested."],
                    )
            elif req_country_code == "IN":
                if "united states" in addr_lower or "usa" in addr_lower or "united kingdom" in addr_lower or "canada" in addr_lower:
                    return LocationValidationResult(
                        status="INVALID",
                        is_valid=False,
                        country_match=False,
                        confidence=1.0,
                        location_scope=scope_mode,
                        requested_scope=requested_scope.to_dict(),
                        resolved_location=resolved.to_dict(),
                        rejection_reason="LOCATION_COUNTRY_MISMATCH",
                        evidence=[f"Address '{address}' indicates foreign country when India was requested."],
                    )

        if resolved.country_code != "UNKNOWN":
            if resolved.country_code == req_country_code:
                country_match = True
                evidence.append(f"Country matched: {resolved.country} ({resolved.country_code})")
            else:
                return LocationValidationResult(
                    status="INVALID",
                    is_valid=False,
                    country_match=False,
                    confidence=1.0,
                    location_scope=scope_mode,
                    requested_scope=requested_scope.to_dict(),
                    resolved_location=resolved.to_dict(),
                    rejection_reason="LOCATION_COUNTRY_MISMATCH",
                    evidence=[f"Country mismatch: Expected {req_country} ({req_country_code}), resolved {resolved.country} ({resolved.country_code})"],
                )
        # Check phone country code against requested country
        if phone:
            clean_phone = re.sub(r"[^0-9+]", "", str(phone))
            if req_country_code == "GB" and (clean_phone.startswith("+1") or clean_phone.startswith("+91") or clean_phone.startswith("+61")):
                return LocationValidationResult(
                    status="INVALID",
                    is_valid=False,
                    country_match=False,
                    confidence=0.9,
                    location_scope=scope_mode,
                    requested_scope=requested_scope.to_dict(),
                    resolved_location=resolved.to_dict(),
                    rejection_reason="LOCATION_COUNTRY_MISMATCH",
                    evidence=[f"Phone {clean_phone} is not a UK number."],
                )
            elif req_country_code in ("US", "CA") and (clean_phone.startswith("+44") or clean_phone.startswith("+91") or clean_phone.startswith("+61")):
                return LocationValidationResult(
                    status="INVALID",
                    is_valid=False,
                    country_match=False,
                    confidence=0.9,
                    location_scope=scope_mode,
                    requested_scope=requested_scope.to_dict(),
                    resolved_location=resolved.to_dict(),
                    rejection_reason="LOCATION_COUNTRY_MISMATCH",
                    evidence=[f"Phone {clean_phone} is a foreign number for {req_country}."],
                )
        country_match = True

        # Country coordinate bounding box check
        coordinate_match = None
        if resolved.latitude is not None and resolved.longitude is not None:
            lat = resolved.latitude
            lon = resolved.longitude

            c_bbox = COUNTRY_BOUNDING_BOXES.get(req_country_code)
            if c_bbox:
                lat_min, lat_max, lon_min, lon_max = c_bbox
                if not (lat_min <= lat <= lat_max and lon_min <= lon <= lon_max):
                    return LocationValidationResult(
                        status="INVALID",
                        is_valid=False,
                        country_match=False,
                        coordinate_match=False,
                        confidence=1.0,
                        location_scope=scope_mode,
                        requested_scope=requested_scope.to_dict(),
                        resolved_location=resolved.to_dict(),
                        rejection_reason="LOCATION_COORDINATES_OUTSIDE_BOUNDARY",
                        evidence=[f"Coordinates ({lat}, {lon}) fall outside the bounding box for {req_country}."],
                    )
                else:
                    coordinate_match = True
                    evidence.append(f"Coordinates ({lat}, {lon}) verified within {req_country} boundary.")

        # Check for insufficient evidence
        has_address = bool(address and str(address).strip())
        has_phone = bool(phone and str(phone).strip())
        has_website = bool(getattr(candidate, "website", None) and str(candidate.website).strip())
        has_coords = bool(resolved.latitude is not None and resolved.longitude is not None)

        if not has_address and not has_coords and not has_phone and not has_website:
            return LocationValidationResult(
                status="INSUFFICIENT_EVIDENCE",
                is_valid=False,
                country_match=False,
                confidence=0.0,
                location_scope=scope_mode,
                requested_scope=requested_scope.to_dict(),
                resolved_location=resolved.to_dict(),
                rejection_reason="LOCATION_INSUFFICIENT_EVIDENCE",
                evidence=["Candidate provides no address, phone, website, or coordinates."],
            )

        # ---------------------------------------------------------------------
        # RULE 2: HARD REGION / STATE ENFORCEMENT
        # ---------------------------------------------------------------------
        region_match = True
        if req_region and str(req_region).strip():
            req_reg_norm = str(req_region).strip().lower()

            if resolved.region:
                res_reg_norm = resolved.region.lower()
                # Check for UK Nations / Counties compatibility
                if req_country_code == "GB":
                    # If requested England but resolved Northern Ireland or Scotland
                    if req_reg_norm in UK_NATIONS and res_reg_norm in UK_NATIONS:
                        if req_reg_norm != res_reg_norm:
                            return LocationValidationResult(
                                status="INVALID",
                                is_valid=False,
                                country_match=True,
                                region_match=False,
                                confidence=1.0,
                                location_scope=scope_mode,
                                requested_scope=requested_scope.to_dict(),
                                resolved_location=resolved.to_dict(),
                                rejection_reason="LOCATION_REGION_MISMATCH",
                                evidence=[f"UK Nation mismatch: Expected {req_region}, got {resolved.region}."],
                            )
                elif req_country_code == "US":
                    # Check US State exact match
                    if req_reg_norm in US_STATES and res_reg_norm in US_STATES:
                        if US_STATES[req_reg_norm] != US_STATES[res_reg_norm]:
                            return LocationValidationResult(
                                status="INVALID",
                                is_valid=False,
                                country_match=True,
                                region_match=False,
                                confidence=1.0,
                                location_scope=scope_mode,
                                requested_scope=requested_scope.to_dict(),
                                resolved_location=resolved.to_dict(),
                                rejection_reason="LOCATION_REGION_MISMATCH",
                                evidence=[f"US State mismatch: Expected {req_region}, got {resolved.region}."],
                            )

        # ---------------------------------------------------------------------
        # RULE 3: EXACT CITY / ADMINISTRATIVE BOUNDARY ENFORCEMENT
        # ---------------------------------------------------------------------
        city_match = True
        boundary_match = None
        if req_city and str(req_city).strip():
            req_city_clean = str(req_city).strip()
            req_city_norm = req_city_clean.lower()
            res_city_norm = (resolved.city or "").lower().strip()
            res_locality_norm = (resolved.locality or "").lower().strip()

            target_key = (req_city_norm, req_country_code)
            admin_polygon = ADMIN_POLYGONS.get(target_key)
            locality_data = ADMIN_LOCALITY_SETS.get(target_key, {})
            in_boundary_set = locality_data.get("in_boundary", set())
            out_neighbors_set = locality_data.get("out_boundary_neighbors", set())
            metro_counties = locality_data.get("metro_counties", set())

            lat = resolved.latitude
            lon = resolved.longitude

            if scope_mode == "EXACT_CITY":
                # 3A. Primary Check: Authoritative Coordinate Boundary Check
                if lat is not None and lon is not None and admin_polygon:
                    inside_poly = is_point_in_polygon(lat, lon, admin_polygon)
                    if not inside_poly:
                        return LocationValidationResult(
                            status="INVALID",
                            is_valid=False,
                            country_match=True,
                            region_match=region_match,
                            city_match=False,
                            coordinate_match=False,
                            boundary_match=False,
                            confidence=1.0,
                            location_scope=scope_mode,
                            requested_scope=requested_scope.to_dict(),
                            resolved_location=resolved.to_dict(),
                            rejection_reason="LOCATION_CITY_BOUNDARY_MISMATCH",
                            evidence=[f"Coordinates ({lat}, {lon}) fall outside the {req_city_clean} administrative boundary."],
                        )
                    else:
                        boundary_match = True
                        evidence.append(f"Coordinates ({lat}, {lon}) verified inside {req_city_clean} administrative boundary.")

                # 3B. Administrative Locality Check
                if res_city_norm in out_neighbors_set or res_locality_norm in out_neighbors_set:
                    return LocationValidationResult(
                        status="INVALID",
                        is_valid=False,
                        country_match=True,
                        region_match=region_match,
                        city_match=False,
                        boundary_match=False,
                        confidence=1.0,
                        location_scope=scope_mode,
                        requested_scope=requested_scope.to_dict(),
                        resolved_location=resolved.to_dict(),
                        rejection_reason="LOCATION_CITY_BOUNDARY_MISMATCH",
                        evidence=[f"Locality '{resolved.city or resolved.locality}' belongs to neighboring borough outside {req_city_clean} administrative area."],
                    )

                # 3C. In-Boundary Locality Check
                if res_city_norm == req_city_norm or res_city_norm in in_boundary_set or res_locality_norm in in_boundary_set:
                    city_match = True
                    evidence.append(f"Administrative locality matched: {resolved.city or req_city_clean}")
                elif resolved.city:
                    return LocationValidationResult(
                        status="INVALID",
                        is_valid=False,
                        country_match=True,
                        region_match=region_match,
                        city_match=False,
                        confidence=1.0,
                        location_scope=scope_mode,
                        requested_scope=requested_scope.to_dict(),
                        resolved_location=resolved.to_dict(),
                        rejection_reason="LOCATION_CITY_MISMATCH",
                        evidence=[f"City mismatch: Expected {req_city_clean}, resolved {resolved.city}."],
                    )
                elif not boundary_match:
                    return LocationValidationResult(
                        status="INSUFFICIENT_EVIDENCE",
                        is_valid=False,
                        country_match=True,
                        region_match=region_match,
                        city_match=False,
                        confidence=0.5,
                        location_scope=scope_mode,
                        requested_scope=requested_scope.to_dict(),
                        resolved_location=resolved.to_dict(),
                        rejection_reason="LOCATION_INSUFFICIENT_EVIDENCE",
                        evidence=[f"No coordinates or verifiable administrative locality for {req_city_clean}."],
                    )

            elif scope_mode == "METRO_AREA":
                # Allow adjacent metropolitan localities in the same metropolitan county
                if (
                    res_city_norm == req_city_norm
                    or res_city_norm in in_boundary_set
                    or res_locality_norm in in_boundary_set
                    or res_city_norm in out_neighbors_set
                    or res_locality_norm in out_neighbors_set
                    or (resolved.county and resolved.county.lower() in metro_counties)
                    or (resolved.region and resolved.region.lower() in metro_counties)
                ):
                    city_match = True
                    evidence.append(f"Metropolitan area matched: {resolved.city} ({req_city_clean} metro)")
                elif resolved.city:
                    return LocationValidationResult(
                        status="INVALID",
                        is_valid=False,
                        country_match=True,
                        region_match=region_match,
                        city_match=False,
                        confidence=1.0,
                        location_scope=scope_mode,
                        requested_scope=requested_scope.to_dict(),
                        resolved_location=resolved.to_dict(),
                        rejection_reason="LOCATION_CITY_MISMATCH",
                        evidence=[f"City mismatch: Expected {req_city_clean} metropolitan area, resolved {resolved.city}."],
                    )

        return LocationValidationResult(
            status="VALID",
            is_valid=True,
            country_match=True,
            region_match=region_match,
            city_match=city_match,
            coordinate_match=coordinate_match,
            boundary_match=boundary_match,
            confidence=0.98 if boundary_match else 0.90,
            location_scope=scope_mode,
            requested_scope=requested_scope.to_dict(),
            resolved_location=resolved.to_dict(),
            rejection_reason=None,
            evidence=evidence,
        )
