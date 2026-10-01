from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BenchmarkCase:
    name: str
    niche: str
    location: str
    country: str = "United States"
    region: str | None = None
    state: str | None = None
    target_count: int = 100
    sources: list[str] = field(default_factory=lambda: ["google_maps", "osm_overpass", "foursquare"])
    enrichments: list[str] = field(default_factory=lambda: ["email", "website", "phone"])
    service: str = "website_dev"
    max_request_budget: int = 80


# Standard configurable benchmark test suites
BENCHMARK_PRESETS: dict[str, BenchmarkCase] = {
    "restaurants_ann_arbor": BenchmarkCase(
        name="Restaurants — Ann Arbor, MI",
        niche="Restaurant",
        location="Ann Arbor, MI",
        region="Michigan",
        state="Ann Arbor, Michigan",
        target_count=100,
    ),
    "dentists_tampa": BenchmarkCase(
        name="Dentists — Tampa, FL",
        niche="Dentist",
        location="Tampa, FL",
        region="Florida",
        state="Tampa, Florida",
        target_count=100,
    ),
    "plumbers_austin": BenchmarkCase(
        name="Plumbers — Austin, TX",
        niche="Plumber",
        location="Austin, TX",
        region="Texas",
        state="Austin, Texas",
        target_count=100,
    ),
    "hvac_phoenix": BenchmarkCase(
        name="HVAC — Phoenix, AZ",
        niche="HVAC",
        location="Phoenix, AZ",
        region="Arizona",
        state="Phoenix, Arizona",
        target_count=100,
    ),
    "lawyers_chicago": BenchmarkCase(
        name="Lawyers — Chicago, IL",
        niche="Lawyer",
        location="Chicago, IL",
        region="Illinois",
        state="Chicago, Illinois",
        target_count=100,
    ),
    "roofers_atlanta": BenchmarkCase(
        name="Roofers — Atlanta, GA",
        niche="Roofer",
        location="Atlanta, GA",
        region="Georgia",
        state="Atlanta, Georgia",
        target_count=100,
    ),
}
