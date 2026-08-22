from __future__ import annotations

import pytest

from backend.app.ml.productivity_error_taxonomy import ProductivityErrorTaxonomyClassifier
from backend.app.ml.productivity_explainability import ProductivityExplainabilityEngine
from backend.app.ml.productivity_holdout import ProductivityHoldoutEvaluator
from backend.app.ml.productivity_model_v1 import ProductivityBaseline, ProductivityModelV1
from backend.app.ml.productivity_readiness import TemporalLeakageError
from backend.app.ml.productivity_slice_analysis import ProductivitySliceAnalyzer
from backend.app.ml.productivity_trainer import EntityAwareSplitter, ProductivityDatasetAuditor
from backend.app.ml.productivity_validation import ProductivityValidationOptimizer
from backend.app.production.production_governance import (
    GovernanceApprovalError,
    ProductionGovernanceManager,
)


@pytest.fixture
def sample_productivity_dataset():
    records = []
    # 250 PRODUCTIVE records
    for i in range(250):
        records.append(
            {
                "canonical_lead_id": f"lead_prod_{i:03d}",
                "raw_data": {"canonical_lead_id": f"lead_prod_{i:03d}"},
                "prediction_time_features": {
                    "google_rating": 4.8,
                    "review_count": 40.0,
                    "phone_validity": 1.0,
                    "website_state": "active",
                    "source_record_count": 3.0,
                    "location_consistency": 1.0,
                    "contactability": "OWNER_CONTACT",
                    "business_maturity": "SMALL_BUSINESS",
                    "niche": "Dental Clinics",
                    "geography": "Dehradun",
                },
                "prediction": {"probability": 0.85, "decision": "GENUINE"},
                "human_outcome": {"final_productivity_outcome": "PRODUCTIVE"},
            }
        )
    # 250 UNPRODUCTIVE records
    for i in range(250):
        records.append(
            {
                "canonical_lead_id": f"lead_unprod_{i:03d}",
                "raw_data": {"canonical_lead_id": f"lead_unprod_{i:03d}"},
                "prediction_time_features": {
                    "google_rating": 4.1,
                    "review_count": 12.0,
                    "phone_validity": 1.0,
                    "website_state": "no_website",
                    "source_record_count": 1.0,
                    "location_consistency": 1.0,
                    "contactability": "GENERIC",
                    "business_maturity": "SMALL_BUSINESS",
                    "niche": "Solar",
                    "geography": "Dehradun",
                },
                "prediction": {"probability": 0.45, "decision": "GENUINE"},
                "human_outcome": {"final_productivity_outcome": "UNPRODUCTIVE"},
            }
        )
    return {"dataset_name": "productivity_real_candidate_v2", "records": records}


def test_productivity_dataset_integrity(sample_productivity_dataset) -> None:
    audit_res = ProductivityDatasetAuditor.audit_dataset(sample_productivity_dataset)
    assert audit_res.total_records_discovered == 500
    assert audit_res.eligible_resolved_records == 500
    assert audit_res.productive_count == 250
    assert audit_res.unproductive_count == 250
    assert audit_res.audit_passed is True


def test_entity_aware_split_isolation(sample_productivity_dataset) -> None:
    eligible = sample_productivity_dataset["records"]
    split_res = EntityAwareSplitter.split_dataset(eligible, seed=42)

    assert split_res.split_passed is True
    train_ids = {r["raw_data"]["canonical_lead_id"] for r in split_res.train_records}
    val_ids = {r["raw_data"]["canonical_lead_id"] for r in split_res.validation_records}
    holdout_ids = {r["raw_data"]["canonical_lead_id"] for r in split_res.holdout_records}

    assert len(train_ids.intersection(val_ids)) == 0
    assert len(train_ids.intersection(holdout_ids)) == 0
    assert len(val_ids.intersection(holdout_ids)) == 0
    assert len(split_res.holdout_hash) > 0


def test_temporal_feature_isolation_and_leakage_rejection(sample_productivity_dataset) -> None:
    bad_data = dict(sample_productivity_dataset)
    bad_data["records"][0]["prediction_time_features"]["productive"] = True
    with pytest.raises(TemporalLeakageError):
        ProductivityDatasetAuditor.audit_dataset(bad_data)


