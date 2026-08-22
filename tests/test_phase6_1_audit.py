from __future__ import annotations

from backend.app.enrichment.enrichment_engine import DeepFeatureEnrichmentEngine
from backend.app.ingestion.ingestion import GooglePlacesAdapter
from backend.app.ml.shadow_evaluation import FeatureDriftAnalyzer, ShadowEvaluator


def test_shadow_evaluation_overlap_join_and_metrics() -> None:
    predictions = [
        {"canonical_lead_id": f"lead_{i}", "predicted_decision": "GENUINE"} for i in range(1, 101)
    ]
    ground_truth = [
        {"canonical_lead_id": f"lead_{i}", "genuineness_outcome": "GENUINE"} for i in range(1, 11)
    ] + [
        {"canonical_lead_id": f"lead_{i}", "genuineness_outcome": "NOT_GENUINE"}
        for i in range(11, 21)
    ]

    metrics = ShadowEvaluator.evaluate_shadow_predictions(predictions, ground_truth)

    assert metrics.prediction_coverage_count == 100
    assert metrics.ground_truth_overlap_count == 20
    assert metrics.predictions_without_ground_truth_count == 80
    assert metrics.tp == 10
    assert metrics.fp == 10
    assert metrics.fn == 0
    assert metrics.tn == 0
    assert metrics.precision == 0.50
    assert metrics.recall == 1.0


def test_feature_drift_analyzer_zero_and_nonzero_drift() -> None:
    gp_adapter = GooglePlacesAdapter()
    raw = gp_adapter.normalize_payload(
        {
            "place_id": "ChIJ_drift_1",
            "name": "Drift Clinic",
            "types": ["Dental Clinics"],
            "website": "https://www.drift.com",
            "formatted_phone_number": "+91 98970 01001",
            "email": "contact@drift.com",
        }
    )
    ee = DeepFeatureEnrichmentEngine()
    snap = ee.enrich_lead("c_drift", raw)

    synth_stats = {
        "website_completeness_pct": 100.0,
        "phone_completeness_pct": 100.0,
        "email_completeness_pct": 100.0,
        "mean_response_time_ms": 450.0,
    }

    report = FeatureDriftAnalyzer.compare_synthetic_vs_real(synth_stats, [snap])

    assert len(report.feature_drifts) == 4
    drift_map = {d.feature_name: d for d in report.feature_drifts}

    assert drift_map["has_website"].drift_statistic == 0.0
    assert drift_map["has_website"].interpretation == "NO_MEANINGFUL_DRIFT"
    assert drift_map["mean_response_time_ms"].drift_statistic == 0.0
