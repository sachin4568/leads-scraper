from __future__ import annotations

import numpy as np

from backend.app.ml.holdout_evaluator import HoldoutEvaluator
from backend.app.ml.real_trainer import RealModelTrainer


def test_entity_isolated_split_integrity() -> None:
    trainer = RealModelTrainer(random_seed=42)

    canonical_leads = [{"canonical_lead_id": f"lead_{i}"} for i in range(1, 201)]
    ground_truth = [
        {
            "canonical_lead_id": f"lead_{i}",
            "genuineness_outcome": "GENUINE",
            "sampling_source": "RANDOM",
        }
        for i in range(1, 101)
    ] + [
        {
            "canonical_lead_id": f"lead_{i}",
            "genuineness_outcome": "NOT_GENUINE",
            "sampling_source": "HARD_NEGATIVE",
        }
        for i in range(101, 201)
    ]

    split = trainer.create_entity_isolated_split(canonical_leads, ground_truth)

    train_set = set(split.train_ids)
    val_set = set(split.val_ids)
    nat_set = set(split.natural_holdout_ids)
    hard_set = set(split.hardcase_holdout_ids)

    # Zero overlap check
    assert len(train_set.intersection(val_set)) == 0
    assert len(train_set.intersection(nat_set)) == 0
    assert len(train_set.intersection(hard_set)) == 0
    assert len(val_set.intersection(nat_set)) == 0
    assert len(val_set.intersection(hard_set)) == 0
    assert len(nat_set.intersection(hard_set)) == 0


def test_real_model_training_and_validation_tuning(tmp_path) -> None:
    X_tr = np.array([[1.0, 1.0], [1.0, 0.0], [0.0, 0.0], [0.0, 1.0]] * 10)
    y_tr = np.array([1, 1, 0, 0] * 10)

    X_val = np.array([[1.0, 1.0], [0.0, 0.0]] * 5)
    y_val = np.array([1, 0] * 5)

    trainer = RealModelTrainer(random_seed=42)
    cat, lgb = trainer.train_challenger_models(X_tr, y_tr, X_val, y_val, output_dir=tmp_path)

    assert cat is not None
    assert lgb is not None

    val_res = trainer.optimize_ensemble_and_threshold_on_val(X_val, y_val)
    assert 0.0 <= val_res.best_alpha <= 1.0
    assert 0.0 <= val_res.best_threshold <= 1.0
    assert val_res.val_f1 >= 0.0


def test_holdout_evaluator_and_champion_comparison() -> None:
    y_true = np.array([1, 1, 1, 1, 0, 0, 0, 0])
    y_probs = np.array([0.95, 0.90, 0.88, 0.40, 0.10, 0.15, 0.20, 0.85])

    metrics = HoldoutEvaluator.evaluate_holdout("test_holdout", y_probs, y_true, threshold=0.50)

    assert metrics.tp == 3
    assert metrics.fp == 1
    assert metrics.fn == 1
    assert metrics.tn == 3
    assert metrics.precision == 0.75
    assert metrics.recall == 0.75
    assert metrics.specificity == 0.75

    comp = HoldoutEvaluator.compare_champion_vs_challenger(metrics)
    assert comp.champion_precision == 0.90
    assert comp.challenger_precision == 0.75
