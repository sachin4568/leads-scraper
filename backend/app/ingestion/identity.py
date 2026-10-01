from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

from sqlalchemy.orm import Session, joinedload

from backend.app.ingestion.ingestion import RawLead
from backend.app.models_phase2 import CanonicalLead


class IdentityConfidence(str, Enum):
    EXACT_MATCH = "EXACT_MATCH"
    HIGH_CONFIDENCE_MATCH = "HIGH_CONFIDENCE_MATCH"
    POSSIBLE_MATCH = "POSSIBLE_MATCH"
    NO_MATCH = "NO_MATCH"


@dataclass
class MatchExplanation:
    """Explainable identity decision details including matched signals and score."""

    match_level: IdentityConfidence
    score: float
    matched_signals: list[str] = field(default_factory=list)
    target_canonical_id: str | None = None
    reason: str = ""


def normalize_business_name(name: str | None) -> str:
    if not name:
        return ""
    clean = str(name).lower()
    # Strip common suffixes & location noise for string matching
    clean = re.sub(
        r"\b(pvt|ltd|inc|llc|group|studio|center|clinic|specialists|services|contractors|co)\b",
        "",
        clean,
    )
    clean = re.sub(r"[^a-z0-9]", "", clean)
    return clean


def normalize_domain(url: str | None) -> str:
    if not url:
        return ""
    clean = (
        str(url).lower().strip().replace("https://", "").replace("http://", "").replace("www.", "")
    )
    domain = clean.split("/")[0].split("?")[0]
    return domain


def normalize_phone(phone: str | None) -> str:
    if not phone:
        return ""
    clean = re.sub(r"[^0-9]", "", str(phone))
    if len(clean) > 10 and clean.startswith("91"):
        clean = clean[2:]
    return clean


def extract_coords(source_name: str, raw_payload: dict | None) -> tuple[float, float] | None:
    if not raw_payload:
        return None
    try:
        if source_name in ("google_places", "google_maps"):
            loc = raw_payload.get("geometry", {}).get("location", {})
            if loc:
                return float(loc.get("lat") or loc.get("latitude")), float(loc.get("lng") or loc.get("longitude"))
            loc_new = raw_payload.get("location")
            if isinstance(loc_new, dict):
                lat = loc_new.get("latitude") or loc_new.get("lat")
                lon = loc_new.get("longitude") or loc_new.get("lng")
                if lat is not None and lon is not None:
                    return float(lat), float(lon)
        elif source_name == "yelp":
            coords = raw_payload.get("coordinates", {})
            if coords:
                return float(coords["latitude"]), float(coords["longitude"])
        elif source_name == "osm_overpass":
            if "lat" in raw_payload and "lon" in raw_payload:
                return float(raw_payload["lat"]), float(raw_payload["lon"])
        
        for lat_key in ("latitude", "lat"):
            for lon_key in ("longitude", "lng", "lon"):
                if lat_key in raw_payload and lon_key in raw_payload:
                    return float(raw_payload[lat_key]), float(raw_payload[lon_key])
    except Exception:
        pass
    return None


def get_canonical_lead_coords(
    db: Session,
    cand: CanonicalLead,
    source_coords_cache: dict[tuple[str, str], tuple[float, float] | None] | None = None,
) -> tuple[float, float] | None:
    try:
        for obs in cand.observations:
            cache_key = (obs.source_name, obs.source_record_id)
            if source_coords_cache is not None and cache_key in source_coords_cache:
                coords = source_coords_cache[cache_key]
                if coords:
                    return coords
                continue

            from backend.app.models import SourceRecord
            src_rec = db.query(SourceRecord).filter(
                SourceRecord.source == obs.source_name,
                SourceRecord.source_id == obs.source_record_id
            ).first()
            if src_rec and src_rec.raw_data:
                coords = extract_coords(obs.source_name, src_rec.raw_data)
                if source_coords_cache is not None:
                    source_coords_cache[cache_key] = coords
                if coords:
                    return coords
            elif source_coords_cache is not None:
                source_coords_cache[cache_key] = None
    except Exception as e:
        logger.warning(f"Could not retrieve coordinates from SourceRecord: {e}")
    return None


