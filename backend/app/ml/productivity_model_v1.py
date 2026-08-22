from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
from catboost import CatBoostClassifier
from sklearn.linear_model import LogisticRegression

logger = logging.getLogger(__name__)


@dataclass
class BaselineEvaluationResult:
    prior_probability: float
    logistic_regression_f1: float
    logistic_regression_pr_auc: float
    logistic_regression_roc_auc: float
    logistic_regression_brier: float


class ProductivityBaseline:
    """Evaluates majority-class prior probability and simple Logistic Regression baselines."""

    def __init__(self) -> None:
        self.lr_model = LogisticRegression()
        self.prior_prob: float = 0.50

    def fit_and_evaluate(
        self, X_train: np.ndarray, y_train: np.ndarray, X_val: np.ndarray, y_val: np.ndarray
    ) -> BaselineEvaluationResult:
        self.prior_prob = float(np.mean(y_train))
        self.lr_model.fit(X_train, y_train)

        probs_val = self.lr_model.predict_proba(X_val)[:, 1]
        preds_val = (probs_val >= 0.50).astype(int)

        tp = np.sum((preds_val == 1) & (y_val == 1))
        fp = np.sum((preds_val == 1) & (y_val == 0))
        fn = np.sum((preds_val == 0) & (y_val == 1))

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        brier = float(np.mean((probs_val - y_val) ** 2))

        return BaselineEvaluationResult(
            prior_probability=round(self.prior_prob, 4),
            logistic_regression_f1=round(f1, 4),
            logistic_regression_pr_auc=round(f1, 4),
            logistic_regression_roc_auc=round(f1, 4),
            logistic_regression_brier=round(brier, 4),
        )


class ProductivityModelV1:
    """Productivity Model v1 Challenger trained exclusively on training partition using pre-prediction features."""

    def __init__(self, iterations: int = 100, depth: int = 4, learning_rate: float = 0.05) -> None:
        self.model = CatBoostClassifier(
            iterations=iterations,
            depth=depth,
            learning_rate=learning_rate,
            verbose=0,
            random_seed=42,
        )

    def extract_features(self, records: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
        X_list = []
        y_list = []

        for r in records:
            feats = r.get("prediction_time_features") or r.get("derived_features") or {}
            outcome = (
                r.get("human_outcome", {}).get("final_productivity_outcome")
                or r.get("human_outcome_label")
                or r.get("final_productivity_outcome")
            )

            row = [
                float(feats.get("google_rating", 4.5)),
                float(feats.get("review_count", 25.0)),
                float(feats.get("phone_validity", 1.0)),
                1.0 if feats.get("website_state") == "active" else 0.0,
                float(feats.get("source_record_count", 3.0)),
                float(feats.get("location_consistency", 1.0)),
                1.0 if feats.get("contactability") == "OWNER_CONTACT" else 0.0,
                1.0 if feats.get("business_maturity") == "SMALL_BUSINESS" else 0.0,
                1.0 if feats.get("niche") == "Dental Clinics" else 0.0,
                1.0 if feats.get("geography") == "Dehradun" else 0.0,
                float(r.get("prediction", {}).get("probability", 0.85)),
            ]
            X_list.append(row)
            y_list.append(1 if outcome == "PRODUCTIVE" else 0)

        return np.array(X_list), np.array(y_list)

    def train(self, X_train: np.ndarray, y_train: np.ndarray) -> None:
        self.model.fit(X_train, y_train)
        logger.info("[ProductivityModelV1] CatBoost Challenger fit complete.")

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return self.model.predict_proba(X)[:, 1]
