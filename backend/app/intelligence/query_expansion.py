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
        "plumbing": {
            "synonyms": ["plumber", "plumbing contractor", "drain cleaning"],
            "services": ["emergency plumbing", "water heater repair", "pipe repair"],
            "subcategories": ["residential plumbing", "commercial plumbing"]
        },
        "electrician": {
            "synonyms": ["electrical contractor", "electrical engineer", "lighting specialist"],
            "services": ["emergency electrician", "rewiring", "fuse box replacement"],
            "subcategories": ["residential electrician", "commercial electrical"]
        },
        "electrical": {
            "synonyms": ["electrician", "electrical contractor", "electrical services"],
            "services": ["electrical repairs", "panel upgrade", "ev charger installation"],
            "subcategories": ["commercial electrical", "residential electrical"]
        },
        "hvac": {
            "synonyms": ["air conditioning", "heating contractor", "climate control"],
            "services": ["ac repair", "furnace maintenance", "heat pump installation"],
            "subcategories": ["residential hvac", "commercial hvac"]
        },
        "heating": {
            "synonyms": ["boiler repair", "furnace repair", "heating engineer"],
            "services": ["boiler installation", "radiator repair", "central heating"],
            "subcategories": ["commercial heating", "residential heating"]
        },
        "air conditioning": {
            "synonyms": ["ac repair", "cooling contractor", "hvac"],
            "services": ["ac installation", "ac maintenance", "air cooling"],
            "subcategories": ["commercial ac", "residential ac"]
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
        },
        "cleaning": {
            "synonyms": ["cleaning service", "cleaners", "janitorial service"],
            "services": ["commercial cleaning", "office cleaning", "deep cleaning"],
            "subcategories": ["carpet cleaning", "window cleaning"]
        },
        "lawyer": {
            "synonyms": ["attorney", "law firm", "legal practice"],
            "services": ["legal consultation", "court representation"],
            "subcategories": ["personal injury lawyer", "corporate attorney", "family lawyer"]
        },
        "attorney": {
            "synonyms": ["lawyer", "law firm", "legal counsel"],
            "services": ["litigation", "legal advice"],
            "subcategories": ["criminal defense", "estate planning", "employment law"]
        },
        "accountant": {
            "synonyms": ["accounting firm", "cpa", "bookkeeper"],
            "services": ["tax preparation", "bookkeeping", "payroll services"],
            "subcategories": ["chartered accountant", "business accounting"]
        },
    }

    def expand_query(self, niche: str, location: str | None = None, max_queries: int = 25) -> list[dict[str, str]]:
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

        # 2. Plural / Singular niche variation
        if not n_lower.endswith("s"):
            add_query(f"{clean_niche}s", "plural niche variation")
        else:
            add_query(clean_niche[:-1], "singular niche variation")

        # 3. Check for dictionary-based synonym/subcategory expansions
        matched_niche = None
        for key in self.NICHES_EXPANSION:
            if key in n_lower or n_lower in key:
                matched_niche = key
                break

        if matched_niche:
            exp_data = self.NICHES_EXPANSION[matched_niche]
            for syn in exp_data.get("synonyms", []):
                add_query(syn, "niche synonym")
            for svc in exp_data.get("services", []):
                add_query(svc, "service terminology")
            for sub in exp_data.get("subcategories", []):
                add_query(sub, "subcategory variation")

        # 4. Universal business modifiers for broad coverage
        universal_modifiers = [
            (f"{clean_niche} services", "services variation"),
            (f"{clean_niche} contractors", "contractor variation"),
            (f"{clean_niche} company", "company variation"),
            (f"emergency {clean_niche}", "emergency variation"),
            (f"commercial {clean_niche}", "commercial variation"),
            (f"residential {clean_niche}", "residential variation"),
            (f"local {clean_niche}", "local prefix variation"),
            (f"best {clean_niche}", "top/best service variation"),
            (f"{clean_niche} repair", "repair variation"),
            (f"{clean_niche} installation", "installation variation"),
            (f"{clean_niche} specialist", "specialist variation"),
            (f"licensed {clean_niche}", "licensed variation"),
        ]
        for mod_q, mod_reason in universal_modifiers:
            add_query(mod_q, mod_reason)

        # 5. Location-specific angles if location is supplied
        if location and str(location).strip():
            loc_clean = str(location).strip()
            loc_city = loc_clean.split(",")[0].strip()
            add_query(f"{clean_niche} in {loc_city}", "location in niche")
            add_query(f"{clean_niche} {loc_city}", "niche city keyword")
            add_query(f"best {clean_niche} in {loc_city}", "best niche in city")
            add_query(f"emergency {clean_niche} {loc_city}", "emergency niche in city")
            add_query(f"{clean_niche} services {loc_city}", "niche services in city")

        # Limit the results to max_queries to prevent query explosion
        final_queries = expanded[:max_queries]
        logger.info(f"[QueryExpansion] Expanded '{niche}' into {len(final_queries)} queries (limit={max_queries})")
        return final_queries
