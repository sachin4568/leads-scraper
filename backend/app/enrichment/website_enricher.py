from __future__ import annotations

import difflib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import unquote, urljoin, urlparse
import urllib.parse

import httpx

from backend.app.enrichment.email_verifier import EmailVerifier
from backend.app.enrichment.entity_resolution import EntityResolver
from backend.app.security.ssrf_guard import validate_outbound_url

logger = logging.getLogger(__name__)

# Technology signatures detected deterministically from HTML & headers
TECHNOLOGY_SIGNATURES: dict[str, list[str]] = {
    # CMS / Platforms
    "WordPress": ["wp-content", "wp-includes", "name=\"generator\" content=\"wordpress", "name='generator' content='wordpress"],
    "Shopify": ["cdn.shopify.com", "shopify.theme", "myshopify.com"],
    "Wix": ["wix.com", "wixstatic.com", "static.parastorage.com"],
    "Squarespace": ["squarespace.com", "static1.squarespace.com"],
    "Webflow": ["webflow.com", "data-wf-page", "data-wf-site"],
    "WooCommerce": ["woocommerce", "wc-blocks"],
    "Next.js": ["__next_data__", "_next/static"],
    # Analytics & Pixels
    "Google Analytics": ["gtag(", "google-analytics.com/analytics.js", "ga('create'"],
    "Google Tag Manager": ["googletagmanager.com/gtm.js", "googletagmanager.com/ns.html"],
    "Meta Pixel": ["connect.facebook.net/en_us/fbevents.js", "fbq('init'", "fbevents.js"],
    "Hotjar": ["static.hotjar.com", "hotjar-"],
    "Microsoft Clarity": ["clarity.ms/tag", "clarity.ms"],
    # CDN / Infra
    "Cloudflare": ["cloudflare", "cdnjs.cloudflare.com"],
}

SOCIAL_PATTERNS: dict[str, str] = {
    "facebook": r"https?://(?:www\.)?facebook\.com/[A-Za-z0-9_.-]+",
    "instagram": r"https?://(?:www\.)?instagram\.com/[A-Za-z0-9_.-]+",
    "linkedin": r"https?://(?:www\.)?linkedin\.com/(?:company|in)/[A-Za-z0-9_.-]+",
    "x": r"https?://(?:www\.)?(?:twitter|x)\.com/[A-Za-z0-9_.-]+",
    "youtube": r"https?://(?:www\.)?youtube\.com/(?:c/|channel/|user/|@)?[A-Za-z0-9_.-]+",
    "tiktok": r"https?://(?:www\.)?tiktok\.com/@[A-Za-z0-9_.-]+",
}

IGNORED_EMAIL_EXTENSIONS: set[str] = {
    "png", "jpg", "jpeg", "gif", "svg", "webp", "css", "js", "woff", "woff2", "ttf", "eot"
}

DECISION_MAKER_PREFIXES: set[str] = {
    "founder", "ceo", "owner", "president", "director", "managing.director",
    "co-founder", "cofounder", "principal", "chief", "head", "lead", "partner"
}

GENERIC_EMAIL_PREFIXES: set[str] = {
    "info", "contact", "hello", "support", "help", "sales", "team", "office",
    "general", "admin", "enquiries", "inquiries", "mail", "service", "frontdesk"
}


@dataclass
class PageFetchResult:
    url: str
    status_code: int | None
    html: str
    response_time_ms: float
    content_type: str
    headers: dict[str, str] = field(default_factory=dict)
    error: str | None = None


@dataclass
class ExtractedContacts:
    emails: list[dict[str, str]] = field(default_factory=list)      # [{"email": ..., "source_page": ...}]
    phones: list[dict[str, str]] = field(default_factory=list)      # [{"phone": ..., "source_page": ...}]
    addresses: list[dict[str, str]] = field(default_factory=list)   # [{"address": ..., "source_page": ...}]
    whatsapp_links: list[str] = field(default_factory=list)


@dataclass
class ExtractedBusinessInfo:
    business_name: str | None = None
    description: str | None = None
    category: str | None = None
    opening_hours: list[str] = field(default_factory=list)
    schema_types: list[str] = field(default_factory=list)
    schema_raw: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ExtractedSEOInfo:
    title: str | None = None
    meta_description: str | None = None
    canonical_url: str | None = None
    robots: str | None = None
    h1_tags: list[str] = field(default_factory=list)
    h2_tags: list[str] = field(default_factory=list)
    og_title: str | None = None
    og_description: str | None = None
    og_image: str | None = None
    twitter_card: str | None = None
    has_sitemap_link: bool = False
    seo_score: int = 100
    seo_issues: list[str] = field(default_factory=list)


