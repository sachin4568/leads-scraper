import logging
import uuid
import re
import urllib.parse
from datetime import datetime, UTC
from typing import List, Dict, Any, Set, Optional, Tuple

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select

from backend.app.models import RawLead, EnrichmentState, EvidenceRecord
from backend.app.database import SessionLocal
from backend.app.worker import celery_app
from backend.app.enrichment.email_verifier import verify_email
from backend.app.enrichment.website_pipeline import get_base_domain

logger = logging.getLogger(__name__)

GENERIC_PROVIDERS = [
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com", "icloud.com", "mail.com", "zoho.com"
]

ROLE_PREFIXES = [
    "info", "contact", "sales", "hello", "support", "marketing", "admin", "office",
    "help", "inquiries", "billing", "press", "media", "jobs", "careers", "webmaster",
    "editor", "editors", "news", "campaigns", "booking", "appointments", "foundation"
]

PRIORITY_KEYWORDS = ["contact", "about", "team", "staff", "support", "book", "appointment", "touch"]

MAX_CRAWL_PAGES = 5

def normalize_email(raw_email: str) -> str:
    """Normalize safe obfuscation and clean the email string."""
    email = raw_email.lower().strip()
    # Handle info [at] company.com
    email = re.sub(r'\s*\[at\]\s*', '@', email)
    email = re.sub(r'\s*\(at\)\s*', '@', email)
    email = re.sub(r'\s+@\s+', '@', email)
    # Basic trim of surrounding punctuation
    email = email.strip(".,;:!'\"<>(){}[] \t\n\r")
    return email

