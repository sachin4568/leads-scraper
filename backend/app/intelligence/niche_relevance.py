from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Core synonyms taxonomy for common business niches
NICHE_SYNONYMS_TAXONOMY: dict[str, set[str]] = {
    "plumber": {
        "plumber", "plumbing", "drain", "pipe", "pipefitting", "water heater",
        "sewer", "leak detection", "rooter", "gas fitter", "sanitation", "hvac & plumbing",
        "emergency plumber", "commercial plumbing", "residential plumbing", "plumber contractor"
    },
    "plumbing": {
        "plumber", "plumbing", "drain", "pipe", "pipefitting", "water heater",
        "sewer", "leak detection", "rooter", "gas fitter", "sanitation", "emergency plumber"
    },
    "electrician": {
        "electrician", "electrical", "wiring", "lighting", "circuit", "panel upgrade",
        "electrical contractor", "commercial electrician", "residential electrician", "ev charger installation"
    },
    "roofing": {
        "roofer", "roofing", "shingles", "gutter", "gutters", "roof repair",
        "roof replacement", "commercial roofing", "roof contractor", "siding and roofing"
    },
    "hvac": {
        "hvac", "heating", "cooling", "air conditioning", "furnace", "heat pump",
        "ventilation", "ac repair", "boiler", "duct cleaning", "heating contractor"
    },
    "dental": {
        "dentist", "dental", "dentistry", "orthodontist", "orthodontics", "teeth",
        "oral surgeon", "pediatric dentist", "cosmetic dentist", "dental clinic", "dental care"
    },
    "dentist": {
        "dentist", "dental", "dentistry", "orthodontist", "orthodontics", "teeth",
        "oral surgeon", "pediatric dentist", "cosmetic dentist", "dental clinic", "dental care"
    },
    "digital marketing": {
        "digital marketing", "marketing agency", "seo", "seo agency", "search engine optimization",
        "social media marketing", "smma", "advertising agency", "media agency", "ppc", "performance marketing",
        "growth marketing", "content marketing", "creative agency", "brand strategy", "online marketing"
    },
    "web development": {
        "web development", "web developer", "website design", "web design", "software agency",
        "web agency", "digital agency", "wordpress development", "custom web development", "frontend developer", "ui/ux design"
    },
    "web design": {
        "web design", "website design", "web developer", "web development", "ui/ux",
        "web designer", "digital agency", "creative agency", "website creation"
    },
    "lawyer": {
        "lawyer", "attorney", "law firm", "legal", "solicitor", "advocate",
        "barrister", "counsel", "legal services", "litigation", "personal injury lawyer"
    },
    "legal": {
        "lawyer", "attorney", "law firm", "legal", "solicitor", "advocate",
        "barrister", "counsel", "legal services", "litigation"
    },
    "accounting": {
        "accounting", "accountant", "cpa", "bookkeeping", "tax consultant",
        "chartered accountant", "tax preparation", "audit", "financial advisory"
    },
    "real estate": {
        "real estate", "realtor", "realty", "property management", "real estate agent",
        "real estate broker", "estate agency", "commercial real estate", "residential realty"
    },
    "landscaping": {
        "landscaping", "landscaper", "lawn care", "lawn mowing", "gardening",
        "tree service", "irrigation", "hardscaping", "grounds maintenance", "turf"
    },
    "restaurant": {
        "restaurant", "bistro", "eatery", "dining", "cafe", "grill", "steakhouse",
        "pizzeria", "taqueria", "trattoria", "brasserie", "diner", "cuisine"
    },
    "gym": {
        "gym", "fitness", "crossfit", "personal training", "health club",
        "workout", "pilates", "yoga studio", "bodybuilding", "martial arts"
    },
    "auto repair": {
        "auto repair", "mechanic", "mechanics", "car repair", "car mechanic", "car mechanics", "auto body", "oil change",
        "brake repair", "transmission", "tire shop", "auto service", "automotive", "garage", "autos"
    },
    "car mechanics": {
        "car mechanic", "car mechanics", "mechanic", "mechanics", "auto repair", "car repair", "auto body", "garage",
        "brake repair", "transmission", "auto service", "automotive", "oil change", "autos"
    },
    "mechanic": {
        "mechanic", "mechanics", "car mechanic", "car mechanics", "auto repair", "car repair", "auto body", "garage",
        "brake repair", "transmission", "auto service", "automotive", "oil change", "autos"
    },
}

