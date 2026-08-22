from __future__ import annotations

import pytest

from backend.app.ml.productivity_features import ProductivityFeatureExtractor
from backend.app.ml.productivity_readiness import TemporalLeakageError
from backend.app.ml.productivity_v1_1_error_taxonomy import ProductivityV11ErrorTaxonomyClassifier
from backend.app.ml.productivity_v1_1_holdout import ProductivityV11HoldoutEvaluator
from backend.app.ml.productivity_v1_1_trainer import (
    EntityAwareSplitterV2,
    ProductivityModelV11,
    ProductivityV11DatasetAuditor,
)
from backend.app.ml.productivity_v1_1_validation import ProductivityV11ValidationOptimizer
from backend.app.production.production_governance import (
    GovernanceApprovalError,
    ProductionGovernanceManager,
)


@pytest.fixture
def sample_v3_corpus():
    records = []
    # 100 PRODUCTIVE hard positives
    for i in range(100):
        records.append(
            {
                "canonical_lead_id": f"lead_v3_pos_{i:03d}",
                "raw_data": {"canonical_lead_id": f"lead_v3_pos_{i:03d}"},
                "prediction_time_features": {
                    "google_rating": 4.6,
                    "review_count": 15.0,
                    "phone_validity": 1.0,
                    "website_state": "no_website",
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
    # 100 UNPRODUCTIVE hard negatives (SERVICE_MISMATCH)
    for i in range(100):
        records.append(
            {
                "canonical_lead_id": f"lead_v3_neg_{i:03d}",
                "raw_data": {"canonical_lead_id": f"lead_v3_neg_{i:03d}"},
                "prediction_time_features": {
                    "google_rating": 4.9,
                    "review_count": 150.0,
                    "phone_validity": 1.0,
                    "website_state": "active",
                    "source_record_count": 5.0,
                    "location_consistency": 1.0,
                    "contactability": "RECEPTION",
                    "business_maturity": "SMALL_BUSINESS",
                    "niche": "Solar",
                    "geography": "Dehradun",
                },
                "prediction": {"probability": 0.88, "decision": "GENUINE"},
                "human_outcome": {"final_productivity_outcome": "UNPRODUCTIVE"},
            }
        )
    return {"dataset_name": "productivity_real_candidate_v3", "records": records}


def test_candidate_v3_dataset_auditor(sample_v3_corpus) -> None:
    res = ProductivityV11DatasetAuditor.audit_dataset(sample_v3_corpus)
    assert res.total_records_discovered == 200
    assert res.eligible_resolved_records == 200
    assert res.productive_count == 100
    assert res.unproductive_count == 100
    assert res.audit_passed is True


def test_productivity_feature_extractor_and_leakage_rejection(sample_v3_corpus) -> None:
    r = sample_v3_corpus["records"][0]
    vec = ProductivityFeatureExtractor.extract_features_vector(r)
    assert len(vec) == 12

    bad_r = dict(r)
    bad_r["prediction_time_features"]["deal_closed"] = True
    with pytest.raises(TemporalLeakageError):
        ProductivityFeatureExtractor.extract_features_vector(bad_r)


def test_entity_aware_split_v2_isolation(sample_v3_corpus) -> None:
    records = sample_v3_corpus["records"]
    split_res = EntityAwareSplitterV2.split_dataset(records, seed=42)

    assert split_res.split_passed is True
    train_ids = {r["raw_data"]["canonical_lead_id"] for r in split_res.train_records}
    val_ids = {r["raw_data"]["canonical_lead_id"] for r in split_res.validation_records}
    holdout_ids = {r["raw_data"]["canonical_lead_id"] for r in split_res.holdout_records}

    assert len(train_ids.intersection(val_ids)) == 0
    assert len(train_ids.intersection(holdout_ids)) == 0
    assert len(val_ids.intersection(holdout_ids)) == 0


def test_validation_only_threshold_tuning_penalizing_zero_specificity(sample_v3_corpus) -> None:
    records = sample_v3_corpus["records"]
    split_res = EntityAwareSplitterV2.split_dataset(records, seed=42)

    model_v11 = ProductivityModelV11(iterations=50, depth=3)
    X_train, y_train = ProductivityFeatureExtractor.extract_matrix(split_res.train_records)
    X_val, y_val = ProductivityFeatureExtractor.extract_matrix(split_res.validation_records)

    model_v11.train(X_train, y_train)
    probs_val = model_v11.predict_proba(X_val)

    opt_res = ProductivityV11ValidationOptimizer.optimize_threshold(probs_val, y_val)
    assert 0.30 <= opt_res.best_threshold <= 0.85
    assert opt_res.best_specificity >= 0.0


def test_single_pass_holdout_v2_evaluation(sample_v3_corpus) -> None:
    records = sample_v3_corpus["records"]
    split_res = EntityAwareSplitterV2.split_dataset(records, seed=42)

    model_v11 = ProductivityModelV11(iterations=50, depth=3)
    X_train, y_train = ProductivityFeatureExtractor.extract_matrix(split_res.train_records)
    X_holdout, y_holdout = ProductivityFeatureExtractor.extract_matrix(split_res.holdout_records)

    model_v11.train(X_train, y_train)
    probs_holdout = model_v11.predict_proba(X_holdout)

    holdout_res = ProductivityV11HoldoutEvaluator.evaluate_holdout(
        probs_holdout, y_holdout, threshold=0.50
    )
    assert holdout_res.holdout_sample_size == len(y_holdout)
    assert 0.0 <= holdout_res.precision <= 1.0
    assert 0.0 <= holdout_res.specificity <= 1.0


def test_service_mismatch_error_taxonomy_comparison(sample_v3_corpus) -> None:
    records = sample_v3_corpus["records"]
    split_res = EntityAwareSplitterV2.split_dataset(records, seed=42)

    model_v11 = ProductivityModelV11(iterations=50, depth=3)
    X_train, y_train = ProductivityFeatureExtractor.extract_matrix(split_res.train_records)
    X_holdout, y_holdout = ProductivityFeatureExtractor.extract_matrix(split_res.holdout_records)
    model_v11.train(X_train, y_train)

    probs_holdout = model_v11.predict_proba(X_holdout)
    err_res = ProductivityV11ErrorTaxonomyClassifier.audit_and_compare_errors(
        split_res.holdout_records,
        probs_holdout,
        threshold_v11=0.50,
        previous_service_mismatch_count=150,
    )
    assert "service_mismatch_rejection_rate" in err_res


def test_governance_challenger_v11_registration() -> None:
    gov = ProductionGovernanceManager()
    gov.register_challenger("productivity_model_v1_1")

    assert "productivity_model_v1_1" in gov.state.challenger_models_registered
    assert gov.state.champion_model_version == "real_model_v2_1"

    with pytest.raises(GovernanceApprovalError):
        gov.promote_challenger_to_champion("productivity_model_v1_1", human_approved=False)
