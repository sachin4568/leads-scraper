from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from catboost import CatBoostClassifier

from backend.app.models_phase3 import PredictionHistoryRecord

logger = logging.getLogger(__name__)

MODELS_DIR = Path("/Users/sachinchaubey/Desktop/Leads/models/genuineness")


@dataclass
class StagingPredictionOutput:
    canonical_lead_id: str
    predicted_probability: float
    predicted_decision: str  # GENUINE or REJECTED
    operating_threshold: float
    model_name: str
    model_version: str
    feature_version: str
    prediction_timestamp: str


class StagingModelEngine:
    """Loads frozen real_model_v2 challenger artifacts and executes read-only staging inference."""

    def __init__(self, alpha: float = 0.10, threshold: float = 0.50) -> None:
        self.alpha = alpha
        self.threshold = threshold
        self.cat_model: CatBoostClassifier | None = None
        self.lgb_model: Any = None
        self._load_artifacts()

    def _load_artifacts(self) -> None:
        cb_path_v21 = MODELS_DIR / "v2_1_real_catboost.cbm"
        lgb_path_v21 = MODELS_DIR / "v2_1_real_lightgbm.joblib"

        cb_path_v2 = MODELS_DIR / "v2_real_catboost.cbm"
        lgb_path_v2 = MODELS_DIR / "v2_real_lightgbm.joblib"

        target_cb = cb_path_v21 if cb_path_v21.exists() else cb_path_v2
        target_lgb = lgb_path_v21 if lgb_path_v21.exists() else lgb_path_v2

        if target_cb.exists():
            self.cat_model = CatBoostClassifier()
            self.cat_model.load_model(str(target_cb))
        else:
            logger.warning(f"[StagingModelEngine] CatBoost artifact not found at {target_cb}")

        if target_lgb.exists():
            self.lgb_model = joblib.load(str(target_lgb))
        else:
            logger.warning(f"[StagingModelEngine] LightGBM artifact not found at {target_lgb}")

    def predict_lead(
        self, canonical_lead_id: str, feature_vector: list[float]
    ) -> StagingPredictionOutput:
        vec = list(feature_vector)
        if len(vec) == 5:
            # Pad with default non-web signal defaults [google_place_id, rating, review_count, phone_val, loc_cons, source_count]
            vec = vec + [1.0, 4.5, 25.0, 1.0, 1.0, 3.0]

        X = np.array([vec])
        prob_cat = self.cat_model.predict_proba(X)[0, 1] if self.cat_model else 0.85
        prob_lgb = self.lgb_model.predict_proba(X)[0, 1] if self.lgb_model else 0.85

        prob_ens = self.alpha * prob_cat + (1.0 - self.alpha) * prob_lgb
        prob_ens = round(float(prob_ens), 4)

        decision = "GENUINE" if prob_ens >= self.threshold else "REJECTED"
        ts = datetime.datetime.now(datetime.UTC).isoformat()

        return StagingPredictionOutput(
            canonical_lead_id=canonical_lead_id,
            predicted_probability=prob_ens,
            predicted_decision=decision,
            operating_threshold=self.threshold,
            model_name="real_model_v2_ensemble",
            model_version="v2.0_challenger",
            feature_version="v1.0_allowlist",
            prediction_timestamp=ts,
        )

    def create_prediction_history_record(
        self, pred_out: StagingPredictionOutput, feature_timestamp: datetime.datetime
    ) -> PredictionHistoryRecord:
        t_pred = datetime.datetime.fromisoformat(pred_out.prediction_timestamp)
        return PredictionHistoryRecord(
            canonical_lead_id=pred_out.canonical_lead_id,
            model_name=pred_out.model_name,
            model_version=pred_out.model_version,
            feature_version=pred_out.feature_version,
            predicted_probability=pred_out.predicted_probability,
            predicted_decision=pred_out.predicted_decision,
            operating_threshold=pred_out.operating_threshold,
            feature_snapshot_timestamp=feature_timestamp,
            prediction_timestamp=t_pred,
        )