def test_baseline_and_challenger_training(sample_productivity_dataset) -> None:
    eligible = sample_productivity_dataset["records"]
    split_res = EntityAwareSplitter.split_dataset(eligible, seed=42)

    model_v1 = ProductivityModelV1(iterations=50, depth=3)
    X_train, y_train = model_v1.extract_features(split_res.train_records)
    X_val, y_val = model_v1.extract_features(split_res.validation_records)

    baseline_engine = ProductivityBaseline()
    base_res = baseline_engine.fit_and_evaluate(X_train, y_train, X_val, y_val)
    assert 0.0 <= base_res.logistic_regression_f1 <= 1.0

    model_v1.train(X_train, y_train)
    probs_val = model_v1.predict_proba(X_val)
    assert len(probs_val) == len(y_val)


def test_validation_only_threshold_tuning(sample_productivity_dataset) -> None:
    eligible = sample_productivity_dataset["records"]
    split_res = EntityAwareSplitter.split_dataset(eligible, seed=42)

    model_v1 = ProductivityModelV1(iterations=50, depth=3)
    X_train, y_train = model_v1.extract_features(split_res.train_records)
    X_val, y_val = model_v1.extract_features(split_res.validation_records)

    model_v1.train(X_train, y_train)
    probs_val = model_v1.predict_proba(X_val)

    opt_res = ProductivityValidationOptimizer.optimize_threshold(probs_val, y_val)
    assert 0.20 <= opt_res.best_threshold <= 0.80
    assert opt_res.best_f1 >= 0.0


def test_frozen_holdout_evaluation(sample_productivity_dataset) -> None:
    eligible = sample_productivity_dataset["records"]
    split_res = EntityAwareSplitter.split_dataset(eligible, seed=42)

    model_v1 = ProductivityModelV1(iterations=50, depth=3)
    X_train, y_train = model_v1.extract_features(split_res.train_records)
    X_holdout, y_holdout = model_v1.extract_features(split_res.holdout_records)

    model_v1.train(X_train, y_train)
    probs_holdout = model_v1.predict_proba(X_holdout)

    holdout_res = ProductivityHoldoutEvaluator.evaluate_holdout(
        probs_holdout, y_holdout, threshold=0.50
    )
    assert holdout_res.holdout_sample_size == len(y_holdout)
    assert 0.0 <= holdout_res.precision <= 1.0
    assert 0.0 <= holdout_res.recall <= 1.0
    assert 0.0 <= holdout_res.f1_score <= 1.0


def test_slice_analysis_explainability_and_error_taxonomy(sample_productivity_dataset) -> None:
    eligible = sample_productivity_dataset["records"]
    split_res = EntityAwareSplitter.split_dataset(eligible, seed=42)

    model_v1 = ProductivityModelV1(iterations=50, depth=3)
    X_train, y_train = model_v1.extract_features(split_res.train_records)
    X_holdout, y_holdout = model_v1.extract_features(split_res.holdout_records)
    model_v1.train(X_train, y_train)

    probs_holdout = model_v1.predict_proba(X_holdout)
    slice_res = ProductivitySliceAnalyzer.analyze_slices(
        split_res.holdout_records, probs_holdout, 0.50
    )
    assert "niche_slices" in slice_res

    explain_res = ProductivityExplainabilityEngine.compute_feature_importance(model_v1.model)
    assert len(explain_res["top_10_features"]) <= 10

    error_res = ProductivityErrorTaxonomyClassifier.audit_and_classify_errors(
        split_res.holdout_records, probs_holdout, 0.50
    )
    assert "false_positives_count" in error_res


def test_governance_challenger_registration_and_safety() -> None:
    gov = ProductionGovernanceManager()
    gov.register_challenger("productivity_model_v1")

    assert "productivity_model_v1" in gov.state.challenger_models_registered
    assert gov.state.champion_model_version == "real_model_v2_1"

    with pytest.raises(GovernanceApprovalError):
        gov.promote_challenger_to_champion("productivity_model_v1", human_approved=False)
