from __future__ import annotations

from backend.app.intelligence.ads_analyzer import AdsOpportunityAnalyzer


def test_ads_analyzer_no_ads_no_pixels() -> None:
    analyzer = AdsOpportunityAnalyzer()
    res = analyzer.analyze(None)
    assert res.opportunity_score == 85
    assert res.has_meta_pixel is False
    assert res.has_google_tag is False
    assert "No active advertising campaigns" in res.signals[0]


def test_ads_analyzer_pixel_installed_no_ads() -> None:
    analyzer = AdsOpportunityAnalyzer()
    html = "<html><head><script>fbq('init', '12345');</script></head></html>"
    res = analyzer.analyze(html)

    assert res.has_meta_pixel is True
    assert res.opportunity_score == 75
    assert "Tracking pixels installed" in res.signals[0]


def test_ads_analyzer_active_ads() -> None:
    analyzer = AdsOpportunityAnalyzer()
    html = "<html><head><script>fbq('init', '12345');</script></head></html>"
    meta_prov = {"is_running_ads": True, "active_ad_count": 5}
    res = analyzer.analyze(html, meta_provenance_data=meta_prov)

    assert res.is_running_meta_ads is True
    assert res.opportunity_score == 20
    assert "actively running paid advertising" in res.signals[0]
