from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

class QueryExpansionEngine:
    """Configurable query-expansion engine to broaden candidate business discovery intelligently."""

    # Configurable synonyms, services, and subcategory expansions per niche category
    NICHES_EXPANSION: dict[str, dict[str, list[str]]] = {
        "dentist": {
            "synonyms": ["dental clinic", "dental practice", "dental surgery"],
            "services": ["cosmetic dentist", "family dentist", "emergency dentist"],
            "subcategories": ["orthodontist", "pediatric dentist", "teeth whitening"]
        },
        "dental clinic": {
            "synonyms": ["dentist", "dental practice", "dental care"],
            "services": ["cosmetic dentistry", "dental implants", "teeth cleaning"],
            "subcategories": ["orthodontics", "family dentistry"]
        },
        "dental": {
            "synonyms": ["dentist", "dental practice", "dental clinic"],
            "services": ["cosmetic dentistry", "oral health", "dental hygiene"],
            "subcategories": ["orthodontist", "pediatric dentistry"]
        },
        "plumber": {
            "synonyms": ["plumbing contractor", "heating engineer", "drain cleaning"],
            "services": ["emergency plumber", "leak repair", "boiler installation"],
            "subcategories": ["residential plumber", "commercial plumbing"]
        },
        "hvac": {
            "synonyms": ["air conditioning", "heating contractor", "climate control"],
            "services": ["ac repair", "furnace maintenance", "heat pump installation"],
            "subcategories": ["residential hvac", "commercial hvac"]
        },
        "roofing": {
            "synonyms": ["roofing contractor", "roof repair", "roof tile specialist"],
            "services": ["gutter replacement", "commercial roofing", "flat roof repair"],
            "subcategories": ["residential roofer", "metal roofing"]
        },
        "restaurant": {
            "synonyms": ["cafe", "eatery", "bistro", "diner"],
            "services": ["fine dining", "takeaway food", "food delivery"],
            "subcategories": ["pizzeria", "steakhouse", "sushi bar"]
        },
        "solar": {
            "synonyms": ["solar panels", "clean energy installer", "renewable power"],
            "services": ["solar installation", "solar repair", "residential solar"],
            "subcategories": ["commercial solar", "solar battery backup"]
        }
    }

    def expand_query(self, niche: str, location: str | None = None, max_queries: int = 5) -> list[dict[str, str]]:
        """Generates multiple search queries with reasons for expansion."""
        clean_niche = (niche or "business").strip()
        n_lower = clean_niche.lower()

        expanded: list[dict[str, str]] = []
        seen_queries: set[str] = set()

        def add_query(q: str, reason: str):
            q_norm = q.lower().strip()
            if q_norm and q_norm not in seen_queries:
                seen_queries.add(q_norm)
                expanded.append({"query": q.strip(), "reason": reason})

        # 1. Exact niche query
        add_query(clean_niche, "exact niche")

        # 2. Plural niche variation
        if not n_lower.endswith("s"):
            add_query(f"{clean_niche}s", "plural niche variation")
        else:
            # Singular fallback if plural was provided
            add_query(clean_niche[:-1], "singular niche variation")

        # 3. Check for dictionary-based synonym/subcategory expansions
        matched_niche = None
        for key in self.NICHES_EXPANSION:
            if key in n_lower or n_lower in key:
                matched_niche = key
                break

        if matched_niche:
            exp_data = self.NICHES_EXPANSION[matched_niche]
            # Add synonyms
            for syn in exp_data.get("synonyms", []):
                add_query(syn, "niche synonym")
            # Add services
            for svc in exp_data.get("services", []):
                add_query(svc, "service terminology")
            # Add subcategories
            for sub in exp_data.get("subcategories", []):
                add_query(sub, "subcategory variation")
        else:
            # Generic expansions if niche is not explicitly configured
            add_query(f"best {clean_niche}", "top/best service variation")
            add_query(f"local {clean_niche}", "local prefix variation")
            add_query(f"{clean_niche} services", "generic service suffix")

        # Limit the results to max_queries to prevent query explosion
        final_queries = expanded[:max_queries]
        logger.info(f"[QueryExpansion] Expanded '{niche}' into {len(final_queries)} queries (limit={max_queries})")
        return final_queries
