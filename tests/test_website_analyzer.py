from __future__ import annotations

from backend.app.intelligence.website_analyzer import WebsiteOpportunityAnalyzer


def test_website_analyzer_no_website() -> None:
    analyzer = WebsiteOpportunityAnalyzer()
    res = analyzer.analyze(None)
    assert res.has_website is False
    assert res.opportunity_score == 95
    assert "No website found" in res.signals[0]


def test_website_analyzer_unoptimized_site() -> None:
    analyzer = WebsiteOpportunityAnalyzer()
    html = "<html><head><title>Old Clinic</title></head><body><h1>Welcome</h1></body></html>"
    res = analyzer.analyze("http://oldclinic.com", html_content=html)

    assert res.has_website is True
    assert res.missing_ssl is True
    assert res.missing_mobile_viewport is True
    assert res.missing_analytics is True
    assert res.opportunity_score >= 80


def test_website_analyzer_modern_site() -> None:
    analyzer = WebsiteOpportunityAnalyzer()
    html = """
    <html>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <script src="https://www.googletagmanager.com/gtag/js?id=UA-12345"></script>
      </head>
      <body>Modern Dental Clinic</body>
    </html>
    """
    res = analyzer.analyze("https://moderndental.com", html_content=html)

    assert res.has_website is True
    assert res.missing_ssl is False
    assert res.missing_mobile_viewport is False
    assert res.missing_analytics is False
    assert res.opportunity_score == 10
