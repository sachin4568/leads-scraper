from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from catboost import CatBoostClassifier

try:
    from lightgbm import LGBMClassifier
except (ImportError, Exception):
    from sklearn.ensemble import HistGradientBoostingClassifier as LGBMClassifier

logger = logging.getLogger(__name__)

MODELS_DIR = Path("/Users/sachinchaubey/Desktop/Leads/models/genuineness")
MODELS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class DatasetPartitionV21:
    X_train: np.ndarray
    y_train: np.ndarray
    X_val: np.ndarray
    y_val: np.ndarray
    X_holdout_v2: np.ndarray
    y_holdout_v2: np.ndarray
    X_sparse_holdout: np.ndarray
    y_sparse_holdout: np.ndarray
    X_hardcase_v2: np.ndarray
    y_hardcase_v2: np.ndarray


@dataclass
class ValidationTuningResultsV21:
    best_alpha: float
    best_threshold: float
    val_precision: float
    val_recall: float
    val_f1: float
    val_specificity: float


class ModelV21Trainer:
    """Trainer for Real Model v2.1 Challenger with non-web feature expansion, sparse-business holdout isolation, and validation-only tuning."""

    def __init__(self, random_seed: int = 42) -> None:
        self.random_seed = random_seed
        self.catboost_model: CatBoostClassifier | None = None
        self.lgb_model: Any = None
        self.best_alpha: float = 0.30
        self.best_threshold: float = 0.50

    def generate_candidate_v3_dataset(
        self, num_records: int = 2150
    ) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
        np.random.seed(self.random_seed)
        X_list = []
        y_list = []
        metadata = []

        # Generate candidate leads (75% Genuine, 25% Not Genuine)
        num_genuine = int(num_records * 0.75)
        for i in range(num_records):
            is_genuine = i < num_genuine
            is_phone_only = is_genuine and (i % 4 == 0)
            has_web = is_genuine and not is_phone_only

            has_phone = 1.0 if (is_genuine or i % 3 == 0) else 0.0
            ssl_v = 1.0 if has_web else 0.0
            num_c = float(np.random.randint(1, 4)) if is_genuine else 0.0
            is_saas = 1.0 if i % 5 == 0 else 0.0

            # Non-Web Signals (Phase 9)
            place_id = 1.0 if is_genuine else (1.0 if i % 2 == 0 else 0.0)
            rating = (
                float(np.random.uniform(4.0, 5.0))
                if is_genuine
                else float(np.random.uniform(1.0, 3.5))
            )
            review_count = (
                float(np.random.randint(10, 200)) if is_genuine else float(np.random.randint(0, 15))
            )
            phone_valid = 1.0 if (is_genuine and has_phone) else 0.0
            loc_consistent = 1.0 if is_genuine else 0.0
            source_count = float(np.random.randint(2, 5)) if is_genuine else 1.0

            vec = [
                1.0 if has_web else 0.0,
                has_phone,
                ssl_v,
                num_c,
                is_saas,
                place_id,
                rating,
                review_count,
                phone_valid,
                loc_consistent,
                source_count,
            ]
            X_list.append(vec)
            y_list.append(1 if is_genuine else 0)

            prov = (
                "PHONE_ONLY"
                if is_phone_only
                else ("HARD_POSITIVE" if is_genuine else "HARD_NEGATIVE")
            )
            metadata.append(
                {
                    "canonical_lead_id": f"lead_cand3_{i:05d}",
                    "provenance": prov,
                    "is_genuine": is_genuine,
                    "is_phone_only": is_phone_only,
                }
            )

        X_arr = np.array(X_list)
        y_arr = np.array(y_list)

        # Stratified Shuffle
        shuffle_idx = np.random.permutation(num_records)
        X_shuffled = X_arr[shuffle_idx]
        y_shuffled = y_arr[shuffle_idx]
        meta_shuffled = [metadata[i] for i in shuffle_idx]

        return X_shuffled, y_shuffled, meta_shuffled

    def train_challenger_v2_1(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        output_dir: Path | None = None,
    ) -> tuple[CatBoostClassifier, Any]:
        target_dir = output_dir or MODELS_DIR
        target_dir.mkdir(parents=True, exist_ok=True)

        # Model A: CatBoost v2.1
        self.catboost_model = CatBoostClassifier(
            iterations=180,
            learning_rate=0.07,
            depth=5,
            random_seed=self.random_seed,
            verbose=0,
        )
        if len(np.unique(y_val)) > 1:
            self.catboost_model.fit(
                X_train, y_train, eval_set=(X_val, y_val), early_stopping_rounds=25
            )
        else:
            self.catboost_model.fit(X_train, y_train)

        # Model B: LightGBM / HistGB v2.1
        if "LGBMClassifier" in str(LGBMClassifier):
            self.lgb_model = LGBMClassifier(
                n_estimators=180,
                learning_rate=0.07,
                max_depth=5,
                random_state=self.random_seed,
                verbose=-1,
            )
        else:
            self.lgb_model = LGBMClassifier(
                max_iter=180,
                learning_rate=0.07,
                max_depth=5,
                random_state=self.random_seed,
            )
        self.lgb_model.fit(X_train, y_train)

        # Save Artifacts
        cb_path = target_dir / "v2_1_real_catboost.cbm"
        lgb_path = target_dir / "v2_1_real_lightgbm.joblib"
        self.catboost_model.save_model(str(cb_path))
        joblib.dump(self.lgb_model, str(lgb_path))

        logger.info(
            f"[ModelV21Trainer] Trained and saved v2.1 CatBoost and LightGBM to {target_dir}"
        )
        return self.catboost_model, self.lgb_model

    def optimize_validation_parameters(
        self, X_val: np.ndarray, y_val: np.ndarray
    ) -> ValidationTuningResultsV21:
        if self.catboost_model is None or self.lgb_model is None:
            raise ValueError("Models must be trained before validation parameter optimization.")

        p_cat = self.catboost_model.predict_proba(X_val)[:, 1]
        p_lgb = (
            self.lgb_model.predict_proba(X_val)[:, 1]
            if hasattr(self.lgb_model, "predict_proba")
            else self.lgb_model.predict(X_val)
        )

        best_f1 = -1.0
        best_alpha = 0.30
        best_threshold = 0.50
        best_prec = 0.0
        best_rec = 0.0
        best_spec = 0.0

        for alpha in [0.10, 0.20, 0.30, 0.40, 0.50]:
            p_ens = alpha * p_cat + (1.0 - alpha) * p_lgb
            for th in [0.40, 0.45, 0.50, 0.55]:
                preds = (p_ens >= th).astype(int)
                tp = int(np.sum((preds == 1) & (y_val == 1)))
                fp = int(np.sum((preds == 1) & (y_val == 0)))
                fn = int(np.sum((preds == 0) & (y_val == 1)))
                tn = int(np.sum((preds == 0) & (y_val == 0)))

                prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
                rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
                spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0
                f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0

                if prec >= 0.95 and f1 > best_f1:
                    best_f1 = f1
                    best_alpha = alpha
                    best_threshold = th
                    best_prec = prec
                    best_rec = rec
                    best_spec = spec

        self.best_alpha = best_alpha
        self.best_threshold = best_threshold

        return ValidationTuningResultsV21(
            best_alpha=best_alpha,
            best_threshold=best_threshold,
            val_precision=round(best_prec, 4),
            val_recall=round(best_rec, 4),
            val_f1=round(best_f1, 4),
            val_specificity=round(best_spec, 4),
        )
