import pytest
from backend.app.enrichment.seo_analyzer import analyze_seo_html, SEOAnalyzer

def test_analyze_seo_html_full():
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <title>Best Plumbing Services in London | ABC Plumbing</title>
        <meta name="description" content="ABC Plumbing offers 24/7 emergency plumbing services across London. Call us today for fast and reliable service.">
        <link rel="canonical" href="https://www.abcplumbing.co.uk/">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta property="og:title" content="ABC Plumbing London">
        <meta property="og:description" content="Fast emergency plumbers.">
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Plumber",
            "name": "ABC Plumbing"
        }
        </script>
    </head>
    <body>
        <h1>Emergency Plumbing Services in London</h1>
        <h2>Our Services</h2>
        <h2>Customer Reviews</h2>
    </body>
    </html>
    """
    findings = analyze_seo_html(html, "https://www.abcplumbing.co.uk/")
    
    assert findings["status"] == "OBSERVED"
    assert findings["has_title"] is True
    assert findings["title"] == "Best Plumbing Services in London | ABC Plumbing"
    assert findings["title_length"] == 47
    assert findings["has_meta_description"] is True
    assert "24/7 emergency plumbing" in findings["meta_description"]
    assert findings["h1_count"] == 1
    assert findings["first_h1_text"] == "Emergency Plumbing Services in London"
    assert findings["h2_count"] == 2
    assert findings["has_canonical"] is True
    assert findings["canonical_url"] == "https://www.abcplumbing.co.uk/"
    assert findings["has_viewport_tag"] is True
    assert findings["has_opengraph"] is True
    assert findings["has_jsonld_schema"] is True
    assert "Plumber" in findings["schema_types"]

def test_analyze_seo_html_missing_tags():
    html = """
    <html>
    <head></head>
    <body>
        <p>Plain text with no headings, no title, no meta tags.</p>
    </body>
    </html>
    """
    findings = analyze_seo_html(html, "https://www.missingtags.com")
    
    assert findings["status"] == "OBSERVED"
    assert findings["has_title"] is False
    assert findings["title"] is None
    assert findings["has_meta_description"] is False
    assert findings["h1_count"] == 0
    assert findings["first_h1_text"] is None
    assert findings["has_viewport_tag"] is False
    assert findings["has_canonical"] is False
    assert findings["has_opengraph"] is False
    assert findings["has_jsonld_schema"] is False

def test_analyze_seo_html_empty():
    findings = analyze_seo_html("", "https://example.com")
    assert findings["status"] == "UNAVAILABLE"

def test_seo_analyzer_no_url():
    analyzer = SEOAnalyzer()
    res = analyzer.audit_url("")
    assert res["status"] == "UNAVAILABLE"
