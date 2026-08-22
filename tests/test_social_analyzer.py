from __future__ import annotations

from backend.app.intelligence.social_analyzer import SocialSignalAnalyzer


def test_social_analyzer_no_profiles() -> None:
    analyzer = SocialSignalAnalyzer()
    res = analyzer.analyze(None)
    assert res.opportunity_score == 90
    assert res.missing_facebook is True
    assert "No social media profiles detected" in res.signals[0]


def test_social_analyzer_partial_profiles() -> None:
    analyzer = SocialSignalAnalyzer()
    html = '<a href="https://facebook.com/metrodental">Facebook</a>'
    res = analyzer.analyze(html)

    assert "facebook" in res.detected_profiles
    assert res.missing_facebook is False
    assert res.missing_instagram is True
    assert res.opportunity_score >= 50


def test_social_analyzer_complete_profiles() -> None:
    analyzer = SocialSignalAnalyzer()
    html = """
      <a href="https://facebook.com/metrodental">FB</a>
      <a href="https://instagram.com/metrodental">IG</a>
      <a href="https://linkedin.com/company/metrodental">LI</a>
      <a href="https://x.com/metrodental">X</a>
    """
    res = analyzer.analyze(html)

    assert res.missing_facebook is False
    assert res.missing_instagram is False
    assert res.missing_linkedin is False
    assert res.missing_x is False
    assert res.opportunity_score == 10
