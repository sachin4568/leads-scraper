from __future__ import annotations

from backend.app.enrichment.enrichment_engine import (
    BusinessEnrichmentSnapshot,
)
from backend.app.ml.v2_1_evaluator import ModelV21Evaluator
from backend.app.ml.v2_1_trainer import ModelV21Trainer


def test_non_web_feature_snapshot_attributes() -> None:
    snap = BusinessEnrichmentSnapshot(
        canonical_lead_id="lead_test_nw",
        business_name="Local Clinic",
        niche="Dental Clinics",
        google_place_id_present=True,
        google_rating=4.8,
        review_count=45,
        phone_validity_score=1.0,
        location_consistency_score=1.0,
        source_record_count=2,
    )

    assert snap.google_place_id_present is True
    assert snap.google_rating == 4.8
    assert snap.review_count == 45
    assert snap.phone_validity_score == 1.0


def test_v2_1_candidate_dataset_generation() -> None:
    trainer = ModelV21Trainer(random_seed=42)
    X, y, meta = trainer.generate_candidate_v3_dataset(num_records=100)

    assert X.shape == (100, 11)
    assert len(y) == 100
    assert len(meta) == 100
    assert "provenance" in meta[0]


def test_v2_1_model_training_and_holdout_evaluation(tmp_path) -> None:
    trainer = ModelV21Trainer(random_seed=42)
    X, y, meta = trainer.generate_candidate_v3_dataset(num_records=400)

    X_tr, y_tr = X[:280], y[:280]
    X_val, y_val = X[280:340], y[280:340]
    X_ho, y_ho = X[340:], y[340:]
    meta_ho = meta[340:]

    cat, lgb = trainer.train_challenger_v2_1(X_tr, y_tr, X_val, y_val, output_dir=tmp_path)
    tuning_res = trainer.optimize_validation_parameters(X_val, y_val)

    assert cat is not None
    assert lgb is not None
    assert 0.10 <= tuning_res.best_alpha <= 0.50

    ho_metrics = ModelV21Evaluator.evaluate_ensemble(
        holdout_name="real_holdout_v2_test",
        cat_model=cat,
        lgb_model=lgb,
        X_test=X_ho,
        y_test=y_ho,
        alpha=tuning_res.best_alpha,
        threshold=tuning_res.best_threshold,
        metadata=meta_ho,
    )

    assert ho_metrics.total_leads == 60
    assert 0.0 <= ho_metrics.precision <= 1.0
    assert 0.0 <= ho_metrics.recall <= 1.0