def is_valid_email_syntax(email: str) -> bool:
    """Basic syntax validation."""
    return bool(re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", email))

def classify_email(email: str, business_domain: str) -> Tuple[str, bool]:
    """
    Classify email into: ROLE_BASED, PERSONAL_BUSINESS, GENERIC_PROVIDER, INVALID, UNKNOWN
    Returns (classification, domain_match)
    """
    if not is_valid_email_syntax(email):
        return "INVALID", False
        
    parts = email.split('@')
    if len(parts) != 2:
        return "INVALID", False
        
    local, domain = parts[0], parts[1]
    
    # Check domain match (allow subdomain match)
    domain_match = False
    if business_domain and (domain == business_domain or domain.endswith(f".{business_domain}")):
        domain_match = True
        
    if domain in GENERIC_PROVIDERS:
        return "GENERIC_PROVIDER", False
        
    if local in ROLE_PREFIXES:
        return "ROLE_BASED", domain_match
        
    if domain_match:
        return "PERSONAL_BUSINESS", True
        
    return "UNKNOWN", False

def extract_emails_from_html(html: str, url: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    found = []
    seen = set()

    def add_email(raw: str, src_type: str, snippet: str):
        norm = normalize_email(raw)
        if is_valid_email_syntax(norm) and norm not in seen:
            seen.add(norm)
            found.append({
                "email": norm,
                "source_url": url,
                "found_on": urllib.parse.urlparse(url).path or "/",
                "source_type": src_type,
                "context_snippet": snippet[:150]
            })

    # 1. mailto: links
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().startswith("mailto:"):
            email_part = href[7:].split('?')[0]
            snippet = a.get_text(strip=True) or href
            add_email(email_part, "mailto_link", snippet)

    # 2. JSON-LD
    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        if script.string:
            # simple regex on json content
            matches = re.findall(r'"email"\s*:\s*"([^"]+)"', script.string, re.IGNORECASE)
            for m in matches:
                add_email(m, "json_ld", script.string[:150])

    # 3. Visible text regex (including obfuscations)
    text = soup.get_text(separator=' ', strip=True)
    # email regex looking for @ or [at] or (at)
    email_pattern = r'[a-zA-Z0-9_.+-]+(?:\s*@\s*|\s*\[at\]\s*|\s*\(at\)\s*)[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    matches = re.finditer(email_pattern, text)
    for match in matches:
        raw_match = match.group(0)
        start = max(0, match.start() - 30)
        end = min(len(text), match.end() + 30)
        snippet = text[start:end]
        add_email(raw_match, "visible_text", snippet)

    return found

def get_prioritized_internal_links(base_url: str, html: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    parsed_base = urllib.parse.urlparse(base_url)
    base_domain = parsed_base.netloc
    
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        full_url = urllib.parse.urljoin(base_url, href)
        parsed_link = urllib.parse.urlparse(full_url)
        
        # Only internal HTTP/HTTPS links
        if parsed_link.netloc == base_domain and parsed_link.scheme in ["http", "https"]:
            # Drop fragments
            clean_url = urllib.parse.urlunparse((parsed_link.scheme, parsed_link.netloc, parsed_link.path, '', parsed_link.query, ''))
            links.add(clean_url)
            
    # Sort by priority keywords
    def rank_link(url: str) -> int:
        lower_url = url.lower()
        if parsed_base.path == urllib.parse.urlparse(url).path:
            return 100 # Skip homepage itself
        for i, kw in enumerate(PRIORITY_KEYWORDS):
            if kw in lower_url:
                return i
        return 50 # Unprioritized
        
    sorted_links = sorted(list(links), key=rank_link)
    return sorted_links

def rank_emails(emails: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Preferred ordering:
    1. ROLE_BASED + business-domain match
    2. PERSONAL_BUSINESS + business-domain match
    3. ROLE_BASED + generic provider
    4. PERSONAL_BUSINESS + generic provider
    5. UNKNOWN
    """
    def get_rank(e: Dict[str, Any]) -> int:
        cls = e["classification"]
        dm = e["domain_match"]
        if cls == "ROLE_BASED" and dm: return 1
        if cls == "PERSONAL_BUSINESS" and dm: return 2
        if cls == "ROLE_BASED" and not dm: return 3
        if cls == "PERSONAL_BUSINESS" and not dm: return 4
        return 5

    return sorted(emails, key=get_rank)

def run_email_discovery(start_url: str, business_domain: str) -> Tuple[str, List[Dict[str, Any]], List[str]]:
    """Crawl bounded pages and extract emails."""
    emails_found: Dict[str, Dict[str, Any]] = {}
    pages_checked = []
    
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
            
            # 1. Fetch homepage
            resp = client.get(start_url, headers=headers)
            if resp.status_code >= 400:
                return "UNAVAILABLE", [], pages_checked
                
            final_start_url = str(resp.url)
            pages_checked.append(final_start_url)
            html = resp.text
            
            extracted = extract_emails_from_html(html, final_start_url)
            for e in extracted:
                emails_found[e["email"]] = e
                
            # 2. Get prioritized links
            links_to_check = get_prioritized_internal_links(final_start_url, html)[:MAX_CRAWL_PAGES-1]
            
            # 3. Crawl remaining pages
            for link in links_to_check:
                try:
                    p_resp = client.get(link, headers=headers)
                    if p_resp.status_code == 200:
                        pages_checked.append(str(p_resp.url))
                        p_extracted = extract_emails_from_html(p_resp.text, str(p_resp.url))
                        for e in p_extracted:
                            if e["email"] not in emails_found:
                                emails_found[e["email"]] = e
                except httpx.RequestError:
                    continue # Skip this page on error
                    
    except httpx.RequestError:
        return "UNAVAILABLE", [], pages_checked
    except Exception as e:
        logger.error(f"Error crawling {start_url}: {e}")
        return "FAILED", [], pages_checked

    results = list(emails_found.values())
    
    # Enrich with classification
    for e in results:
        cls, dm = classify_email(e["email"], business_domain)
        e["classification"] = cls
        e["domain_match"] = dm
        e["domain"] = e["email"].split("@")[1] if "@" in e["email"] else ""
        e["observed_at"] = datetime.now(UTC).isoformat()
        
    results = [
        e for e in results 
        if e["classification"] not in ("INVALID", "ROLE_BASED")
    ]
    
    # Add verification step
    for e in results:
        e["verification_status"] = verify_email(e["email"])

    results = rank_emails(results)
    
    status = "COMPLETED"
    if not results:
        status = "COMPLETED" # No email found after successful crawl
        
    return status, results, pages_checked

@celery_app.task(bind=True, max_retries=3)
def enrich_email_pipeline(self, raw_lead_id: str, workspace_id: str):
    logger.info(f"Starting email pipeline for {raw_lead_id}")
    
    start_url = None
    business_domain = ""
    
    # 1. State: Read verified website
    with SessionLocal() as db:
        lead = db.scalar(select(RawLead).where(RawLead.id == uuid.UUID(raw_lead_id)))
        if not lead:
            return
            
        state = db.scalar(select(EnrichmentState).where(EnrichmentState.raw_lead_id == lead.id))
        if not state:
            state = EnrichmentState(raw_lead_id=lead.id)
            db.add(state)
            
        state.email_status = "RUNNING"
        db.commit()
        
        # Look for verified website in evidence
        website_evidence = db.execute(
            select(EvidenceRecord)
            .where(EvidenceRecord.raw_lead_id == uuid.UUID(raw_lead_id))
            .where(EvidenceRecord.evidence_type == "WEBSITE")
            .where(EvidenceRecord.classification.in_(["VERIFIED_BUSINESS_WEBSITE", "LIKELY_BUSINESS_WEBSITE"]))
        ).scalars().first()
        
        if website_evidence and website_evidence.details:
            start_url = website_evidence.details.get("final_url") or website_evidence.details.get("candidate_url")
            
        # Fallback to RawLead if no verified website but still try to use it if it's not checked yet
        # However, instructions say: "Prefer crawling VERIFIED_BUSINESS_WEBSITE ... never blindly crawl UNVERIFIED ... platform URLs"
        if not start_url:
            pass # We won't blindly crawl. We rely on the website pipeline having run.

    # 2. Network Check
    if not start_url:
        # We can't crawl without a valid domain
        pipeline_status = "UNAVAILABLE"
        emails = []
    else:
        business_domain = get_base_domain(start_url)
        pipeline_status, emails, _ = run_email_discovery(start_url, business_domain)

    # 3. State: Write Evidence
    with SessionLocal() as db:
        state = db.scalar(select(EnrichmentState).where(EnrichmentState.raw_lead_id == uuid.UUID(raw_lead_id)))
        
        if state:
            state.email_status = pipeline_status

        if not emails and pipeline_status == "COMPLETED":
            # Document explicitly that search completed but found nothing
            evidence = EvidenceRecord(
                workspace_id=uuid.UUID(workspace_id),
                raw_lead_id=uuid.UUID(raw_lead_id),
                field_name="email",
                status="NO_PUBLIC_EMAIL_FOUND",
                evidence_type="EMAIL",
                classification="NO_PUBLIC_EMAIL_FOUND",
                confidence_score=100,
                source=start_url[:64],
                details={"reason": "Crawl completed but no valid email found."}
            )
            db.add(evidence)
        else:
            for idx, e in enumerate(emails):
                confidence = 100 if idx == 0 else max(10, 100 - (idx * 10))
                
                evidence = EvidenceRecord(
                    workspace_id=uuid.UUID(workspace_id),
                    raw_lead_id=uuid.UUID(raw_lead_id),
                    field_name="email",
                    status=e["verification_status"],
                    evidence_type="EMAIL",
                    classification=e["classification"],
                    confidence_score=confidence,
                    source=e["source_url"][:64],
                    details=e
                )
                db.add(evidence)
                
        db.commit()


