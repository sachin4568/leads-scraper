import pytest
from unittest.mock import MagicMock, patch

from backend.app.enrichment.website_enricher import (
    ProductionWebsiteEnricher,
    PageFetchResult,
    ExtractedContacts,
    ExtractedSEOInfo,
    ExtractedBusinessInfo,
    WebsiteHealth,
)


def test_social_profiles_extractor_filters_share_and_intent_links():
    """Verifies that share buttons (/sharer, intent/tweet, shareArticle)
    are ignored, while authentic company profiles are extracted.
    """
    enricher = ProductionWebsiteEnricher()

    sample_html = """
    <!DOCTYPE html>
    <html>
    <head><title>Toronto Pro Plumbing</title></head>
    <body>
        <!-- Share buttons (Must be ignored) -->
        <a href="https://www.facebook.com/sharer/sharer.php?u=https://example.com">Share on FB</a>
        <a href="https://twitter.com/intent/tweet?url=https://example.com">Tweet this</a>
        <a href="https://www.linkedin.com/shareArticle?mini=true&url=https://example.com">Share on LinkedIn</a>

        <!-- Real company profiles (Must be captured) -->
        <footer>
            <a href="https://www.facebook.com/torontoproplumbing">Facebook</a>
            <a href="https://instagram.com/torontoproplumbing">Instagram</a>
            <a href="https://www.linkedin.com/company/toronto-pro-plumbing">LinkedIn</a>
            <a href="https://x.com/torontoplumbpro">Twitter</a>
            <a href="https://youtube.com/@torontoproplumbing">YouTube</a>
            <a href="https://tiktok.com/@torontoproplumb">TikTok</a>
        </footer>
    </body>
    </html>
    """

    socials = enricher._extract_social_profiles(sample_html)

    assert socials.get("facebook") == "https://www.facebook.com/torontoproplumbing"
    assert socials.get("instagram") == "https://instagram.com/torontoproplumbing"
    assert socials.get("linkedin") == "https://www.linkedin.com/company/toronto-pro-plumbing"
    assert socials.get("x") == "https://x.com/torontoplumbpro"
    assert socials.get("youtube") == "https://youtube.com/@torontoproplumbing"
    assert socials.get("tiktok") == "https://tiktok.com/@torontoproplumb"


def test_website_enricher_crawls_and_merges_subpages():
    """Verifies that contacts and social profiles located on subpages (/contact, /about)
    are fetched, parsed, and merged into the main enriched result.
    """
    enricher = ProductionWebsiteEnricher(max_pages=3)

    hp_html = """
    <html>
    <head><title>Metro Plumbing GTA</title></head>
    <body>
        <h1>Metro Plumbing GTA</h1>
        <a href="/contact">Contact Us</a>
        <a href="/about">About Us</a>
        <p>Call us today!</p>
    </body>
    </html>
    """

    contact_html = """
    <html>
    <head><title>Contact Us - Metro Plumbing GTA</title></head>
    <body>
        <a href="mailto:service@metroplumbinggta.ca">service@metroplumbinggta.ca</a>
        <a href="tel:+14165559876">(416) 555-9876</a>
        <a href="https://wa.me/14165559876">WhatsApp Chat</a>
        <a href="https://instagram.com/metroplumbinggta">Instagram</a>
    </body>
    </html>
    """

    def mock_fetch(url: str):
        if "contact" in url:
            return PageFetchResult(url=url, status_code=200, html=contact_html, response_time_ms=30.0, content_type="text/html")
        return PageFetchResult(url=url, status_code=200, html=hp_html, response_time_ms=25.0, content_type="text/html")

    with patch.object(enricher, "_fetch_page", side_effect=mock_fetch):
        res = enricher.enrich_website("https://metroplumbinggta.ca")

        assert res.health.is_reachable
        assert len(res.contacts.emails) > 0
        assert res.contacts.emails[0]["email"] == "service@metroplumbinggta.ca"
        assert len(res.contacts.phones) > 0
        assert "+14165559876" in res.contacts.phones[0]["phone"] or "(416) 555-9876" in res.contacts.phones[0]["phone"]
        assert len(res.contacts.whatsapp_links) > 0
        assert res.social_profiles.get("instagram") == "https://instagram.com/metroplumbinggta"
