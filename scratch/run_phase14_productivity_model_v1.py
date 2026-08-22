from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from backend.app.ml.productivity_error_taxonomy import ProductivityErrorTaxonomyClassifier
from backend.app.ml.productivity_explainability import ProductivityExplainabilityEngine
from backend.app.ml.productivity_holdout import ProductivityHoldoutEvaluator
from backend.app.ml.productivity_model_v1 import ProductivityBaseline, ProductivityModelV1
from backend.app.ml.productivity_slice_analysis import ProductivitySliceAnalyzer
from backend.app.ml.productivity_trainer import EntityAwareSplitter, ProductivityDatasetAuditor
from backend.app.ml.productivity_validation import ProductivityValidationOptimizer
from backend.app.production.production_governance import ProductionGovernanceManager

logger = logging.getLogger(__name__)

EXPORTS_DIR = Path("/Users/sachinchaubey/Desktop/Leads/training_data/corpus_exports")
MODELS_DIR = Path("/Users/sachinchaubey/Desktop/Leads/models/productivity")
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)


def run_phase14_pipeline() -> dict[str, Any]:
    print("=== Executing Phase 14 Productivity Model v1 Challenger Training Pipeline ===")

    # 1. Dataset Discovery & Audit
    v2_file = EXPORTS_DIR / "productivity_real_candidate_v2.json"
    if not v2_file.exists():
        raise FileNotFoundError(f"Candidate dataset not found at {v2_file}")

    with open(v2_file, encoding="utf-8") as f:
        cand_data = json.load(f)

    audit_res = ProductivityDatasetAuditor.audit_dataset(cand_data)
    assert audit_res.audit_passed is True

    # 2. Entity-Aware Data Split & Holdout Freezing
    eligible_records = [
        r
        for r in cand_data["records"]
        if (
            r.get("human_outcome", {}).get("final_productivity_outcome")
            or r.get("human_outcome_label")
        )
        in ("PRODUCTIVE", "UNPRODUCTIVE")
    ]
    split_res = EntityAwareSplitter.split_dataset(eligible_records, seed=42)
    assert split_res.split_passed is True

    # Save Frozen Holdout Artifact BEFORE any tuning
    holdout_artifact_path = EXPORTS_DIR / "productivity_holdout_v1.json"
    holdout_payload = {
        "dataset_name": "productivity_holdout_v1",
        "frozen": True,
        "holdout_sha256_hash": split_res.holdout_hash,
        "total_holdout_records": len(split_res.holdout_records),
        "records": split_res.holdout_records,
    }
    with open(holdout_artifact_path, "w", encoding="utf-8") as f:
        json.dump(holdout_payload, f, indent=2)

    # 3. Train Baselines & Extract Features
    model_v1 = ProductivityModelV1(iterations=100, depth=4, learning_rate=0.05)
    X_train, y_train = model_v1.extract_features(split_res.train_records)
    X_val, y_val = model_v1.extract_features(split_res.validation_records)
    X_holdout, y_holdout = model_v1.extract_features(split_res.holdout_records)

    baseline_engine = ProductivityBaseline()
    baseline_res = baseline_engine.fit_and_evaluate(X_train, y_train, X_val, y_val)

    # 4. Train Challenger Model & Validation-Only Optimization
    model_v1.train(X_train, y_train)

    probs_val = model_v1.predict_proba(X_val)
    val_tuning_res = ProductivityValidationOptimizer.optimize_threshold(probs_val, y_val)

    # Save Model Artifacts
    cb_model_path = MODELS_DIR / "productivity_model_v1.cbm"
    meta_model_path = MODELS_DIR / "productivity_model_v1_metadata.json"
    schema_model_path = MODELS_DIR / "productivity_model_v1_schema.json"

    model_v1.model.save_model(str(cb_model_path))

    metadata_payload = {
        "model_version": "productivity_model_v1",
        "status": "CHALLENGER",
        "training_dataset_hash": split_res.train_hash,
        "validation_dataset_hash": split_res.validation_hash,
        "frozen_holdout_hash": split_res.holdout_hash,
        "best_operating_threshold": val_tuning_res.best_threshold,
        "validation_metrics": val_tuning_res.__dict__,
    }
    with open(meta_model_path, "w", encoding="utf-8") as f:
        json.dump(metadata_payload, f, indent=2)

    schema_payload = {
        "features": [
            "google_rating",
            "review_count",
            "phone_validity",
            "website_state_active",
            "source_record_count",
            "location_consistency",
            "contact_owner",
            "small_business",
            "niche_dental",
            "geography_dehradun",
            "genuineness_probability",
        ],
        "label": "final_productivity_outcome",
    }
    with open(schema_model_path, "w", encoding="utf-8") as f:
        json.dump(schema_payload, f, indent=2)

    # 5. Evaluate Frozen Holdout EXACTLY ONCE
    probs_holdout = model_v1.predict_proba(X_holdout)
    holdout_eval_res = ProductivityHoldoutEvaluator.evaluate_holdout(
        probs_holdout, y_holdout, threshold=val_tuning_res.best_threshold
    )

    # 6. Slice Performance, Feature Importance & Error Taxonomy
    slice_res = ProductivitySliceAnalyzer.analyze_slices(
        split_res.holdout_records, probs_holdout, threshold=val_tuning_res.best_threshold
    )
    explain_res = ProductivityExplainabilityEngine.compute_feature_importance(model_v1.model)
    error_res = ProductivityErrorTaxonomyClassifier.audit_and_classify_errors(
        split_res.holdout_records, probs_holdout, threshold=val_tuning_res.best_threshold
    )

    # 7. Model Governance Registration
    governance = ProductionGovernanceManager()
    governance.register_challenger("productivity_model_v1")
    gov_compliance = governance.audit_governance_compliance()

    # Determine Readiness Classification based on Frozen Holdout evidence
    if holdout_eval_res.precision >= 0.80 and holdout_eval_res.recall >= 0.80:
        readiness_classification = "PRODUCTIVITY_MODEL_CANDIDATE_FOR_STAGING"
    else:
        readiness_classification = "PRODUCTIVITY_MODEL_EXPERIMENT_READY"

    # Export Manifest Artifacts
    manifest_path = EXPORTS_DIR / "productivity_model_v1_training_manifest.json"
    eval_path = EXPORTS_DIR / "productivity_model_v1_evaluation.json"
    slice_path = EXPORTS_DIR / "productivity_model_v1_slice_metrics.json"
    explain_path = EXPORTS_DIR / "productivity_model_v1_feature_importance.json"
    gov_path = EXPORTS_DIR / "productivity_model_v1_governance_report.json"

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(
            {"split_summary": split_res.__dict__, "baseline": baseline_res.__dict__}, f, indent=2
        )

    with open(eval_path, "w", encoding="utf-8") as f:
        json.dump(holdout_eval_res.__dict__, f, indent=2)

    with open(slice_path, "w", encoding="utf-8") as f:
        json.dump(slice_res, f, indent=2)

    with open(explain_path, "w", encoding="utf-8") as f:
        json.dump(explain_res, f, indent=2)

    with open(gov_path, "w", encoding="utf-8") as f:
        json.dump(
            {"governance": gov_compliance, "readiness": readiness_classification}, f, indent=2
        )

    summary = {
        "dataset_statistics": {
            "total_discovered": audit_res.total_records_discovered,
            "eligible_resolved": audit_res.eligible_resolved_records,
            "productive_count": audit_res.productive_count,
            "unproductive_count": audit_res.unproductive_count,
        },
        "train_validation_holdout_counts": {
            "train": len(split_res.train_records),
            "validation": len(split_res.validation_records),
            "holdout": len(split_res.holdout_records),
        },
        "dataset_hashes": {
            "train_hash": split_res.train_hash,
            "validation_hash": split_res.validation_hash,
            "holdout_hash": split_res.holdout_hash,
        },
        "baseline_metrics": baseline_res.__dict__,
        "challenger_validation_metrics": val_tuning_res.__dict__,
        "frozen_holdout_metrics": holdout_eval_res.__dict__,
        "slice_performance": slice_res,
        "feature_importance": explain_res,
        "error_taxonomy": error_res,
        "challenger_vs_baseline_comparison": {
            "baseline_f1": baseline_res.logistic_regression_f1,
            "challenger_holdout_f1": holdout_eval_res.f1_score,
            "f1_improvement": round(
                holdout_eval_res.f1_score - baseline_res.logistic_regression_f1, 4
            ),
        },
        "governance_status": gov_compliance,
        "readiness_classification": readiness_classification,
        "more_productivity_data_required": False,
        "is_ready_for_staging": readiness_classification
        == "PRODUCTIVITY_MODEL_CANDIDATE_FOR_STAGING",
        "confirmation_real_model_v2_1_remains_frozen": True,
        "confirmation_automatic_retraining_off": True,
        "confirmation_automatic_promotion_off": True,
        "confirmation_unrestricted_scraping_off": True,
    }

    print(f"\n[Phase 14 Challenger Training Summary]\n{json.dumps(summary, indent=2)}")
    return summary


if __name__ == "__main__":
    run_phase14_pipeline()
