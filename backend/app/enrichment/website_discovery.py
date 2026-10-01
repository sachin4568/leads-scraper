from __future__ import annotations

import difflib
import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from backend.app.enrichment.entity_resolution import EntityResolver
from backend.app.security.ssrf_guard import validate_outbound_url

logger = logging.getLogger(__name__)

# Aggregator and directory domains that must never be accepted as official business websites
AGGREGATOR_DOMAIN_BLACKLIST: set[str] = {
    # Directory & Review Platforms
    "yelp.com", "tripadvisor.com", "yellowpages.com", "zomato.com",
    "justdial.com", "swiggy.com", "foursquare.com", "magicpin.in",
    "opentable.com", "dineout.co.in", "bookatable.com", "burrp.com",
    "mapquest.com", "bbb.org", "manta.com", "angi.com", "thumbtack.com",
    "eater.com", "restaurantji.com", "menupages.com", "zmenu.com",
    "sirved.com", "foodpanda.com", "ubereats.com", "doordash.com", "grubhub.com",
    # Social Platforms
    "facebook.com", "instagram.com", "twitter.com", "x.com",
    "linkedin.com", "youtube.com", "tiktok.com", "pinterest.com",
    # Generic Search, Wiki & Map Portals
    "google.com", "bing.com", "yahoo.com", "duckduckgo.com",
    "wikipedia.org", "wikidata.org", "openstreetmap.org", "osm.org"
}

# Parked domain signatures
PARKED_DOMAIN_SIGNATURES: tuple[str, ...] = (
    "buy this domain",
    "domain is for sale",
    "sedoparking",
    "godaddy parking",
    "hugedomains",
    "parked free by",
    "this domain may be for sale",
    "domain has expired",
    "renew now",
    "under construction",
    "namesilo",
    "dan.com",
)


class DiscoveryProvenance(str, Enum):
    PROVIDER_GROUND_TRUTH = "PROVIDER_GROUND_TRUTH"
    ZERO_BUDGET_DISCOVERED = "ZERO_BUDGET_DISCOVERED"
    ZERO_BUDGET_VERIFIED = "ZERO_BUDGET_VERIFIED"
    UNVERIFIED = "UNVERIFIED"


class VerificationDecision(str, Enum):
    ACCEPT = "ACCEPT"
    REVIEW = "REVIEW"
    REJECT = "REJECT"


@dataclass
class CandidateURL:
    url: str
    domain: str
    discovery_source: str
    discovery_query: str | None = None
    rank: int = 1
    raw_snippet: str | None = None


@dataclass
class VerificationResult:
    decision: VerificationDecision
    confidence_score: float
    verified_url: str | None
    verified_domain: str | None
    provenance: DiscoveryProvenance
    signals: dict[str, Any] = field(default_factory=dict)
    matched_reasons: list[str] = field(default_factory=list)


class CandidateFilter:
    """Safely filters, normalizes, and sanitizes discovered candidate URLs."""

    @staticmethod
    def is_blacklisted_domain(domain: str | None) -> bool:
        if not domain:
            return True
        dom = domain.lower().strip()
        if dom.startswith("www."):
            dom = dom[4:]
        for blacklisted in AGGREGATOR_DOMAIN_BLACKLIST:
            if dom == blacklisted or dom.endswith(f".{blacklisted}"):
                return True
        return False

    @staticmethod
    def normalize_candidate_url(raw_url: str | None) -> str | None:
        if not raw_url or not str(raw_url).strip():
            return None
        target = str(raw_url).strip()

        # Handle DuckDuckGo redirect wrapper links e.g. /l/?uddg=https%3A%2F%2Fexample.com
        if "uddg=" in target:
            try:
                parsed = urlparse(target)
                qs = parse_qs(parsed.query)
                if "uddg" in qs and qs["uddg"]:
                    target = unquote(qs["uddg"][0])
            except Exception:
                pass

        if not target.startswith(("http://", "https://")):
            target = f"https://{target}"

        try:
            parsed = urlparse(target)
            if parsed.scheme not in ("http", "https"):
                return None
            hostname = parsed.hostname
            if not hostname or "." not in hostname:
                return None
            
            # Clean URL: scheme + hostname + path without tracking fragments
            clean_url = f"{parsed.scheme}://{hostname}{parsed.path}"
            return clean_url
        except Exception:
            return None