@dataclass
class WebsiteHealth:
    is_reachable: bool = False
    http_status: int | None = None
    is_https: bool = False
    final_url: str | None = None
    response_time_ms: float | None = None
    pages_fetched_count: int = 0
    total_bytes_downloaded: int = 0
    ssl_valid: bool = False


@dataclass
class EnrichedWebsiteResult:
    domain: str
    target_url: str
    health: WebsiteHealth
    contacts: ExtractedContacts
    business_info: ExtractedBusinessInfo
    seo: ExtractedSEOInfo
    social_profiles: dict[str, str] = field(default_factory=dict)
    technologies: list[str] = field(default_factory=list)
    conflicts: dict[str, Any] = field(default_factory=dict)
    enrichment_timestamp: float = field(default_factory=time.time)


_GLOBAL_DOMAIN_CACHE: dict[str, tuple[float, EnrichedWebsiteResult]] = {}
_MAX_GLOBAL_CACHE_SIZE: int = 2000
_CACHE_TTL_SECONDS: float = 3600.0


class ProductionWebsiteEnricher:
    """Bounded, SSRF-safe, ₹0 production website intelligence extractor."""

    def __init__(self, timeout_seconds: float = 5.0, max_pages: int = 10, max_bytes_per_page: int = 500000) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_pages = max_pages
        self.max_bytes_per_page = max_bytes_per_page
        self._cache: dict[str, EnrichedWebsiteResult] = {}

    def _fetch_page(self, url: str) -> PageFetchResult:
        """Fetches a single page safely with SSRF protection, size caps, and timing."""
        try:
            validate_outbound_url(url, allow_http=True)
        except ValueError as ssrf_err:
            return PageFetchResult(
                url=url, status_code=None, html="", response_time_ms=0.0,
                content_type="", error=f"SSRF blocked: {ssrf_err}"
            )

        t0 = time.perf_counter()
        try:
            with httpx.Client(
                timeout=self.timeout_seconds,
                follow_redirects=True,
                max_redirects=3,
                verify=False,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 LeadIntel/1.0"},
            ) as client:
                resp = client.get(url)
                elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
                ctype = resp.headers.get("content-type", "").lower()
                
                # Check for HTML content
                if "text/html" not in ctype and "application/xhtml" not in ctype and ctype:
                    return PageFetchResult(
                        url=str(resp.url), status_code=resp.status_code, html="",
                        response_time_ms=elapsed_ms, content_type=ctype,
                        error="Non-HTML Content-Type"
                    )

                body = resp.text[: self.max_bytes_per_page] if resp.text else ""
                headers_dict = {k.lower(): v for k, v in resp.headers.items()}
                return PageFetchResult(
                    url=str(resp.url), status_code=resp.status_code, html=body,
                    response_time_ms=elapsed_ms, content_type=ctype, headers=headers_dict
                )
        except Exception as e:
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            return PageFetchResult(
                url=url, status_code=None, html="", response_time_ms=elapsed_ms,
                content_type="", error=str(e)
            )

    def _discover_internal_links(self, base_url: str, html: str) -> list[str]:
        """Finds priority contact, about, and services links from HTML."""
        links: list[str] = []
        parsed_base = urlparse(base_url)
        base_domain = parsed_base.netloc.lower()

        # Find all href attributes
        raw_hrefs = re.findall(r'<a[^>]*href=["\']([^"\']+)["\']', html, re.IGNORECASE)
        # Prioritize pages where personal and owner emails are published
        priority_keywords = [
            "founder", "owner", "leadership", "management", "team", "our-team",
            "staff", "people", "meet", "executive", "executives", "directors",
            "principals", "doctor", "doctors", "agents", "attorneys", "lawyers",
            "partners", "bio", "about", "about-us", "who-we-are", "contact",
            "contact-us", "services"
        ]

        candidate_links: list[tuple[int, str]] = []
        seen: set[str] = {base_url.rstrip("/")}

        for href in raw_hrefs:
            href_clean = href.strip()
            if not href_clean or href_clean.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            
            full_url = urljoin(base_url, href_clean)
            parsed = urlparse(full_url)
            
            # Same domain only
            if parsed.netloc.lower() != base_domain:
                continue
            
            query_part = f"?{parsed.query}" if any(pg in parsed.query.lower() for pg in ("page=", "p=", "pg=")) else ""
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/") + query_part
            if clean_url in seen:
                continue

            # Check for keyword matches — only add to seen (and dedup) on a match,
            # so that non-matching URLs remain available for the fallback loop below.
            path_lower = parsed.path.lower()
            for rank, kw in enumerate(priority_keywords):
                if kw in path_lower:
                    seen.add(clean_url)
                    candidate_links.append((rank, clean_url))
                    break

        # Fallback: if no priority keyword pages were found, include any same-domain
        # internal links as generic candidates so the crawler visits them instead of
        # stopping at the homepage.
        if not candidate_links:
            for href in raw_hrefs:
                href_clean = href.strip()
                if not href_clean or href_clean.startswith(("#", "javascript:", "mailto:", "tel:")):
                    continue
                full_url = urljoin(base_url, href_clean)
                parsed = urlparse(full_url)
                if parsed.netloc.lower() != base_domain:
                    continue
                query_part = f"?{parsed.query}" if any(pg in parsed.query.lower() for pg in ("page=", "p=", "pg=")) else ""
                clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/") + query_part
                if clean_url in seen:
                    continue
                seen.add(clean_url)
                # Use a low priority rank so keyword matches always win when present.
                candidate_links.append((len(priority_keywords), clean_url))

        # Sort candidate links by keyword priority
        candidate_links.sort(key=lambda x: x[0])
        return [url for _, url in candidate_links]

    def scrape_facebook_about(self, facebook_url: str) -> list[dict[str, Any]]:
        """
        Attempts to fetch the Facebook Business About page and extract email addresses.

        Facebook aggressively blocks bots; this is a best-effort, single-fetch attempt.
        The URL is normalised to the /about path before fetching.

        Returns a list of email dicts in the same format as ExtractedContacts.emails
        (e.g., [{"email": "owner@example.com", "source": "facebook_about"}]).
        Returns an empty list on any error or when no emails are found.
        """
        try:
            # Normalise to the /about path
            parsed = urlparse(facebook_url)
            about_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}/about"

            page = self._fetch_page(about_url)
            if not page.html:
                return []

            contacts = self._extract_contacts_from_html(page.html, about_url)
            # Tag each email with its source for traceability
            for email_dict in contacts.emails:
                email_dict.setdefault("source", "facebook_about")
            return contacts.emails
        except Exception as fb_err:
            logger.warning(
                f"[WebsiteEnricher] Facebook About scrape failed for {facebook_url}: {fb_err}"
            )
            return []

    def _extract_contacts_from_html(self, html: str, page_url: str) -> ExtractedContacts:
        """Extracts emails, phones, addresses, and WhatsApp links from HTML text."""
        contacts = ExtractedContacts()
        html_lower = html.lower()

        # Comprehensive company/role prefixes that must NEVER be used for personal outreach
        role_prefixes = {
            "info", "contact", "contactus", "contact-us", "sales", "hello", "support",
            "marketing", "admin", "administrator", "office", "officeadmin", "help",
            "helpdesk", "inquiries", "inquiry", "enquiries", "enquiry", "billing",
            "accounts", "accounting", "press", "media", "jobs", "careers", "career",
            "webmaster", "postmaster", "hostmaster", "editor", "editors", "news",
            "newsletter", "campaigns", "booking", "bookings", "appointments", "appointment",
            "foundation", "general", "service", "services", "customerservice", "customer",
            "frontdesk", "reception", "desk", "mail", "team", "feedback", "donotreply",
            "no-reply", "noreply", "privacy", "legal", "compliance", "hr", "humanresources",
            "security", "orders", "order", "quote", "quotes", "estimate", "estimates",
            "inbox", "mailroom", "leads", "lead", "customercare", "helpcenter", "ops",
            "operations", "hi", "enquire", "receptionist", "reservations", "reservation",
            "dispatch", "main", "store", "shop", "hq", "founder", "cofounder", "owner",
            "ceo", "president", "director", "principal", "partner", "chief", "proprietor",
            "managingdirector", "generalmanager"
        }

        unwanted_automated_prefixes = {
            "noreply", "no-reply", "donotreply", "do-not-reply", "mailer-daemon",
            "postmaster", "hostmaster", "webmaster", "privacy", "legal",
            "compliance", "sentry", "abuse", "test", "example"
        }

        def is_unwanted_automated_email(local_p: str) -> bool:
            clean_lp = re.sub(r"[0-9_\-\.]+$", "", local_p.lower())
            if clean_lp in unwanted_automated_prefixes:
                return True
            for up in unwanted_automated_prefixes:
                if local_p.lower() == up or local_p.lower().startswith((f"{up}.", f"{up}_", f"{up}-")):
                    return True
            return False

        def is_role_email(local_p: str) -> bool:
            clean_lp = re.sub(r"[0-9_\-\.]+$", "", local_p.lower())
            if clean_lp in role_prefixes:
                return True
            for rp in role_prefixes:
                if local_p.lower() == rp or local_p.lower().startswith((f"{rp}.", f"{rp}_", f"{rp}-")):
                    return True
            return False

        # 1. Email extraction (mailto + regex + obfuscation + json-ld)
        # Strip script, style, svg, path, code, noscript tags to prevent false extractions of package versions or code snippets
        clean_html_text = re.sub(r'<(script|style|svg|path|code|noscript)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
        extracted_candidates: list[str] = []

        # 1a. mailto: links (including URL decoded)
        mailtos = re.findall(r'href=["\']mailto:([^"?\'\s>]+)', html, re.IGNORECASE)
        for m in mailtos:
            unquoted = urllib.parse.unquote(m).strip()
            if unquoted:
                extracted_candidates.append(unquoted)

        # 1b. Raw regex emails (enforces strictly alphabetic TLD of 2-24 chars, blocking software versions like intl-segmenter@11.7.10)
        raw_emails = re.findall(r'\b[a-zA-Z0-9_.+-]+@(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,24}\b', clean_html_text)
        extracted_candidates.extend(raw_emails)

        # 1c. Obfuscated emails: e.g. name [at] domain.com or name (at) domain.com
        obfuscated = re.findall(
            r'([a-zA-Z0-9_.+-]+)\s*(?:\[at\]|\(at\)|&#64;|%40|\s+at\s+)\s*((?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,24})',
            clean_html_text,
            re.IGNORECASE
        )
        for ob_user, ob_domain in obfuscated:
            extracted_candidates.append(f"{ob_user.strip()}@{ob_domain.strip()}")

        # 1d. JSON-LD schema emails
        json_lds_emails = re.findall(r'"email"\s*:\s*"([^"]+)"', html, re.IGNORECASE)
        extracted_candidates.extend(json_lds_emails)

        # Score, categorize, and deduplicate personal & business emails
        scored_emails: list[dict[str, Any]] = []
        seen_emails: set[str] = set()
        page_lower = page_url.lower()

        # Decision-maker title mapping
        decision_maker_titles = {
            "founder": "Founder",
            "co-founder": "Co-Founder",
            "owner": "Owner",
            "co-owner": "Co-Owner",
            "ceo": "CEO",
            "chief executive": "CEO",
            "president": "President",
            "managing director": "Managing Director",
            "director": "Director",
            "partner": "Partner",
            "principal": "Principal",
            "proprietor": "Proprietor",
            "dr": "Doctor",
            "doctor": "Doctor",
            "physician": "Physician",
            "surgeon": "Surgeon",
            "dentist": "Dentist",
            "attorney": "Attorney",
            "lawyer": "Lawyer",
            "general manager": "General Manager",
        }

        for em in extracted_candidates:
            clean_em = em.strip().lower().strip(".,;:!'\"<>(){}[] \t\n\r")
            if "@" not in clean_em:
                continue
            local_part, em_domain = clean_em.split("@", 1)
            ext = clean_em.split(".")[-1] if "." in clean_em else ""

            is_telemetry = (
                "sentry" in em_domain
                or "wixpress.com" in em_domain
                or "cloudflare.com" in em_domain
                or "schema.org" in em_domain
                or "w3.org" in em_domain
                or "example.com" in em_domain
                or "placeholder" in em_domain
            )

            # Strictly skip invalid, telemetry, and automated no-reply emails
            # Domain must have at least one dot and an alphabetic TLD of length 2-24
            if "." not in em_domain:
                continue
            tld = em_domain.split(".")[-1]
            if not tld.isalpha() or len(tld) < 2 or len(tld) > 24 or re.match(r"^[\d\.]+$", em_domain):
                continue

            if (
                ext in IGNORED_EMAIL_EXTENSIONS
                or is_telemetry
                or EmailVerifier.is_placeholder_email(clean_em)
                or is_unwanted_automated_email(local_part)
                or len(clean_em) > 100
                or clean_em in seen_emails
                or not re.match(r"^[a-zA-Z0-9_.+-]+@(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,24}$", clean_em)
            ):
                continue

            seen_emails.add(clean_em)

            # Determine surrounding context in HTML
            surrounding = ""
            match_pos = html_lower.find(clean_em)
            if match_pos != -1:
                surrounding = html_lower[max(0, match_pos - 150): min(len(html_lower), match_pos + 150)]

            is_role = is_role_email(local_part)
            detected_role = None
            matched_dm_key = None

            # Check surrounding text for decision-maker titles
            for kw, title_val in decision_maker_titles.items():
                if kw in surrounding:
                    matched_dm_key = kw
                    detected_role = title_val
                    break

            local_name_parts = [
                part for part in re.split(r"[._-]+", local_part)
                if part.isalpha() and len(part) > 1
            ]
            named_contact = len(local_name_parts) >= 2

            if detected_role and named_contact and not is_role:
                # Priority 1: Decision-maker business email
                priority_tier = 1
                contact_type = "decision_maker"
                score = 100.0
                if matched_dm_key and matched_dm_key in ("founder", "co-founder", "owner", "ceo", "president"):
                    score += 30.0
                if any(sep in local_part for sep in (".", "_", "-")):
                    score += 15.0
            elif is_role:
                # Priority 3: Official generic business email
                priority_tier = 3
                contact_type = "generic_official"
                score = 35.0
                detected_role = None
            else:
                # Priority 2: Named professional email
                priority_tier = 2
                contact_type = "named_professional"
                score = 65.0
                detected_role = "Professional Contact"
                if any(sep in local_part for sep in (".", "_", "-")):
                    score += 20.0
                elif len(local_part) >= 4 and local_part.isalpha():
                    score += 10.0
                if any(k in page_lower for k in ("team", "staff", "people", "about", "bio")):
                    score += 15.0

            norm_type = "decision_maker" if priority_tier == 1 else ("named_professional" if priority_tier == 2 else "generic")
            scored_emails.append({
                "email": clean_em,
                "source_page": page_url,
                "source_url": page_url,
                "priority_tier": priority_tier,
                "priority": priority_tier,
                "contact_type": contact_type,
                "type": norm_type,
                "role_or_title": detected_role,
                "context_snippet": surrounding.strip()[:150] if surrounding else page_url,
                "is_generic": is_role,
                "source_backed": True,
                "score": score,
            })

        # Sort highest priority tier first (1 > 2 > 3), then highest score
        scored_emails.sort(key=lambda x: (x["priority_tier"], -x["score"]))
        for em_item in scored_emails:
            contacts.emails.append(em_item)

        # 2. Phone extraction (tel + formatted phone regex) for conflict detection
        tels = re.findall(r'href=["\']tel:([^"\'\s]+)', html, re.IGNORECASE)
        seen_phones: set[str] = set()
        for p in tels:
            clean_p = p.strip()
            if clean_p and clean_p not in seen_phones:
                seen_phones.add(clean_p)
                contacts.phones.append({"phone": clean_p, "source_page": page_url})

        # Regex for visible international/local phone numbers (requiring explicit formatting or +)
        phone_matches = re.findall(
            r'(?:\+\d{1,3}[\s-]?)?(?:\(\d{2,4}\)[\s-]?|\d{2,4}[\s-])\d{3,4}[\s-]?\d{3,4}',
            html,
        )
        for pm in phone_matches:
            clean_p = pm.strip()
            if "." in clean_p or clean_p.startswith(("199", "200", "201", "202")):
                continue
            digits = re.sub(r"\D", "", clean_p)
            if 8 <= len(digits) <= 15 and clean_p not in seen_phones:
                seen_phones.add(clean_p)
                contacts.phones.append({"phone": clean_p, "source_page": page_url})

        # 3. WhatsApp link detection
        wa_links = re.findall(r'href=["\'](https?://(?:wa\.me|api\.whatsapp\.com)[^"\']+)["\']', html, re.IGNORECASE)
        contacts.whatsapp_links.extend(list(set(wa_links)))

        # 4. Schema.org address extraction
        json_lds = re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
        for jb in json_lds:
            try:
                data = json.loads(jb.strip())
                items = data if isinstance(data, list) else [data]
                for it in items:
                    if isinstance(it, dict) and "address" in it:
                        addr = it["address"]
                        if isinstance(addr, str):
                            contacts.addresses.append({"address": addr.strip(), "source_page": page_url})
                        elif isinstance(addr, dict):
                            parts = [
                                str(addr.get("streetAddress", "")),
                                str(addr.get("addressLocality", "")),
                                str(addr.get("addressRegion", "")),
                                str(addr.get("postalCode", "")),
                                str(addr.get("addressCountry", "")),
                            ]
                            formatted_addr = ", ".join([p for p in parts if p.strip()])
                            if formatted_addr:
                                contacts.addresses.append({"address": formatted_addr, "source_page": page_url})
            except Exception:
                continue

        return contacts

    def _extract_business_info(self, html: str) -> ExtractedBusinessInfo:
        """Extracts Schema.org entities, descriptions, categories, and opening hours."""
        b_info = ExtractedBusinessInfo()
        json_lds = re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
        
        for jb in json_lds:
            try:
                data = json.loads(jb.strip())
                items = data if isinstance(data, list) else [data]
                for it in items:
                    if isinstance(it, dict):
                        itype = str(it.get("@type", ""))
                        if itype:
                            b_info.schema_types.append(itype)
                            b_info.schema_raw.append(it)
                        if not b_info.business_name and "name" in it:
                            b_info.business_name = str(it["name"]).strip()
                        if not b_info.description and "description" in it:
                            b_info.description = str(it["description"]).strip()
                        if not b_info.category and "servesCuisine" in it:
                            b_info.category = str(it["servesCuisine"]).strip()
                        if "openingHours" in it:
                            oh = it["openingHours"]
                            if isinstance(oh, list):
                                b_info.opening_hours.extend([str(x) for x in oh])
                            elif isinstance(oh, str):
                                b_info.opening_hours.append(oh)
            except Exception:
                continue

        # Fallback meta description
        if not b_info.description:
            meta_desc = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
            if meta_desc:
                b_info.description = meta_desc.group(1).strip()

        return b_info

    def _extract_seo_info(self, html: str) -> ExtractedSEOInfo:
        """Analyzes title, headings, meta tags, OpenGraph, and Twitter cards."""
        seo = ExtractedSEOInfo()
        html_lower = html.lower()

        # Title
        t_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        if t_match:
            seo.title = t_match.group(1).strip()

        # Meta description
        d_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if d_match:
            seo.meta_description = d_match.group(1).strip()

        # Canonical URL
        c_match = re.search(r'<link[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if c_match:
            seo.canonical_url = c_match.group(1).strip()

        # Robots
        r_match = re.search(r'<meta[^>]*name=["\']robots["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if r_match:
            seo.robots = r_match.group(1).strip()

        # Headings
        seo.h1_tags = [h.strip() for h in re.findall(r'<h1[^>]*>(.*?)</h1>', html, re.IGNORECASE | re.DOTALL) if h.strip()]
        seo.h2_tags = [h.strip() for h in re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.IGNORECASE | re.DOTALL) if h.strip()][:5]

        # OpenGraph
        og_t = re.search(r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if og_t:
            seo.og_title = og_t.group(1).strip()
        og_d = re.search(r'<meta[^>]*property=["\']og:description["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if og_d:
            seo.og_description = og_d.group(1).strip()
        og_i = re.search(r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if og_i:
            seo.og_image = og_i.group(1).strip()

        # Twitter card
        tw_c = re.search(r'<meta[^>]*name=["\']twitter:card["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if tw_c:
            seo.twitter_card = tw_c.group(1).strip()

        # Sitemap reference
        seo.has_sitemap_link = "sitemap.xml" in html_lower or "/sitemap" in html_lower

        # Calculate SEO Opportunity/Health
        score = 100
        if not seo.title or len(seo.title) < 10:
            score -= 25
            seo.seo_issues.append("Title missing or short (< 10 chars)")
        if not seo.meta_description or len(seo.meta_description) < 20:
            score -= 25
            seo.seo_issues.append("Meta description missing or short")
        if not seo.h1_tags:
            score -= 20
            seo.seo_issues.append("Missing H1 heading tag")
        if not seo.canonical_url:
            score -= 15
            seo.seo_issues.append("Missing canonical tag")
        if not (seo.og_title or seo.og_image):
            score -= 15
            seo.seo_issues.append("Missing OpenGraph social meta tags")

        seo.seo_score = max(0, score)
        return seo

    def _extract_technologies(self, html: str, headers: dict[str, str]) -> list[str]:
        """Detects CMS, analytics, pixels, and frameworks deterministically."""
        detected: list[str] = []
        combined = html.lower() + " " + " ".join([f"{k}:{v}" for k, v in headers.items()]).lower()

        for tech, sigs in TECHNOLOGY_SIGNATURES.items():
            if any(sig.lower() in combined for sig in sigs):
                detected.append(tech)

        return detected

    def _extract_social_profiles(self, html: str) -> dict[str, str]:
        """Extracts social media profile links, filtering out share, intent, and tracking URLs."""
        socials: dict[str, str] = {}
        ignored_segments = (
            "sharer", "intent", "sharearticle", "/tr?", "dialog",
            "/plugins/", "/events/", "/groups/", "/policies/", "/help/", "/p/", "/reel/",
            "explore", "stories", "search", "login", "signup", "privacy", "terms", "hashtag", "sharer.php"
        )
        ignored_last_parts = {
            "intent", "share", "sharer", "sharearticle", "home", "about", "contact",
            "privacy", "terms", "facebook", "twitter", "instagram", "linkedin", "youtube",
            "tiktok", "login", "signup", "settings", "search", "explore", "hashtag",
            "direct", "stories", "feed", "tweet"
        }

        for plat, pat in SOCIAL_PATTERNS.items():
            matches = re.findall(pat, html, re.IGNORECASE)
            for m in matches:
                clean_m = m.strip().rstrip("/")
                if not any(ign in clean_m.lower() for ign in ignored_segments):
                    parts = clean_m.split("/")
                    last_part = parts[-1].lower() if parts else ""
                    if len(last_part) >= 2 and last_part not in ignored_last_parts:
                        socials[plat] = clean_m
                        break
        return socials

    def enrich_website(
        self,
        target_url: str,
        provider_phone: str | None = None,
        provider_email: str | None = None,
        provider_address: str | None = None,
    ) -> EnrichedWebsiteResult:
        """Performs bounded, multi-page website enrichment with conflict checking and caching."""
        clean_url = target_url.strip()
        if not clean_url.startswith(("http://", "https://")):
            clean_url = f"https://{clean_url}"

        domain = EntityResolver.normalize_domain(clean_url) or urlparse(clean_url).netloc

        # Check Instance Cache & Process-level Global Domain Cache
        if domain in self._cache:
            logger.info(f"[Website Enricher] Returning instance cached enrichment for domain: {domain}")
            return self._cache[domain]

        now_ts = time.time()
        if domain in _GLOBAL_DOMAIN_CACHE:
            cached_ts, cached_res = _GLOBAL_DOMAIN_CACHE[domain]
            if now_ts - cached_ts < _CACHE_TTL_SECONDS:
                logger.info(f"[Website Enricher] Returning global cached enrichment for domain: {domain}")
                self._cache[domain] = cached_res
                return cached_res

        # 1. Fetch Homepage
        hp_res = self._fetch_page(clean_url)
        
        health = WebsiteHealth(
            is_reachable=bool(hp_res.status_code and hp_res.status_code < 400),
            http_status=hp_res.status_code,
            is_https=clean_url.startswith("https://") or (hp_res.url and hp_res.url.startswith("https://")),
            final_url=hp_res.url if hp_res.status_code else clean_url,
            response_time_ms=hp_res.response_time_ms,
            pages_fetched_count=1 if hp_res.status_code else 0,
            total_bytes_downloaded=len(hp_res.html.encode("utf-8")),
            ssl_valid=bool(hp_res.status_code and hp_res.url and hp_res.url.startswith("https://")),
        )

        if not health.is_reachable or not hp_res.html:
            empty_res = EnrichedWebsiteResult(
                domain=domain,
                target_url=clean_url,
                health=health,
                contacts=ExtractedContacts(),
                business_info=ExtractedBusinessInfo(),
                seo=ExtractedSEOInfo(),
            )
            self._cache[domain] = empty_res
            return empty_res

        # 2. Extract Homepage Signals
        contacts = self._extract_contacts_from_html(hp_res.html, hp_res.url)
        b_info = self._extract_business_info(hp_res.html)
        seo = self._extract_seo_info(hp_res.html)
        socials = self._extract_social_profiles(hp_res.html)
        techs = self._extract_technologies(hp_res.html, hp_res.headers)

        # 3. Discover and Fetch Priority Subpages (bounded to max_pages)
        internal_links = self._discover_internal_links(hp_res.url, hp_res.html)
        subpages_to_fetch = internal_links[: self.max_pages - 1]

        # Use email map to deduplicate, upgrade, and prioritize candidates across subpages
        email_map: dict[str, dict[str, Any]] = {c["email"]: c for c in contacts.emails}

        for sub_url in subpages_to_fetch:
            # Bounded budget early exit: If a Priority 1 Decision-Maker email is already secured
            # and we have fetched at least 2 pages, stop crawling further pages to respect the time SLA
            has_decision_maker = any(e.get("priority_tier") == 1 for e in email_map.values())
            if has_decision_maker and health.pages_fetched_count >= 2:
                break

            sub_res = self._fetch_page(sub_url)
            health.pages_fetched_count += 1
            health.total_bytes_downloaded += len(sub_res.html.encode("utf-8"))

            if sub_res.status_code and sub_res.html:
                sub_contacts = self._extract_contacts_from_html(sub_res.html, sub_res.url)

                # Merge and upgrade deduplicated contacts
                for em in sub_contacts.emails:
                    em_key = em["email"]
                    if em_key not in email_map:
                        email_map[em_key] = em
                    else:
                        existing = email_map[em_key]
                        # Upgrade if discovered on a subpage with higher priority tier or higher score
                        if (em.get("priority_tier", 3) < existing.get("priority_tier", 3)) or (
                            em.get("priority_tier", 3) == existing.get("priority_tier", 3)
                            and em.get("score", 0.0) > existing.get("score", 0.0)
                        ):
                            email_map[em_key] = em

                existing_phones = {c["phone"] for c in contacts.phones}
                for ph in sub_contacts.phones:
                    if ph["phone"] not in existing_phones:
                        existing_phones.add(ph["phone"])
                        contacts.phones.append(ph)

                existing_addrs = {c["address"] for c in contacts.addresses}
                for ad in sub_contacts.addresses:
                    if ad["address"] not in existing_addrs:
                        existing_addrs.add(ad["address"])
                        contacts.addresses.append(ad)

                contacts.whatsapp_links = list(set(contacts.whatsapp_links + sub_contacts.whatsapp_links))

                # Merge social profiles
                sub_socials = self._extract_social_profiles(sub_res.html)
                for k, v in sub_socials.items():
                    if k not in socials:
                        socials[k] = v

        # Re-sort contacts.emails strictly by Priority Tier (Tier 1 > Tier 2 > Tier 3) and score
        contacts.emails = sorted(
            email_map.values(),
            key=lambda x: (x.get("priority_tier", 3), -x.get("score", 0.0))
        )

        # 4. Check for conflicts with provider ground truth
        conflicts: dict[str, Any] = {}
        if provider_phone and contacts.phones:
            prov_digits = re.sub(r"\D", "", provider_phone)
            web_digits = [re.sub(r"\D", "", p["phone"]) for p in contacts.phones]
            if prov_digits and not any(prov_digits[-8:] in wd for wd in web_digits if len(wd) >= 8):
                conflicts["phone"] = {
                    "provider_value": provider_phone,
                    "website_values": [p["phone"] for p in contacts.phones],
                    "conflict": True,
                }

        if provider_email and contacts.emails:
            prov_em = provider_email.strip().lower()
            web_ems = [e["email"].strip().lower() for e in contacts.emails]
            if prov_em and prov_em not in web_ems:
                conflicts["email"] = {
                    "provider_value": provider_email,
                    "website_values": web_ems,
                    "conflict": True,
                }

        result = EnrichedWebsiteResult(
            domain=domain,
            target_url=clean_url,
            health=health,
            contacts=contacts,
            business_info=b_info,
            seo=seo,
            social_profiles=socials,
            technologies=techs,
            conflicts=conflicts,
        )

        self._cache[domain] = result
        
        # Update Process-level cache with bounded capacity
        if len(_GLOBAL_DOMAIN_CACHE) >= _MAX_GLOBAL_CACHE_SIZE:
            # Evict first 10% oldest entries
            keys_to_evict = list(_GLOBAL_DOMAIN_CACHE.keys())[: (_MAX_GLOBAL_CACHE_SIZE // 10)]
            for k in keys_to_evict:
                _GLOBAL_DOMAIN_CACHE.pop(k, None)
        _GLOBAL_DOMAIN_CACHE[domain] = (now_ts, result)

        return result
