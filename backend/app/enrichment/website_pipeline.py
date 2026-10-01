import logging
import uuid
import re
import urllib.parse
from datetime import datetime, UTC
from typing import Dict, Any, Tuple

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select

from backend.app.models import RawLead, EnrichmentState, EvidenceRecord
from backend.app.database import SessionLocal
from backend.app.worker import celery_app

logger = logging.getLogger(__name__)

PLATFORM_DOMAINS = [
    "facebook.com", "instagram.com", "linkedin.com", "yelp.com", "tripadvisor.com", 
    "google.com", "yellowpages.com", "twitter.com", "x.com", "tiktok.com"
]

def normalize_url(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    return url

def get_base_domain(url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except:
        return ""

def is_platform_domain(url: str) -> bool:
    domain = get_base_domain(url)
    return any(domain == p or domain.endswith(f".{p}") for p in PLATFORM_DOMAINS)

def normalize_phone(phone: str) -> str:
    if not phone: return ""
    return re.sub(r'\D', '', phone)

def normalize_text(text: str) -> str:
    if not text: return ""
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    return ' '.join(text.split())

def check_identity(html_content: str, final_url: str, lead_name: str, lead_phone: str, lead_address: str) -> Tuple[int, Dict[str, Any]]:
    soup = BeautifulSoup(html_content, "html.parser")
    text = soup.get_text(separator=' ', strip=True).lower()
    
    signals = {
        "name_match": False,
        "phone_match": False,
        "address_match": False,
        "domain_relationship": False,
        "structured_data": False
    }
    
    score = 0
    
    # Domain relationship
    domain = get_base_domain(final_url)
    norm_name = normalize_text(lead_name) if lead_name else ""
    if norm_name:
        name_parts = [p for p in norm_name.split() if len(p) > 2]
        if name_parts and any(p in domain for p in name_parts):
            signals["domain_relationship"] = True
            score += 20
            
    # Name match
    if norm_name and norm_name in text:
        signals["name_match"] = True
        score += 30
        
    # Phone match
    norm_phone = normalize_phone(lead_phone) if lead_phone else ""
    if norm_phone and len(norm_phone) >= 7:
        digits_in_html = re.sub(r'\D', '', text)
        if norm_phone in digits_in_html:
            signals["phone_match"] = True
            score += 50
            
    # Address match
    norm_addr = normalize_text(lead_address) if lead_address else ""
    if norm_addr:
        addr_parts = [p for p in norm_addr.split() if len(p) > 2]
        # Match if at least 2 significant parts of the address appear nearby
        if len(addr_parts) >= 2 and all(p in text for p in addr_parts[:3]):
            signals["address_match"] = True
            score += 40

    # Structured data Check (Organization/LocalBusiness)
    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        if script.string and ("Organization" in script.string or "LocalBusiness" in script.string):
            signals["structured_data"] = True
            score += 10
            break
            
    # Cap score at 100
    score = min(score, 100)
    
    return score, signals

def fetch_and_evaluate_website(candidate_url: str, lead_name: str, lead_phone: str, lead_address: str) -> tuple[str, int, dict]:
    url = normalize_url(candidate_url)
    if not url:
        return "NO_WEBSITE", 100, {"reason": "Empty URL"}
        
    if is_platform_domain(url):
        return "NOT_BUSINESS_WEBSITE", 100, {"reason": "Platform domain detected", "candidate": candidate_url}

    details = {
        "candidate_url": candidate_url,
        "final_url": None,
        "http_status": None,
        "identity_signals": {},
        "identity_score": 0,
        "quality_signals": {},
        "observed_at": datetime.now(UTC).isoformat()
    }
    
    try:
        # TLS verify=True is the default. We explicitly enforce it now.
        with httpx.Client(timeout=10.0, follow_redirects=True, verify=True) as client:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
            resp = client.get(url, headers=headers)
            
            details["http_status"] = resp.status_code
            details["final_url"] = str(resp.url)
            
            if resp.status_code >= 400:
                details["reason"] = f"HTTP {resp.status_code}"
                return "BROKEN", 90, details
                
            if is_platform_domain(details["final_url"]):
                details["reason"] = "Redirected to platform domain"
                return "NOT_BUSINESS_WEBSITE", 100, details
                
            html = resp.text
            identity_score, identity_signals = check_identity(html, details["final_url"], lead_name, lead_phone, lead_address)
            details["identity_signals"] = identity_signals
            details["identity_score"] = identity_score
            
            # Extract Quality signals
            soup = BeautifulSoup(html, "html.parser")
            title_tag = soup.find("title")
            meta_desc = soup.find("meta", attrs={"name": "description"})
            h1_tag = soup.find("h1")
            viewport = soup.find("meta", attrs={"name": "viewport"})
            
            details["quality_signals"] = {
                "https": str(resp.url).startswith("https"),
                "has_title": bool(title_tag),
                "title_length": len(title_tag.text) if title_tag else 0,
                "has_meta_desc": bool(meta_desc),
                "has_h1": bool(h1_tag),
                "has_viewport": bool(viewport)
            }
            
            # Classification thresholds
            if identity_score >= 80:
                classification = "VERIFIED_BUSINESS_WEBSITE"
            elif identity_score >= 50:
                classification = "LIKELY_BUSINESS_WEBSITE"
            elif identity_score > 0:
                classification = "UNVERIFIED"
                details["reason"] = "Insufficient identity evidence"
            else:
                classification = "NOT_BUSINESS_WEBSITE"
                details["reason"] = "No identity signals matched"
                
            return classification, identity_score, details
                
    except httpx.ConnectTimeout:
        details["reason"] = "Connection Timeout"
        return "UNREACHABLE", 80, details
    except httpx.ReadTimeout:
        details["reason"] = "Read Timeout"
        return "UNREACHABLE", 80, details
    except httpx.ConnectError as e:
        details["reason"] = f"Connection Error: {str(e)}"
        return "UNREACHABLE", 80, details
    except Exception as e:
        # Includes SSLError and others
        logger.error(f"Error fetching website {url}: {e}")
        details["reason"] = f"Network or Parsing Error: {str(e)}"
        if "SSL" in str(type(e).__name__) or "cert" in str(e).lower():
            return "BROKEN", 80, details  # Broken due to SSL
        return "FAILED", 0, details

def save_evidence_transaction(db, workspace_id, raw_lead_id, classification, source, details, confidence_score):
    evidence = EvidenceRecord(
        workspace_id=workspace_id,
        raw_lead_id=raw_lead_id,
        field_name="website",
        status=classification,
        evidence_type="WEBSITE",
        classification=classification,
        confidence_score=confidence_score,
        source=source,
        details=details
    )
    db.add(evidence)
    db.commit()

@celery_app.task(bind=True, max_retries=3)
def enrich_website_pipeline(self, raw_lead_id: str, workspace_id: str):
    logger.info(f"Starting website pipeline for {raw_lead_id}")
    
    with SessionLocal() as db:
        lead = db.scalar(select(RawLead).where(RawLead.id == uuid.UUID(raw_lead_id)))
        if not lead:
            return
            
        state = db.scalar(select(EnrichmentState).where(EnrichmentState.raw_lead_id == lead.id))
        if not state:
            state = EnrichmentState(raw_lead_id=lead.id)
            db.add(state)
            
        state.website_status = "RUNNING"
        db.commit()
        
        candidate_url = lead.website
        business_name = lead.business_name
        phone = lead.phone
        address = lead.location

    if not candidate_url:
        classification = "NO_WEBSITE"
        confidence = 100
        details = {"reason": "No candidate URL provided"}
    else:
        classification, confidence, details = fetch_and_evaluate_website(
            candidate_url, business_name, phone, address
        )

    with SessionLocal() as db:
        state = db.scalar(select(EnrichmentState).where(EnrichmentState.raw_lead_id == uuid.UUID(raw_lead_id)))
        if state:
            if classification == "FAILED":
                state.website_status = "FAILED"
            elif classification == "UNREACHABLE":
                state.website_status = "UNKNOWN"
            else:
                state.website_status = "COMPLETED"
            
        save_evidence_transaction(
            db, 
            uuid.UUID(workspace_id), 
            uuid.UUID(raw_lead_id), 
            classification, 
            candidate_url or "system", 
            details, 
            confidence
        )
        db.commit()