class CanonicalIdentityEngine:
    """Multi-signal identity resolution engine guaranteeing location evidence and explainable matching."""

    def __init__(self) -> None:
        self._canonical_coords_cache: dict[str, tuple[float, float] | None] = {}
        self._source_coords_cache: dict[tuple[str, str], tuple[float, float] | None] = {}

    def evaluate_candidate_match(
        self, raw_lead: RawLead, cand: CanonicalLead
    ) -> MatchExplanation:
        """Evaluates match score and signals between a RawLead and a CanonicalLead."""
        norm_name = normalize_business_name(raw_lead.business_name)
        norm_phone = normalize_phone(raw_lead.phone)
        norm_domain = normalize_domain(raw_lead.website)
        norm_email = str(raw_lead.email).lower().strip() if raw_lead.email else ""
        norm_city = str(raw_lead.city).lower().strip() if raw_lead.city else ""

        # Check cross-country mismatch
        if raw_lead.country and cand.country:
            from backend.app.ingestion.canonical_location import LocationValidator
            c_raw = LocationValidator.normalize_country(raw_lead.country)
            c_cand = LocationValidator.normalize_country(cand.country)
            if c_raw and c_cand and c_raw[1] != c_cand[1]:
                return MatchExplanation(
                    match_level=IdentityConfidence.NO_MATCH,
                    score=0.0,
                    matched_signals=[],
                    target_canonical_id=cand.id,
                    reason=f"Country mismatch ({c_raw[1]} vs {c_cand[1]})",
                )

        cand_domain = normalize_domain(cand.canonical_domain)
        cand_phone = normalize_phone(cand.canonical_phone)
        cand_email = str(cand.canonical_email).lower().strip() if cand.canonical_email else ""
        cand_name = normalize_business_name(cand.business_name)
        cand_city = str(cand.city).lower().strip() if cand.city else ""

        matched_signals: list[str] = []
        score = 0.0

        # 1. Phone Match (Weight 0.4)
        if norm_phone and cand_phone and norm_phone == cand_phone:
            score += 0.40
            matched_signals.append("exact_phone")

        # 2. Domain Match (Weight 0.3)
        if norm_domain and cand_domain and norm_domain == cand_domain:
            score += 0.30
            matched_signals.append("exact_domain")
        elif norm_email and cand_email and norm_email == cand_email:
            score += 0.30
            matched_signals.append("exact_email")

        # 3. Fuzzy Name Match (Weight 0.2)
        import difflib
        name_ratio = difflib.SequenceMatcher(None, norm_name, cand_name).ratio() if (norm_name and cand_name) else 0.0
        score += name_ratio * 0.20
        if name_ratio >= 0.85:
            matched_signals.append(f"fuzzy_name_high_similarity({name_ratio:.2f})")
        elif name_ratio >= 0.60:
            matched_signals.append(f"fuzzy_name_mid_similarity({name_ratio:.2f})")

        # 4. Fallback to city/state matching
        if norm_city and cand_city and norm_city == cand_city:
            score += 0.08
            matched_signals.append("geo_city_fallback_match")
        elif raw_lead.state and cand.state and str(raw_lead.state).lower().strip() == str(cand.state).lower().strip():
            score += 0.04
            matched_signals.append("geo_state_fallback_match")

        # Combination Boosts
        if "exact_phone" in matched_signals and name_ratio >= 0.90:
            score += 0.25
            matched_signals.append("phone_name_combo_boost")
        elif "exact_domain" in matched_signals and name_ratio >= 0.90:
            score += 0.30
            matched_signals.append("domain_name_combo_boost")

        if score >= 0.85:
            level = IdentityConfidence.HIGH_CONFIDENCE_MATCH
        elif score >= 0.50:
            level = IdentityConfidence.POSSIBLE_MATCH
        else:
            level = IdentityConfidence.NO_MATCH

        return MatchExplanation(
            match_level=level,
            score=round(score, 2),
            matched_signals=matched_signals,
            target_canonical_id=cand.id,
            reason=f"Matched signals: {', '.join(matched_signals)}",
        )

    def resolve_identity(
        self, db: Session, raw_lead: RawLead
    ) -> tuple[CanonicalLead | None, MatchExplanation]:
        norm_name = normalize_business_name(raw_lead.business_name)
        norm_phone = normalize_phone(raw_lead.phone)
        norm_domain = normalize_domain(raw_lead.website)
        norm_email = str(raw_lead.email).lower().strip() if raw_lead.email else ""
        norm_city = str(raw_lead.city).lower().strip() if raw_lead.city else ""

        # 1. Check Deterministic Source Place ID / Stable ID (EXACT_MATCH)
        if raw_lead.source_record_id and raw_lead.source_name == "google_places":
            matched = (
                db.query(CanonicalLead)
                .filter(CanonicalLead.google_place_id == raw_lead.source_record_id)
                .first()
            )
            if matched:
                return matched, MatchExplanation(
                    match_level=IdentityConfidence.EXACT_MATCH,
                    score=1.0,
                    matched_signals=["google_place_id"],
                    target_canonical_id=matched.id,
                    reason="Exact Google Place ID match.",
                )

        # 2. Extract incoming lead coords once
        raw_payload = getattr(raw_lead, "raw_payload", None) or getattr(raw_lead, "raw_data", None)
        raw_coords = extract_coords(raw_lead.source_name, raw_payload)

        # 3. Query all candidates matching domain, phone, email, or name with joined observations
        query = db.query(CanonicalLead).options(joinedload(CanonicalLead.observations))
        candidates = query.all()

        # Batch-load coordinates if incoming lead has coordinates and some candidates lack cached coordinates
        if raw_coords:
            uncached_candidates = [c for c in candidates if c.id not in self._canonical_coords_cache]
            if uncached_candidates:
                uncached_source_ids = []
                for cand in uncached_candidates:
                    for obs in cand.observations:
                        if obs.source_record_id and (obs.source_name, obs.source_record_id) not in self._source_coords_cache:
                            uncached_source_ids.append(obs.source_record_id)

                if uncached_source_ids:
                    from backend.app.models import SourceRecord
                    src_recs = db.query(SourceRecord).filter(SourceRecord.source_id.in_(uncached_source_ids)).all()
                    for sr in src_recs:
                        coords = extract_coords(sr.source, sr.raw_data)
                        self._source_coords_cache[(sr.source, sr.source_id)] = coords

                for cand in uncached_candidates:
                    cand_c = None
                    for obs in cand.observations:
                        cand_c = self._source_coords_cache.get((obs.source_name, obs.source_record_id))
                        if cand_c:
                            break
                    self._canonical_coords_cache[cand.id] = cand_c

        best_candidate: CanonicalLead | None = None
        best_explanation: MatchExplanation | None = None

        for cand in candidates:
            cand_domain = normalize_domain(cand.canonical_domain)
            cand_phone = normalize_phone(cand.canonical_phone)
            cand_email = str(cand.canonical_email).lower().strip() if cand.canonical_email else ""
            cand_name = normalize_business_name(cand.business_name)
            cand_city = str(cand.city).lower().strip() if cand.city else ""

            # Check cross-country mismatch
            if raw_lead.country and cand.country:
                from backend.app.ingestion.canonical_location import LocationValidator
                c_raw = LocationValidator.normalize_country(raw_lead.country)
                c_cand = LocationValidator.normalize_country(cand.country)
                if c_raw and c_cand and c_raw[1] != c_cand[1]:
                    continue  # Cross-country entities can never be merged

            matched_signals: list[str] = []
            score = 0.0

            # 1. Phone Match (Weight 0.4)
            if norm_phone and cand_phone and norm_phone == cand_phone:
                score += 0.40
                matched_signals.append("exact_phone")

            # 2. Domain Match (Weight 0.3)
            if norm_domain and cand_domain and norm_domain == cand_domain:
                score += 0.30
                matched_signals.append("exact_domain")
            elif norm_email and cand_email and norm_email == cand_email:
                score += 0.30
                matched_signals.append("exact_email")

            # 3. Fuzzy Name Match (Weight 0.2)
            import difflib
            name_ratio = difflib.SequenceMatcher(None, norm_name, cand_name).ratio() if (norm_name and cand_name) else 0.0
            score += name_ratio * 0.20
            if name_ratio >= 0.85:
                matched_signals.append(f"fuzzy_name_high_similarity({name_ratio:.2f})")
            elif name_ratio >= 0.60:
                matched_signals.append(f"fuzzy_name_mid_similarity({name_ratio:.2f})")

            # 4. Geolocation Proximity Match (Weight 0.1)
            cand_coords = self._canonical_coords_cache.get(cand.id) if raw_coords else None

            geo_score = 0.0
            if raw_coords and cand_coords:
                from backend.app.sources.geo_utils import haversine_distance
                dist = haversine_distance(raw_coords[0], raw_coords[1], cand_coords[0], cand_coords[1])
                if dist <= 100:
                    geo_score = 1.0
                    matched_signals.append(f"geo_proximity_match_100m({dist:.1f}m)")
                elif dist <= 500:
                    geo_score = 0.9
                    matched_signals.append(f"geo_proximity_match_500m({dist:.1f}m)")
                elif dist <= 2000:
                    geo_score = 0.7
                    matched_signals.append(f"geo_proximity_match_2km({dist:.1f}m)")
                elif dist <= 5000:
                    geo_score = 0.5
                    matched_signals.append(f"geo_proximity_match_5km({dist:.1f}m)")
                else:
                    matched_signals.append(f"geo_proximity_distant({dist:.1f}m)")
            else:
                # Fallback to city/state matching
                if norm_city and cand_city and norm_city == cand_city:
                    geo_score = 0.8
                    matched_signals.append("geo_city_fallback_match")
                elif raw_lead.state and cand.state and str(raw_lead.state).lower().strip() == str(cand.state).lower().strip():
                    geo_score = 0.4
                    matched_signals.append("geo_state_fallback_match")

            score += geo_score * 0.10

            # Combination Boosts to handle high-confidence threshold
            if "exact_phone" in matched_signals and name_ratio >= 0.90:
                score += 0.25
                matched_signals.append("phone_name_combo_boost")
            elif "exact_domain" in matched_signals and name_ratio >= 0.90:
                score += 0.30
                matched_signals.append("domain_name_combo_boost")

            # Evaluate Match Level using weights and thresholds
            # High-confidence threshold (0.85) for auto-merge.
            # POSSIBLE_MATCH threshold (0.50) for link but flag.
            if score >= 0.85:
                level = IdentityConfidence.HIGH_CONFIDENCE_MATCH
            elif score >= 0.50:
                level = IdentityConfidence.POSSIBLE_MATCH
            else:
                level = IdentityConfidence.NO_MATCH

            explanation = MatchExplanation(
                match_level=level,
                score=round(score, 2),
                matched_signals=matched_signals,
                target_canonical_id=cand.id,
                reason=f"Matched signals: {', '.join(matched_signals)}",
            )

            if level in (IdentityConfidence.EXACT_MATCH, IdentityConfidence.HIGH_CONFIDENCE_MATCH):
                if not best_explanation or score > best_explanation.score:
                    best_candidate = cand
                    best_explanation = explanation
            elif level == IdentityConfidence.POSSIBLE_MATCH and not best_explanation:
                best_candidate = cand
                best_explanation = explanation

        if (
            best_candidate
            and best_explanation
            and best_explanation.match_level
            in (IdentityConfidence.EXACT_MATCH, IdentityConfidence.HIGH_CONFIDENCE_MATCH)
        ):
            return best_candidate, best_explanation

        if best_explanation and best_explanation.match_level == IdentityConfidence.POSSIBLE_MATCH:
            # POSSIBLE_MATCH return candidate explanation but NO automatic merge!
            return None, best_explanation

        return None, MatchExplanation(
            match_level=IdentityConfidence.NO_MATCH,
            score=0.0,
            matched_signals=[],
            target_canonical_id=None,
            reason="No matching canonical business entity found.",
        )
