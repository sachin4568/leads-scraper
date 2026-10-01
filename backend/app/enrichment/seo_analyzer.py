from typing import Dict, Any, Optional
import re
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup

def analyze_seo_html(html_content: str, url: str) -> Dict[str, Any]:
    """
    Parses HTML content to observe technical and on-page SEO signals.
    Returns a dictionary of objective findings.
    """
    if not html_content:
        return {
            "status": "UNAVAILABLE",
            "error": "Empty HTML content"
        }
        
    soup = BeautifulSoup(html_content, "html.parser")
    
    # 1. Title Tag
    title_tag = soup.find("title")
    title = title_tag.text.strip() if title_tag and title_tag.text else None
    title_length = len(title) if title else 0
    
    # 2. Meta Description
    meta_desc_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    if not meta_desc_tag:
        meta_desc_tag = soup.find("meta", property=re.compile(r"^og:description$", re.I))
        
    meta_description = meta_desc_tag.get("content", "").strip() if meta_desc_tag and meta_desc_tag.get("content") else None
    meta_description_length = len(meta_description) if meta_description else 0
    
    # 3. Heading Structure
    h1_tags = soup.find_all("h1")
    h1_count = len(h1_tags)
    first_h1_text = h1_tags[0].text.strip() if h1_tags and h1_tags[0].text else None
    
    h2_tags = soup.find_all("h2")
    h2_count = len(h2_tags)
    
    # 4. Canonical & Robots Meta
    canonical_tag = soup.find("link", rel=re.compile(r"^canonical$", re.I))
    canonical_url = canonical_tag.get("href", "").strip() if canonical_tag and canonical_tag.get("href") else None
    has_canonical = bool(canonical_url)
    
    robots_tag = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
    robots_meta = robots_tag.get("content", "").strip() if robots_tag and robots_tag.get("content") else None
    
    # 5. Mobile Readiness (Viewport meta)
    viewport_tag = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})
    has_viewport_tag = bool(viewport_tag)
    viewport_content = viewport_tag.get("content", "").strip() if viewport_tag and viewport_tag.get("content") else None
    
    # 6. Structured Data (OpenGraph & JSON-LD)
    og_tags = soup.find_all("meta", property=re.compile(r"^og:", re.I))
    has_opengraph = len(og_tags) > 0
    
    jsonld_scripts = soup.find_all("script", type=re.compile(r"application/ld\+json", re.I))
    has_jsonld_schema = len(jsonld_scripts) > 0
    schema_types = []
    if has_jsonld_schema:
        for script in jsonld_scripts:
            if script.text:
                matches = re.findall(r'"@type"\s*:\s*"([^"]+)"', script.text)
                schema_types.extend(matches)
                
    return {
        "status": "OBSERVED",
        "title": title,
        "title_length": title_length,
        "has_title": bool(title),
        "meta_description": meta_description,
        "meta_description_length": meta_description_length,
        "has_meta_description": bool(meta_description),
        "h1_count": h1_count,
        "first_h1_text": first_h1_text,
        "h2_count": h2_count,
        "has_canonical": has_canonical,
        "canonical_url": canonical_url,
        "robots_meta": robots_meta,
        "has_viewport_tag": has_viewport_tag,
        "viewport_content": viewport_content,
        "has_opengraph": has_opengraph,
        "has_jsonld_schema": has_jsonld_schema,
        "schema_types": list(set(schema_types))
    }

class SEOAnalyzer:
    def audit_url(self, url: str) -> Dict[str, Any]:
        """
        Executes HTTP request to analyze SEO elements of a given URL.
        """
        if not url:
            return {"status": "UNAVAILABLE", "error": "No URL provided"}
            
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5"
            }
            resp = httpx.get(url, headers=headers, timeout=10.0, follow_redirects=True)
            
            if resp.status_code != 200:
                return {
                    "status": "UNAVAILABLE",
                    "error": f"HTTP {resp.status_code}"
                }
                
            findings = analyze_seo_html(resp.text, str(resp.url))
            findings["final_url"] = str(resp.url)
            findings["http_status"] = resp.status_code
            return findings
            
        except Exception as e:
            return {
                "status": "UNAVAILABLE",
                "error": str(e)
            }