# Incompatible/Irrelevant Negative Categories that must never cross-match
NEGATIVE_CATEGORY_PATTERNS: dict[str, list[str]] = {
    "religious": [
        "place_of_worship", "church", "cathedral", "mosque", "synagogue",
        "temple", "shrine", "chapel", "parish", "diocese", "monastery"
    ],
    "financial_institution": [
        "bank", "atm", "credit union", "bureau_de_change", "money transfer", "central bank"
    ],
    "dining_and_food": [
        "restaurant", "fast_food", "food_court", "pizza", "bakery",
        "bar", "pub", "bistro", "cafe", "ice_cream", "food_truck"
    ],
    "education": [
        "school", "kindergarten", "college", "university", "preschool",
        "elementary school", "high school", "academy", "primary school"
    ],
    "medical_pharmacy": [
        "pharmacy", "chemist", "drugstore", "hospital", "emergency room"
    ],
    "retail_grocery": [
        "supermarket", "grocery", "convenience_store", "department_store",
        "shopping_mall", "clothing_store", "shoe_store", "liquor_store"
    ],
    "civic_and_emergency": [
        "post_office", "police", "fire_station", "townhall", "courthouse", "prison", "embassy"
    ],
    "automotive_fuel": [
        "fuel", "gas_station", "charging_station", "parking", "parking_space"
    ]
}


@dataclass
class NicheRelevanceDecision:
    is_relevant: bool
    confidence_score: float
    matched_reason: str
    target_niche: str
    detected_category: str | None = None


