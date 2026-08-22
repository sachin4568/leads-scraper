from __future__ import annotations

import pytest

from backend.app.ml.deduplication import generate_canonical_entity_id
from backend.app.ml.feature_pipeline import FeaturePipeline
from backend.app.ml.leakage_guard import LeakageError, LeakageGuard
from backend.app.ml.model_registry import Phase1ModelRecord, Phase1ModelRegistry
from backend.app.ml.schemas import HumanOutcome, HumanOutcomeEvent
from backend.app.ml.train_pipeline import execute_phase1_pipeline


def test_leakage_guard_raises_on_forbidden_column() -> None:
    forbidden = ["Lead Score", "Industry", "Location"]
    with pytest.raises(LeakageError) as exc_info:
        LeakageGuard.check_for_leakage(forbidden)
    assert "Target leakage detected" in str(exc_info.value)


def test_leakage_guard_allows_valid_features() -> None:
    valid = ["Industry", "Location", "Has Website", "SSL Valid"]
    allowed = LeakageGuard.check_for_leakage(valid)
    assert len(allowed) == 4


def test_canonical_entity_id_generation() -> None:
    id1 = generate_canonical_entity_id(
        "Apex Dental", "+12125551234", "info@apexdental.com", "apexdental.com", "Dehradun"
    )
    id2 = generate_canonical_entity_id(
        "Apex Dental", "+12125551234", "info@apexdental.com", "apexdental.com", "Dehradun"
    )
    id3 = generate_canonical_entity_id("Different Clinic", "+19999999999")

    assert id1 == id2
    assert id1 != id3


def test_feature_pipeline_extracts_target_and_uncertain_separately() -> None:
    raw_sample = [
        {"Industry": "Dental", "Ground Truth Genuine": "GENUINE", "Has Website": "TRUE"},
        {"Industry": "Plumbing", "Ground Truth Genuine": "NOT_GENUINE", "Has Website": "FALSE"},
        {"Industry": "HVAC", "Ground Truth Genuine": "UNCERTAIN", "Has Website": "TRUE"},
    ]
    pipeline = FeaturePipeline()
    feats, targets, uncertain = pipeline.process_records(raw_sample)

    assert len(feats) == 2
    assert targets == [1, 0]
    assert len(uncertain) == 1
    assert uncertain[0]["Industry"] == "HVAC"


def test_human_outcome_event_schema() -> None:
    event = HumanOutcomeEvent(
        lead_id="LD-00100",
        original_prediction="GENUINE",
        original_model_version="v1.0_phase1_baseline",
        original_probability=0.92,
        human_outcome=HumanOutcome.GENUINE_PRODUCTIVE,
        reason="Owner booked meeting",
        timestamp=1700000000.0,
    )
    assert event.human_outcome == "GENUINE_PRODUCTIVE"
    assert event.original_probability == 0.92


def test_model_registry_saves_experimental_status() -> None:
    registry = Phase1ModelRegistry()
    record = Phase1ModelRecord(
        model_name="CatBoost_Phase1",
        model_version="v1.0_exp_test",
        status="EXPERIMENTAL",
        dataset_version="v1.0",
        feature_version="v1.0",
        training_timestamp="2026-08-12 16:50:00",
        random_seed=42,
        training_sample_count=1000,
        positive_count=800,
        negative_count=200,
        validation_metrics={"f1": 0.88},
        test_metrics={"f1": 0.87},
        selected_threshold=0.50,
        artifact_path="/tmp/v1.0_exp_test.json",
    )
    saved = registry.register_experimental_model(record)
    assert saved.status == "EXPERIMENTAL"


def test_execute_phase1_pipeline_full_run() -> None:
    import os
    from pathlib import Path
    training_data_path = os.environ.get("LEAD_ML_TRAINING_DATA_PATH", "/Users/sachinchaubey/Desktop/Leads/training_data/Lead_ML_Training_Data_10000.xlsx")
    if not Path(training_data_path).exists():
        pytest.skip(f"Requires the external training data artifact at {training_data_path} which is not present in the current workspace.")

    report = execute_phase1_pipeline(file_path=training_data_path)
    assert report["dataset_row_count"] == 10000
    assert report["split_counts"]["complete_dataset"]["genuine"] == 7959
    assert report["split_counts"]["complete_dataset"]["not_genuine"] == 646
    assert report["split_counts"]["complete_dataset"]["uncertain"] == 1395
    assert report["evaluation_label"] == "PHASE 1.1 BASELINE — STRATIFIED SYNTHETIC/OFFLINE DATA"
    assert (
        report["production_gate_status"] == "NO — NOT YET (EXPERIMENTAL STRATIFIED BASELINE ONLY)"
    )
