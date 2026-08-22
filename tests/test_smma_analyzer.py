from __future__ import annotations

from backend.app.intelligence import (
    AdsOpportunityAnalyzer,
    SEOOpportunityAnalyzer,
    SMMAOpportunityAnalyzer,
    SocialSignalAnalyzer,
    WebsiteOpportunityAnalyzer,
)


def test_smma_analyzer_high_opportunity() -> None:
    web_res = WebsiteOpportunityAnalyzer().analyze(None)  # 95
    seo_res = SEOOpportunityAnalyzer().analyze(None)  # 85
    social_res = SocialSignalAnalyzer().analyze(None)  # 90
    ads_res = AdsOpportunityAnalyzer().analyze(None)  # 85

    analyzer = SMMAOpportunityAnalyzer()
    res = analyzer.analyze(web_res, seo_res, social_res, ads_res)

    assert res.overall_smma_score >= 80
    assert res.priority_rank == "HIGH"
    assert "web_design" in res.breakdown_scores
    assert len(res.key_opportunities) > 0


def test_smma_analyzer_low_opportunity() -> None:
    html = """
    <html>
      <head>
        <title>Top NYC Dental Clinic - Apex Dental</title>
        <meta name="description" content="Best NYC Dental Clinic">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <script src="https://www.googletagmanager.com/gtag/js?id=UA-123"></script>
        <script>fbq('init', '12345');</script>
        <script type="application/ld+json">{"@type": "Dentist"}</script>
      </head>
      <body>
        <h1>Apex Dental Clinic</h1>
        <a href="https://facebook.com/apexdental">FB</a>
        <a href="https://instagram.com/apexdental">IG</a>
        <a href="https://linkedin.com/company/apexdental">LI</a>
        <a href="https://x.com/apexdental">X</a>
      </body>
    </html>
    """
    web_res = WebsiteOpportunityAnalyzer().analyze("https://apexdental.com", html)
    seo_res = SEOOpportunityAnalyzer().analyze(html)
    social_res = SocialSignalAnalyzer().analyze(html)
    ads_res = AdsOpportunityAnalyzer().analyze(html, meta_provenance_data={"is_running_ads": True})

    analyzer = SMMAOpportunityAnalyzer()
    res = analyzer.analyze(web_res, seo_res, social_res, ads_res)

    assert res.overall_smma_score <= 30
    assert res.priority_rank == "LOW"
