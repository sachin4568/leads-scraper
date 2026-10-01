from typing import Dict, Any, Tuple, Optional
import re
from urllib.parse import urlparse, urlunparse
import httpx
from bs4 import BeautifulSoup

def normalize_social_url(url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Given a raw URL, attempts to extract platform, handle/username, and normalized URL.
    Returns (platform, handle, normalized_url) or (None, None, None) if invalid.
    """
    if not url:
        return None, None, None
        
    try:
        parsed = urlparse(url)
    except Exception:
        return None, None, None
        
    scheme = "https"
    netloc = parsed.netloc.lower()
    
    if netloc.startswith("www."):
        netloc = netloc[4:]
    if netloc.startswith("m."):
        netloc = netloc[2:]
        
    path = parsed.path.strip("/")
    path_parts = path.split("/") if path else []
    
    platform = None
    handle = None
    
    if "instagram.com" in netloc:
        platform = "instagram"
        invalid_paths = {"p", "reel", "reels", "stories", "explore", "tags", "developer", "about", "legal", "directory", "accounts"}
        if path_parts and path_parts[0].lower() not in invalid_paths:
            handle = path_parts[0]
            
    elif "facebook.com" in netloc or "fb.com" in netloc:
        platform = "facebook"
        netloc = "facebook.com"
        invalid_paths = {"groups", "events", "pages", "share.php", "login", "watch", "story.php", "pg", "public", "help"}
        if path_parts and path_parts[0].lower() not in invalid_paths:
            if path_parts[0].lower() == "profile.php":
                query_params = parsed.query
                match = re.search(r'id=([^&]+)', query_params)
                if match:
                    handle = match.group(1)
            else:
                handle = path_parts[0]

    if platform and handle:
        normalized_path = f"/{handle}"
        normalized_url = urlunparse((scheme, netloc, normalized_path, "", "", ""))
        return platform, handle, normalized_url
        
    return None, None, None

def evaluate_social_identity(
    business_name: str, 
    handle: str, 
    platform_data: Dict[str, Any], 
    website_urls: list[str],
    email_addresses: list[str] = None
) -> str:
    """
    Deterministically evaluates if a social profile matches the business.
    Returns Classification:
    - VERIFIED_SOCIAL_PROFILE
    - LIKELY_SOCIAL_PROFILE
    - UNVERIFIED_SOCIAL_PROFILE
    - NOT_BUSINESS_PROFILE
    """
    if platform_data.get("is_personal", False):
        return "NOT_BUSINESS_PROFILE"
        
    score = 0
    
    # 1. Handle match (Max 30)
    clean_bname = re.sub(r'[^a-z0-9]', '', business_name.lower())
    clean_handle = re.sub(r'[^a-z0-9]', '', handle.lower())
    if clean_handle and (clean_handle == clean_bname):
        score += 30
    elif clean_handle and (clean_handle in clean_bname or clean_bname in clean_handle):
        score += 20
        
    # 2. Profile Name Match (Max 40)
    profile_name = (platform_data.get("profile_name") or "").lower()
    if profile_name and clean_bname:
        clean_pname = re.sub(r'[^a-z0-9]', '', profile_name)
        if clean_pname == clean_bname:
            score += 40
        elif clean_bname in clean_pname or clean_pname in clean_bname:
            score += 25
        
    # 3. Website Cross-link (Max 50)
    profile_website = (platform_data.get("website_url") or "").lower()
    if profile_website and website_urls:
        for w in website_urls:
            w_parsed = urlparse(w).netloc.replace("www.", "").lower()
            if w_parsed and w_parsed in profile_website:
                score += 50
                break

    # 4. Email Domain Cross-link (Max 20)
    if email_addresses and profile_website:
        for email in email_addresses:
            if "@" in email:
                domain = email.split("@")[1].lower()
                if domain and domain in profile_website:
                    score += 20
                    break

    if score >= 70:
        return "VERIFIED_SOCIAL_PROFILE"
    elif score >= 40:
        return "LIKELY_SOCIAL_PROFILE"
    else:
        return "UNVERIFIED_SOCIAL_PROFILE"

class SocialScraper:
    def fetch_profile(self, platform: str, url: str) -> Dict[str, Any]:
        """
        Executes actual HTTP request using httpx without stealth/anti-bot bypass.
        Returns observable public metrics or UNAVAILABLE/NOT_FOUND.
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
                "Accept-Language": "en-US,en;q=0.9",
            }
            resp = httpx.get(url, headers=headers, timeout=8.0, follow_redirects=True)
            
            # Check for access blocks or login redirects
            final_url = str(resp.url).lower()
            if resp.status_code in (403, 401, 429) or "login" in final_url or "accounts/login" in final_url:
                return {
                    "status": "UNAVAILABLE",
                    "error": f"HTTP {resp.status_code} or Login Redirect ({final_url})"
                }
                
            if resp.status_code == 404:
                return {"status": "NOT_FOUND"}
                
            if resp.status_code != 200:
                return {"status": "UNAVAILABLE", "error": f"HTTP {resp.status_code}"}
                
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Extract Open Graph & Meta tags
            og_title = soup.find("meta", property="og:title")
            title_tag = soup.find("title")
            profile_name = None
            if og_title and og_title.get("content"):
                profile_name = og_title["content"].split("|")[0].split("-")[0].strip()
            elif title_tag and title_tag.text:
                profile_name = title_tag.text.split("|")[0].split("-")[0].strip()
                
            og_desc = soup.find("meta", property="og:description")
            meta_desc = soup.find("meta", attrs={"name": "description"})
            desc_text = ""
            if og_desc and og_desc.get("content"):
                desc_text = og_desc["content"]
            elif meta_desc and meta_desc.get("content"):
                desc_text = meta_desc["content"]
                
            # Extract Followers
            followers = None
            followers_status = "UNKNOWN"
            follower_match = re.search(r'([0-9.,KMB]+)\s*Followers', desc_text, re.IGNORECASE)
            if follower_match:
                followers_str = follower_match.group(1).replace(",", "")
                if followers_str.isdigit():
                    followers = int(followers_str)
                    followers_status = "OBSERVED"
                elif followers_str == "0":
                    followers = 0
                    followers_status = "OBSERVED"
                    
            # Extract Website Link if visible
            website_url = None
            og_url = soup.find("meta", property="og:url")
            if og_url and og_url.get("content"):
                website_url = og_url["content"]

            if not profile_name or profile_name.lower() in ("instagram", "facebook"):
                if not followers and not desc_text:
                    return {"status": "UNAVAILABLE", "error": "Platform shell page returned without public profile metadata"}
                
            if profile_name and any(nf in profile_name.lower() for nf in ["page not found", "not available", "isn't available", "content not found"]):
                return {"status": "NOT_FOUND"}
                
            return {
                "status": "FOUND",
                "profile_name": profile_name,
                "followers": followers,
                "followers_status": followers_status,
                "website_url": website_url,
                "description": desc_text[:255] if desc_text else None
            }
        except Exception as e:
            return {"status": "UNAVAILABLE", "error": str(e)}
