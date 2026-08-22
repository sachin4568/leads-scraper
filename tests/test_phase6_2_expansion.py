from __future__ import annotations

from backend.app.feedback.double_review import DoubleReviewAnnotation, DoubleReviewManager
from backend.app.ml.error_taxonomy import ErrorAnalysisRecord, ErrorTaxonomyClassifier
from backend.app.ml.shadow_evaluation import ShadowEvaluator


def test_double_review_and_cohens_kappa() -> None:
    mgr = DoubleReviewManager()

    # 10 Overlapping Leads: 6 GENUINE/GENUINE, 2 NOT_GENUINE/NOT_GENUINE, 2 Disagreements
    for i in range(1, 7):
        mgr.submit_annotation(DoubleReviewAnnotation(f"lead_{i}", "reviewer_1", "GENUINE"))
        mgr.submit_annotation(DoubleReviewAnnotation(f"lead_{i}", "reviewer_2", "GENUINE"))

    for i in range(7, 9):
        mgr.submit_annotation(DoubleReviewAnnotation(f"lead_{i}", "reviewer_1", "NOT_GENUINE"))
        mgr.submit_annotation(DoubleReviewAnnotation(f"lead_{i}", "reviewer_2", "NOT_GENUINE"))

    mgr.submit_annotation(DoubleReviewAnnotation("lead_9", "reviewer_1", "GENUINE"))
    mgr.submit_annotation(DoubleReviewAnnotation("lead_9", "reviewer_2", "NOT_GENUINE"))

    mgr.submit_annotation(DoubleReviewAnnotation("lead_10", "reviewer_1", "NOT_GENUINE"))
    mgr.submit_annotation(DoubleReviewAnnotation("lead_10", "reviewer_2", "GENUINE"))

    report = mgr.calculate_inter_rater_agreement()

    assert report.total_double_reviewed == 10
    assert report.raw_agreement_count == 8
    assert report.raw_agreement_pct == 80.0
    assert report.disagreement_count == 2
    assert report.cohens_kappa is not None
    assert report.cohens_kappa > 0.0


def test_insufficient_double_review_handling() -> None:
    mgr = DoubleReviewManager()
    report = mgr.calculate_inter_rater_agreement()

    assert report.total_double_reviewed == 0
    assert report.interpretation == "INTER-RATER AGREEMENT INSUFFICIENT"


def test_error_taxonomy_classification_and_exporter() -> None:
    dis_type_fp, reason_fp = ErrorTaxonomyClassifier.classify_disagreement(
        model_decision="GENUINE",
        human_genuineness="NOT_GENUINE",
        feature_signals={"website_exists": False, "has_phone": True},
    )
    assert dis_type_fp == "FALSE_POSITIVE"
    assert reason_fp == "STALE_LISTING"

    dis_type_fn, reason_fn = ErrorTaxonomyClassifier.classify_disagreement(
        model_decision="REJECTED",
        human_genuineness="GENUINE",
        feature_signals={"website_exists": False, "has_phone": True, "is_sparse": True},
    )
    assert dis_type_fn == "FALSE_NEGATIVE"
    assert reason_fn == "PHONE_ONLY_GENUINE"

    rec = ErrorAnalysisRecord(
        canonical_lead_id="lead_err_01",
        sampling_source="HARD_NEGATIVE",
        feature_snapshot_version="v1.0",
        model_version="v1.1",
        probability=0.85,
        model_decision="GENUINE",
        human_genuineness="NOT_GENUINE",
        disagreement_type="FALSE_POSITIVE",
        validated_error_reason="STALE_LISTING",
        evidence_reference="Audit_ref_01",
        reviewer="reviewer_1",
        timestamp="2026-08-13T01:50:00Z",
    )

    payload = ErrorTaxonomyClassifier.export_error_analysis_dataset(
        [rec], dataset_version="test_v1"
    )
    assert payload["total_records"] == 1
    assert payload["false_positives_count"] == 1


def test_shadow_evaluation_specificity_and_negative_metrics() -> None:
    predictions = [
        {"canonical_lead_id": f"lead_{i}", "predicted_decision": "GENUINE"} for i in range(1, 11)
    ] + [
        {"canonical_lead_id": f"lead_{i}", "predicted_decision": "REJECTED"} for i in range(11, 21)
    ]

    ground_truth = [
        {"canonical_lead_id": f"lead_{i}", "genuineness_outcome": "GENUINE"} for i in range(1, 11)
    ] + [
        {"canonical_lead_id": f"lead_{i}", "genuineness_outcome": "NOT_GENUINE"}
        for i in range(11, 21)
    ]

    metrics = ShadowEvaluator.evaluate_shadow_predictions(predictions, ground_truth)

    assert metrics.tp == 10
    assert metrics.fp == 0
    assert metrics.fn == 0
    assert metrics.tn == 10
    specificity = round(metrics.tn / (metrics.tn + metrics.fp), 4)
    assert specificity == 1.0
