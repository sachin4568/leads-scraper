from __future__ import annotations

from backend.app.intelligence.seo_analyzer import SEOOpportunityAnalyzer


def test_seo_analyzer_no_html() -> None:
    analyzer = SEOOpportunityAnalyzer()
    res = analyzer.analyze(None)
    assert res.opportunity_score == 85
    assert "HTML content unavailable" in res.signals[0]


def test_seo_analyzer_unoptimized_page() -> None:
    analyzer = SEOOpportunityAnalyzer()
    html = "<html><body><p>Welcome to our business</p></body></html>"
    res = analyzer.analyze(html)

    assert res.missing_title is True
    assert res.missing_meta_description is True
    assert res.missing_h1 is True
    assert res.missing_schema_org is True
    assert res.opportunity_score == 100


def test_seo_analyzer_optimized_page() -> None:
    analyzer = SEOOpportunityAnalyzer()
    html = """
    <html>
      <head>
        <title>Top Rated Dental Clinic in New York - Apex Dental</title>
        <meta name="description" content="Apex Dental provides comprehensive family dental services in NYC. Book online today!">
        <script type="application/ld+json">{"@context": "https://schema.org", "@type": "Dentist"}</script>
      </head>
      <body>
        <h1>Family & Cosmetic Dentistry in New York</h1>
      </body>
    </html>
    """
    res = analyzer.analyze(html)

    assert res.missing_title is False
    assert res.missing_meta_description is False
    assert res.missing_h1 is False
    assert res.missing_schema_org is False
    assert res.opportunity_score == 10
