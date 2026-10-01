import pytest
import uuid
from backend.app.enrichment.social_providers import normalize_social_url, evaluate_social_identity, SocialScraper

def test_url_normalization_instagram():
    # Valid profiles
    plat, handle, norm = normalize_social_url("https://www.instagram.com/abcplumbing/?hl=en")
    assert plat == "instagram"
    assert handle == "abcplumbing"
    assert norm == "https://instagram.com/abcplumbing"
    
    # Invalid paths (e.g. posts, reels, accounts/login)
    plat, handle, norm = normalize_social_url("https://instagram.com/p/C123456/")
    assert handle is None
    
    plat, handle, norm = normalize_social_url("https://instagram.com/reel/C789/")
    assert handle is None

def test_url_normalization_facebook():
    # Valid profiles
    plat, handle, norm = normalize_social_url("https://m.facebook.com/abcplumbing")
    assert plat == "facebook"
    assert handle == "abcplumbing"
    assert norm == "https://facebook.com/abcplumbing"
    
    # Query param profiles
    plat, handle, norm = normalize_social_url("https://www.facebook.com/profile.php?id=10006371")
    assert plat == "facebook"
    assert handle == "10006371"
    assert norm == "https://facebook.com/10006371"
    
    # Invalid paths (e.g. groups, events)
    plat, handle, norm = normalize_social_url("https://facebook.com/groups/localplumbers")
    assert handle is None

def test_evaluate_social_identity_strong():
    # Name match + Handle match => Score = 30 (handle) + 40 (exact name) = 70 => VERIFIED
    classification = evaluate_social_identity(
        "ABC Plumbing", 
        "abcplumbing", 
        {"profile_name": "ABC Plumbing"}, 
        []
    )
    assert classification == "VERIFIED_SOCIAL_PROFILE"

def test_evaluate_social_identity_weak_handle_only():
    # Only handle similarity => Score = 20 => UNVERIFIED
    classification = evaluate_social_identity(
        "ABC Plumbing Services UK", 
        "abcplumbing123", 
        {}, 
        []
    )
    assert classification == "UNVERIFIED_SOCIAL_PROFILE"

def test_evaluate_social_identity_crosslink():
    # Website cross-link => Score = 50 => LIKELY
    classification = evaluate_social_identity(
        "Unknown Plumbers", 
        "unknown123", 
        {"website_url": "https://unknownplumbers.com"}, 
        ["https://unknownplumbers.com"]
    )
    assert classification == "LIKELY_SOCIAL_PROFILE"

def test_evaluate_social_identity_email_crosslink():
    # Website cross-link (50) + Email domain cross-link (20) => Score = 70 => VERIFIED
    classification = evaluate_social_identity(
        "Unknown Plumbers", 
        "unknown123", 
        {"website_url": "https://unknownplumbers.com"}, 
        ["https://unknownplumbers.com"],
        ["info@unknownplumbers.com"]
    )
    assert classification == "VERIFIED_SOCIAL_PROFILE"

def test_scraper_real_or_blocked():
    scraper = SocialScraper()
    # Test real fetch on public non-blocked endpoint or 404
    data = scraper.fetch_profile("instagram", "https://instagram.com/non_existent_profile_xyz_9999999")
    assert data["status"] in ("NOT_FOUND", "UNAVAILABLE")
