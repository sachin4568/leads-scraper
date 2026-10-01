from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Standard country lookup dictionary
CANADIAN_PROVINCES: dict[str, str] = {
    "ontario": "Ontario",
    "on": "Ontario",
    "quebec": "Quebec",
    "qc": "Quebec",
    "british columbia": "British Columbia",
    "bc": "British Columbia",
    "alberta": "Alberta",
    "ab": "Alberta",
    "manitoba": "Manitoba",
    "mb": "Manitoba",
    "saskatchewan": "Saskatchewan",
    "sk": "Saskatchewan",
    "nova scotia": "Nova Scotia",
    "ns": "Nova Scotia",
    "new brunswick": "New Brunswick",
    "nb": "New Brunswick",
    "newfoundland and labrador": "Newfoundland and Labrador",
    "nl": "Newfoundland and Labrador",
    "prince edward island": "Prince Edward Island",
    "pe": "Prince Edward Island",
    "pei": "Prince Edward Island",
    "northwest territories": "Northwest Territories",
    "nt": "Northwest Territories",
    "nunavut": "Nunavut",
    "nu": "Nunavut",
    "yukon": "Yukon",
    "yt": "Yukon",
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

UK_REGIONS: dict[str, str] = {
    "england": "England",
    "scotland": "Scotland",
    "wales": "Wales",
    "northern ireland": "Northern Ireland",
    "greater london": "London",
    "london": "London",
    "manchester": "Greater Manchester",
    "birmingham": "West Midlands",
    "leeds": "West Yorkshire",
    "glasgow": "Glasgow",
    "edinburgh": "Edinburgh",
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

COUNTRY_ALIASES: dict[str, tuple[str, str]] = {
    # Name -> (Canonical Name, ISO Code)
    "canada": ("Canada", "CA"),
    "ca": ("Canada", "CA"),
    "united states": ("United States", "US"),
    "united states of america": ("United States", "US"),
    "usa": ("United States", "US"),
    "us": ("United States", "US"),
    "united kingdom": ("United Kingdom", "GB"),
    "uk": ("United Kingdom", "GB"),
    "great britain": ("United Kingdom", "GB"),
    "england": ("United Kingdom", "GB"),
    "scotland": ("United Kingdom", "GB"),
    "wales": ("United Kingdom", "GB"),
    "australia": ("Australia", "AU"),
    "au": ("Australia", "AU"),
    "india": ("India", "IN"),
    "in": ("India", "IN"),
    "germany": ("Germany", "DE"),
    "de": ("Germany", "DE"),
    "france": ("France", "FR"),
    "fr": ("France", "FR"),
}

CANADIAN_MAJOR_CITIES: set[str] = {
    "toronto", "montreal", "vancouver", "calgary", "edmonton", "ottawa", "winnipeg",
    "quebec city", "hamilton", "kitchener", "waterloo", "london", "halifax", "victoria",
    "windsor", "oshawa", "barrie", "kingston", "guelph", "mississauga", "brampton", "markham",
    "richmond hill", "vaughan", "surrey", "burnaby",
}


@dataclass
class NormalizedLocationHierarchy:
    raw_query: str
    city: str | None = None
    state_or_province: str | None = None
    country: str = "United States"
    country_code: str = "US"
    formatted_location: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_query": self.raw_query,
            "city": self.city,
            "state_or_province": self.state_or_province,
            "country": self.country,
            "country_code": self.country_code,
            "formatted_location": self.formatted_location,
        }


class LocationNormalizer:
    """Parses and normalizes multi-part geographical strings into canonical country,
    state/province, and city hierarchies.
    """

    @classmethod
    def parse_location(
        cls,
        location_str: str | None,
        fallback_country: str | None = None,
        fallback_region: str | None = None,
    ) -> NormalizedLocationHierarchy:
        from backend.app.ingestion.canonical_location import LocationValidator, CanonicalLocation

        # Use LocationValidator to resolve location
        resolved: CanonicalLocation = LocationValidator.resolve_candidate_location(
            candidate_address=location_str,
            raw_place_data=None,
            requested_country_code=LocationValidator.normalize_country(fallback_country)[1] if LocationValidator.normalize_country(fallback_country) else None,
        )

        country = resolved.country
        country_code = resolved.country_code
        region = resolved.region
        city = resolved.city

        # If country could not be determined from location string, apply fallback
        if country == "Unknown" or not country:
            if fallback_country:
                c_norm = LocationValidator.normalize_country(fallback_country)
                if c_norm:
                    country, country_code = c_norm
                else:
                    country = fallback_country
                    country_code = "US"
            else:
                country = "United States"
                country_code = "US"

        if not region and fallback_region:
            r_norm = LocationValidator.normalize_region(fallback_region, country_code)
            if r_norm:
                region = r_norm[0]
            else:
                region = fallback_region

        if not city and location_str and str(location_str).strip() and str(location_str).strip().lower() != country.lower():
            # If location_str was not the country itself
            city = str(location_str).split(",")[0].strip()

        loc_elements = [e for e in [city, region, country] if e and e != "Unknown"]
        seen_el = set()
        clean_elements = []
        for el in loc_elements:
            if el not in seen_el:
                seen_el.add(el)
                clean_elements.append(el)

        formatted_location = ", ".join(clean_elements)

        return NormalizedLocationHierarchy(
            raw_query=str(location_str or ""),
            city=city,
            state_or_province=region,
            country=country,
            country_code=country_code,
            formatted_location=formatted_location,
        )


def is_location_relevant(
    candidate_address: str | None,
    candidate_phone: str | None,
    candidate_website: str | None,
    candidate_country: str | None,
    target_hierarchy: NormalizedLocationHierarchy,
) -> tuple[bool, str]:
    """Evaluates whether a candidate business matches the requested location hierarchy.
    Rejects clear cross-country or cross-region mismatches.
    """
    from backend.app.ingestion.canonical_location import LocationValidator, CanonicalLocation

    scope = CanonicalLocation(
        country=target_hierarchy.country,
        country_code=target_hierarchy.country_code,
        region=target_hierarchy.state_or_province,
        city=target_hierarchy.city,
    )

    candidate_mock = type(
        "CandidateMock",
        (),
        {
            "address": candidate_address,
            "phone": candidate_phone,
            "website": candidate_website,
            "country": candidate_country,
            "latitude": None,
            "longitude": None,
            "raw_data": {},
        },
    )()

    res = LocationValidator.evaluate_candidate(candidate_mock, scope)
    if not res.is_valid:
        reason = res.rejection_reason or "LOCATION_MISMATCH"
        if res.evidence:
            reason = f"{reason} ({res.evidence[0]})"
        return False, reason

    return True, "LOCATION_RELEVANT"