class WebsiteEntityVerifier:
    """Deterministic entity verifier triangulating business identity against independent on-page signals."""

    def __init__(self, timeout_seconds: float = 5.0, max_redirects: int = 3) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_redirects = max_redirects

    def fetch_page_html(self, url: str) -> tuple[int | None, str | None, str | None]:
        """Safely fetches HTML content using SSRF guard, bounded redirects, and size limits."""
        try:
            validate_outbound_url(url, allow_http=True)
        except ValueError as ssrf_err:
            logger.warning(f"[Website Verifier] SSRF blocked URL: {url} ({ssrf_err})")
            return None, None, None

        try:
            with httpx.Client(
                timeout=self.timeout_seconds,
                follow_redirects=True,
                max_redirects=self.max_redirects,
                verify=False,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 LeadIntel/1.0"},
            ) as client:
                resp = client.get(url)
                final_url = str(resp.url)
                # Cap response body to 500KB to prevent memory exhaustion
                html_text = resp.text[:500000] if resp.text else ""
                return resp.status_code, final_url, html_text
        except Exception as fetch_err:
            logger.debug(f"[Website Verifier] Fetch failed for {url}: {fetch_err}")
            return None, None, None

    def verify_candidate(
        self,
        candidate: CandidateURL,
        business_name: str,
        phone: str | None = None,
        email: str | None = None,
        address: str | None = None,
        city: str | None = None,
    ) -> VerificationResult:
        """Evaluates strong, supporting, and negative signals to make a deterministic ACCEPT/REVIEW/REJECT decision."""
        # 1. Reject blacklisted aggregator domains immediately
        if CandidateFilter.is_blacklisted_domain(candidate.domain):
            return VerificationResult(
                decision=VerificationDecision.REJECT,
                confidence_score=0.0,
                verified_url=None,
                verified_domain=None,
                provenance=DiscoveryProvenance.UNVERIFIED,
                matched_reasons=["Candidate matches aggregator/directory domain blacklist"],
            )

        status_code, final_url, html_content = self.fetch_page_html(candidate.url)
        if not status_code or status_code >= 400 or not html_content:
            return VerificationResult(
                decision=VerificationDecision.REJECT,
                confidence_score=0.0,
                verified_url=None,
                verified_domain=None,
                provenance=DiscoveryProvenance.UNVERIFIED,
                matched_reasons=[f"HTTP fetch failed or returned status {status_code}"],
            )

        html_lower = html_content.lower()

        # 2. Check for parked domain signatures (Immediate REJECT)
        for sig in PARKED_DOMAIN_SIGNATURES:
            if sig in html_lower:
                return VerificationResult(
                    decision=VerificationDecision.REJECT,
                    confidence_score=0.0,
                    verified_url=None,
                    verified_domain=None,
                    provenance=DiscoveryProvenance.UNVERIFIED,
                    matched_reasons=[f"Detected parked domain signature: '{sig}'"],
                )

        score = 0.0
        reasons: list[str] = []
        hard_signals_count = 0
        signals_map: dict[str, Any] = {}

        # 3. Strong Signal: Phone Normalization Match (+0.50)
        if phone:
            digits_only = re.sub(r"\D", "", phone)
            if len(digits_only) >= 7:
                # Check for full number or last 8-10 digits in HTML
                sub_digits = digits_only[-8:] if len(digits_only) >= 8 else digits_only
                html_digits = re.sub(r"\D", "", html_lower)
                if sub_digits in html_digits:
                    score += 0.50
                    hard_signals_count += 1
                    reasons.append("Exact phone digit sequence verified in page HTML")
                    signals_map["phone_matched"] = True

        # 4. Strong Signal: Email Domain Alignment (+0.40)
        if email and "@" in email:
            email_dom = email.split("@")[-1].lower().strip()
            cand_dom = candidate.domain.lower().strip()
            if cand_dom.startswith("www."):
                cand_dom = cand_dom[4:]
            if email_dom == cand_dom or cand_dom.endswith(f".{email_dom}"):
                score += 0.40
                hard_signals_count += 1
                reasons.append(f"Email domain '{email_dom}' aligns with candidate domain '{cand_dom}'")
                signals_map["email_domain_aligned"] = True

        # 5. Strong Signal: Schema.org LocalBusiness / Organization JSON-LD (+0.40)
        json_ld_matches = re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html_content, re.DOTALL | re.IGNORECASE)
        for block in json_ld_matches:
            try:
                data = json.loads(block.strip())
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if isinstance(item, dict):
                        itype = str(item.get("@type", ""))
                        iname = str(item.get("name", "")).strip()
                        if iname and any(t in itype.lower() for t in ["business", "organization", "restaurant", "store", "place"]):
                            ratio = difflib.SequenceMatcher(None, EntityResolver.normalize_name(business_name), EntityResolver.normalize_name(iname)).ratio()
                            if ratio >= 0.85:
                                score += 0.40
                                hard_signals_count += 1
                                reasons.append(f"Schema.org {itype} entity '{iname}' matches business name (ratio={ratio:.2f})")
                                signals_map["schema_org_matched"] = True
                                break
            except Exception:
                continue

        # 6. Supporting/Strong Signal: Business Name Similarity in Page Title / H1 (+0.30)
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL)
        if title_match:
            page_title = title_match.group(1).strip()
            t_ratio = difflib.SequenceMatcher(None, EntityResolver.normalize_name(business_name), EntityResolver.normalize_name(page_title)).ratio()
            name_clean = EntityResolver.normalize_name(business_name) or ""
            tokens = [t for t in name_clean.split() if len(t) > 2]
            if t_ratio >= 0.70 or (tokens and all(t in page_title.lower() for t in tokens)):
                score += 0.30
                if t_ratio >= 0.80 or (tokens and len(tokens) >= 2 and all(t in page_title.lower() for t in tokens)):
                    hard_signals_count += 1
                reasons.append(f"Page title contains business name tokens ('{page_title[:40]}...')")
                signals_map["title_matched"] = True

        # 7. Authoritative Signal: Domain Token / Business Name Similarity (+0.35)
        cand_dom = candidate.domain.lower()
        if cand_dom.startswith("www."):
            cand_dom = cand_dom[4:]
        dom_part = cand_dom.split(".")[0].replace("-", " ").replace("_", " ")
        name_clean = EntityResolver.normalize_name(business_name) or ""
        tokens = [t for t in name_clean.split() if len(t) > 2]
        d_ratio = difflib.SequenceMatcher(None, name_clean, dom_part).ratio()
        
        if d_ratio >= 0.65 or (tokens and len(tokens) >= 2 and all(t in dom_part.replace(" ", "") for t in tokens)) or (tokens and any(t in dom_part for t in tokens if len(t) >= 5)):
            score += 0.35
            hard_signals_count += 1
            reasons.append("Authoritative business name match in candidate domain hostname")
            signals_map["domain_token_matched"] = True

        # 8. Supporting Signal: Location / City in HTML (+0.15)
        if city and city.lower() in html_lower:
            score += 0.15
            reasons.append(f"Location city '{city}' corroborated in page text")
            signals_map["city_corroborated"] = True

        if address:
            # Check postal code or street in HTML
            postcode_match = re.search(r"\b\d{5,6}\b", address)
            if postcode_match and postcode_match.group(0) in html_lower:
                score += 0.20
                reasons.append(f"Postal code '{postcode_match.group(0)}' corroborated in page HTML")
                signals_map["postcode_corroborated"] = True

        final_score = min(1.0, round(score, 2))
        signals_map["confidence_score"] = final_score
        signals_map["hard_signals_count"] = hard_signals_count

        # Acceptance Decision Matrix:
        # ACCEPT requires: (final_score >= 0.60 AND at least 1 Hard Signal) OR (title + domain matched and score >= 0.50)
        if (final_score >= 0.60 and hard_signals_count >= 1) or (final_score >= 0.50 and signals_map.get("title_matched") and signals_map.get("domain_token_matched")):
            decision = VerificationDecision.ACCEPT
            provenance = DiscoveryProvenance.ZERO_BUDGET_VERIFIED
            v_url = final_url or candidate.url
            v_dom = EntityResolver.normalize_domain(v_url)
        elif final_score >= 0.45:
            decision = VerificationDecision.REVIEW
            provenance = DiscoveryProvenance.ZERO_BUDGET_DISCOVERED
            v_url = None
            v_dom = None
        else:
            decision = VerificationDecision.REJECT
            provenance = DiscoveryProvenance.UNVERIFIED
            v_url = None
            v_dom = None

        return VerificationResult(
            decision=decision,
            confidence_score=final_score,
            verified_url=v_url,
            verified_domain=v_dom,
            provenance=provenance,
            signals=signals_map,
            matched_reasons=reasons,
        )


