from __future__ import annotations

from backend.app.ml.fn_analyzer import FalseNegativeAnalyzer, FalseNegativeRecord


def test_wilson_confidence_interval_calculation() -> None:
    # 120 TP out of 160 Actual Genuine Leads
    ci = FalseNegativeAnalyzer.calculate_wilson_confidence_interval(
        successes=120, trials=160, confidence=0.95
    )

    assert ci.estimate == 0.75
    assert ci.lower_bound > 0.65
    assert ci.upper_bound < 0.85
    assert ci.lower_bound < ci.estimate < ci.upper_bound


def test_probability_distribution_categorization() -> None:
    probs = [0.45, 0.42, 0.48, 0.35, 0.25, 0.22]
    dist = FalseNegativeAnalyzer.analyze_probability_distribution(probs)

    assert dist.min_prob == 0.22
    assert dist.max_prob == 0.48
    assert dist.near_threshold_count == 3
    assert dist.mid_low_confidence_count == 1
    assert dist.very_low_confidence_count == 2


def test_false_negative_dataset_exporter() -> None:
    rec = FalseNegativeRecord(
        canonical_lead_id="lead_fn_test_01",
        model_version="v2.0",
        feature_version="v1.0",
        model_probability=0.44,
        model_decision="REJECTED",
        human_genuineness="GENUINE",
        niche="Dental Clinics",
        geography="Dehradun",
        business_maturity="MICRO",
        website_state="no_website",
        contactability="OWNER_CONTACT",
        phone_state="VALID",
        email_state="MISSING",
        social_state="MISSING",
        sampling_source="EDGE_CASE",
        candidate_reason="NO_WEBSITE_GENUINE",
        validated_reason="PHONE_ONLY_GENUINE",
        attribution_type="MODEL_BEHAVIOR_ERROR",
        reviewer_1_decision="GENUINE",
        reviewer_2_decision="GENUINE",
        reviewers_agree=True,
    )

    payload = FalseNegativeAnalyzer.export_false_negative_dataset([rec], dataset_version="test_v1")
    assert payload["total_false_negatives"] == 1
    assert payload["records"][0]["validated_reason"] == "PHONE_ONLY_GENUINE"