class NicheRelevanceGate:
    """Evaluates whether a candidate business belongs to the requested target niche."""

    @classmethod
    def get_synonym_family(cls, target_niche: str) -> set[str]:
        """Returns normalized synonym set for the given niche."""
        t_clean = target_niche.lower().strip()
        
        # 1. Exact lookup
        if t_clean in NICHE_SYNONYMS_TAXONOMY:
            return NICHE_SYNONYMS_TAXONOMY[t_clean]

        # 2. Substring / plural matching
        for k, syns in NICHE_SYNONYMS_TAXONOMY.items():
            if k in t_clean or t_clean in k:
                return syns

        # 3. Dynamic tokenization & basic stemming fallback
        tokens = set(re.findall(r"\b[a-z]{3,}\b", t_clean))
        syns = set(tokens)
        syns.add(t_clean)
        # Add common singular/plural variants
        for tok in tokens:
            if tok.endswith("s") and len(tok) > 3:
                syns.add(tok[:-1])
            elif not tok.endswith("s"):
                syns.add(f"{tok}s")
                syns.add(f"{tok}ing")
                syns.add(f"{tok}er")
        return syns

    @classmethod
    def is_negative_category_conflict(cls, target_niche: str, detected_texts: list[str]) -> tuple[bool, str | None]:
        """Checks if detected category/name texts trigger an irrelevant negative category."""
        target_lower = target_niche.lower().strip()
        combined_text = " ".join([t.lower().strip() for t in detected_texts if t])

        for group_name, patterns in NEGATIVE_CATEGORY_PATTERNS.items():
            # If target niche is intentionally looking for this domain, skip negative check
            if any(re.search(r"\b" + re.escape(p) + r"\b", target_lower) for p in patterns):
                continue

            for pat in patterns:
                # Check for word boundary pattern match
                if re.search(r"\b" + re.escape(pat) + r"\b", combined_text):
                    return True, f"{group_name}:{pat}"

        return False, None

    @classmethod
    def evaluate_candidate(
        cls,
        business_name: str | None,
        category: str | None,
        raw_data: dict[str, Any] | None,
        target_niche: str,
        query_context: str | None = None,
    ) -> NicheRelevanceDecision:
        """Deterministically evaluates candidate niche relevance."""
        if not target_niche or not str(target_niche).strip():
            return NicheRelevanceDecision(
                is_relevant=True,
                confidence_score=0.7,
                matched_reason="DEFAULT_ACCEPT_NO_TARGET_NICHE",
                target_niche=target_niche or "",
            )

        name_str = (business_name or "").strip()
        cat_str = (category or "").strip()
        tags = (raw_data.get("tags") if isinstance(raw_data, dict) else {}) or {}
        properties = (raw_data.get("properties") if isinstance(raw_data, dict) else {}) or {}
        types_list = raw_data.get("types") if isinstance(raw_data, dict) and isinstance(raw_data.get("types"), list) else []
        
        tag_values = [str(v) for k, v in tags.items() if isinstance(v, str)]
        prop_values = [str(v) for k, v in properties.items() if isinstance(v, str)]
        types_str = " ".join([str(t) for t in types_list])
        
        all_signals = [name_str, cat_str, types_str] + tag_values + prop_values

        # 1. Negative Category Rejection (Fast Pre-Filter)
        has_neg_conflict, neg_reason = cls.is_negative_category_conflict(target_niche, all_signals)
        if has_neg_conflict:
            logger.info(
                f"[NicheRelevance] Candidate '{name_str}' REJECTED for target '{target_niche}' "
                f"due to conflicting negative category: {neg_reason}"
            )
            return NicheRelevanceDecision(
                is_relevant=False,
                confidence_score=0.0,
                matched_reason=f"NEGATIVE_CATEGORY_CONFLICT:{neg_reason}",
                target_niche=target_niche,
                detected_category=neg_reason,
            )

        # 2. Positive Synonym & Token Root Matching
        synonym_family = cls.get_synonym_family(target_niche)

        # Normalized signal strings (spaces replacing underscores)
        cat_clean = cat_str.lower().replace("_", " ")
        types_clean = types_str.lower().replace("_", " ")
        name_clean = name_str.lower().replace("_", " ")
        tags_clean = [tv.lower().replace("_", " ") for tv in tag_values]

        # 2a. Check explicit category/types
        for syn in synonym_family:
            syn_clean = syn.replace("_", " ")
            if re.search(r"\b" + re.escape(syn_clean) + r"\b", cat_clean) or re.search(r"\b" + re.escape(syn_clean) + r"\b", types_clean):
                return NicheRelevanceDecision(
                    is_relevant=True,
                    confidence_score=0.95,
                    matched_reason=f"EXACT_CATEGORY_MATCH ({syn})",
                    target_niche=target_niche,
                    detected_category=cat_str or syn,
                )

        # 2b. Check business name
        for syn in synonym_family:
            syn_clean = syn.replace("_", " ")
            if re.search(r"\b" + re.escape(syn_clean) + r"\b", name_clean):
                return NicheRelevanceDecision(
                    is_relevant=True,
                    confidence_score=0.90,
                    matched_reason=f"NAME_KEYWORD_MATCH ({syn})",
                    target_niche=target_niche,
                    detected_category=syn,
                )

        # 2c. Check raw OSM tags (e.g. craft=plumber, amenity=dentist, shop=bakery)
        for syn in synonym_family:
            syn_clean = syn.replace("_", " ")
            for tag_clean, orig_val in zip(tags_clean, tag_values):
                if re.search(r"\b" + re.escape(syn_clean) + r"\b", tag_clean):
                    return NicheRelevanceDecision(
                        is_relevant=True,
                        confidence_score=0.88,
                        matched_reason=f"TAG_KEYWORD_MATCH ({syn})",
                        target_niche=target_niche,
                        detected_category=orig_val,
                    )

        # 3. Fallback: No positive niche signals matched
        logger.info(f"[NicheRelevance] Candidate '{name_str}' failed niche relevance for '{target_niche}'.")
        return NicheRelevanceDecision(
            is_relevant=False,
            confidence_score=0.1,
            matched_reason="NO_NICHE_SIGNALS_MATCHED",
            target_niche=target_niche,
        )