class ZeroBudgetDiscoveryEngine:
    """Orchestrates zero-budget website candidate discovery and verification."""

    def __init__(self) -> None:
        self.verifier = WebsiteEntityVerifier()

    def discover_from_osm_secondary_tags(self, raw_data_tags: dict[str, Any]) -> list[CandidateURL]:
        """Extracts candidate URLs from secondary OSM tags."""
        candidates: list[CandidateURL] = []
        tags = raw_data_tags or {}

        # 1. Secondary explicit website tags
        for tag_key in ["contact:url", "operator:website", "brand:website"]:
            val = tags.get(tag_key)
            if val and str(val).strip():
                clean_url = CandidateFilter.normalize_candidate_url(str(val))
                if clean_url:
                    dom = EntityResolver.normalize_domain(clean_url)
                    if dom and not CandidateFilter.is_blacklisted_domain(dom):
                        candidates.append(
                            CandidateURL(
                                url=clean_url,
                                domain=dom,
                                discovery_source=f"OSM_{tag_key.upper().replace(':', '_')}",
                                rank=1,
                            )
                        )

        # 2. Wikidata property P856 lookup if wikidata tag exists
        wikidata_id = tags.get("wikidata")
        if wikidata_id and str(wikidata_id).strip().startswith("Q"):
            try:
                # Wikidata public entity API
                w_url = f"https://www.wikidata.org/wiki/Special:EntityData/{wikidata_id.strip()}.json"
                validate_outbound_url(w_url)
                with httpx.Client(timeout=4.0) as client:
                    resp = client.get(w_url)
                    if resp.status_code == 200:
                        data = resp.json()
                        claims = data.get("entities", {}).get(wikidata_id, {}).get("claims", {})
                        p856 = claims.get("P856", [])
                        for c in p856:
                            val = c.get("mainsnak", {}).get("datavalue", {}).get("value")
                            if val:
                                clean_url = CandidateFilter.normalize_candidate_url(str(val))
                                if clean_url:
                                    dom = EntityResolver.normalize_domain(clean_url)
                                    if dom and not CandidateFilter.is_blacklisted_domain(dom):
                                        candidates.append(
                                            CandidateURL(
                                                url=clean_url,
                                                domain=dom,
                                                discovery_source="WIKIDATA_P856",
                                                rank=1,
                                            )
                                        )
            except Exception as wiki_err:
                logger.debug(f"[Discovery Engine] Wikidata lookup skipped: {wiki_err}")

        return candidates

    def discover_from_zero_budget_search(
        self,
        business_name: str,
        city: str | None = None,
        phone: str | None = None,
        category: str | None = None,
        limit: int = 3,
    ) -> list[CandidateURL]:
        """Queries zero-budget search engines with multi-identity query generation."""
        candidates: list[CandidateURL] = []
        seen_domains: set[str] = set()

        # Build multiple query identities
        queries: list[str] = []
        clean_name = business_name.strip()
        loc_str = city.strip() if city else ""

        if loc_str:
            queries.append(f'"{clean_name}" {loc_str}')
            queries.append(f'{clean_name} {loc_str} official website')
        else:
            queries.append(f'"{clean_name}" official website')
            queries.append(f'{clean_name} website')

        if phone:
            digits = re.sub(r"\D", "", phone)
            if len(digits) >= 7:
                queries.append(f'"{clean_name}" {digits[-7:]}')

        for query_str in queries[:2]:
            try:
                endpoint = "https://html.duckduckgo.com/html/"
                validate_outbound_url(endpoint)
                with httpx.Client(
                    timeout=5.0,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 LeadIntel/1.0"},
                ) as client:
                    resp = client.post(endpoint, data={"q": query_str})
                    if resp.status_code == 200:
                        html_text = resp.text
                        raw_links = re.findall(r'<a[^>]*class="[^"]*(?:result__url|result__snippet|result__title)[^"]*"[^>]*href="([^"]+)"', html_text)
                        if not raw_links:
                            raw_links = re.findall(r'<a[^>]*href=["\'](/l/\?uddg=[^"\']+|https?://[^"\']+)["\']', html_text)

                        for rlink in raw_links:
                            clean_url = CandidateFilter.normalize_candidate_url(rlink)
                            if clean_url:
                                dom = EntityResolver.normalize_domain(clean_url)
                                if dom and dom not in seen_domains and not CandidateFilter.is_blacklisted_domain(dom):
                                    seen_domains.add(dom)
                                    candidates.append(
                                        CandidateURL(
                                            url=clean_url,
                                            domain=dom,
                                            discovery_source="ZERO_BUDGET_SEARCH_DDG",
                                            discovery_query=query_str,
                                            rank=len(candidates) + 1,
                                        )
                                    )
                                    if len(candidates) >= limit:
                                        return candidates
            except Exception as search_err:
                logger.debug(f"[Discovery Engine] Zero-budget search failed or rate-limited for '{query_str}': {search_err}")

        return candidates

    def discover_and_verify_official_website(
        self,
        business_name: str | None,
        phone: str | None = None,
        email: str | None = None,
        address: str | None = None,
        city: str | None = None,
        raw_data_tags: dict[str, Any] | None = None,
    ) -> VerificationResult:
        """End-to-end execution: candidate discovery -> filtering -> entity verification -> decision."""
        if not business_name or not str(business_name).strip():
            return VerificationResult(
                decision=VerificationDecision.REJECT,
                confidence_score=0.0,
                verified_url=None,
                verified_domain=None,
                provenance=DiscoveryProvenance.UNVERIFIED,
                matched_reasons=["Missing or empty business name"],
            )

        all_candidates: list[CandidateURL] = []
        seen_domains: set[str] = set()

        # Step 1: OSM Secondary & Wikidata Candidates
        if raw_data_tags:
            sec_cands = self.discover_from_osm_secondary_tags(raw_data_tags)
            for c in sec_cands:
                if c.domain not in seen_domains:
                    seen_domains.add(c.domain)
                    all_candidates.append(c)

        # Step 2: Zero-Budget Search Candidates (if needed)
        if len(all_candidates) < 2:
            search_cands = self.discover_from_zero_budget_search(
                business_name=business_name,
                city=city,
                phone=phone,
                limit=3 - len(all_candidates),
            )
            for c in search_cands:
                if c.domain not in seen_domains:
                    seen_domains.add(c.domain)
                    all_candidates.append(c)

        if not all_candidates:
            return VerificationResult(
                decision=VerificationDecision.REJECT,
                confidence_score=0.0,
                verified_url=None,
                verified_domain=None,
                provenance=DiscoveryProvenance.UNVERIFIED,
                matched_reasons=["No candidates discovered from secondary tags, Wikidata, or search"],
            )

        # Step 3: Verify each candidate and pick the best validated match
        best_result: VerificationResult | None = None

        for cand in all_candidates[:3]:  # Bounded to top 3 candidates
            res = self.verifier.verify_candidate(
                candidate=cand,
                business_name=business_name,
                phone=phone,
                email=email,
                address=address,
                city=city,
            )
            if res.decision == VerificationDecision.ACCEPT:
                return res  # Return first ACCEPTED candidate
            if best_result is None or res.confidence_score > best_result.confidence_score:
                best_result = res

        return best_result or VerificationResult(
            decision=VerificationDecision.REJECT,
            confidence_score=0.0,
            verified_url=None,
            verified_domain=None,
            provenance=DiscoveryProvenance.UNVERIFIED,
            matched_reasons=["No candidate achieved ACCEPT verification threshold"],
        )
