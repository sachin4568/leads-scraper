from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from backend.app.enrichment.enrichment_engine import BusinessEnrichmentSnapshot

logger = logging.getLogger(__name__)


@dataclass
class ShadowEvaluationMetrics:
    """Empirical evaluation metrics calculated strictly on shadow predictions overlapping with validated human ground truth."""

    prediction_coverage_count: int  # All real leads receiving predictions (e.g. 5,000)
    ground_truth_overlap_count: int  # Predicted leads with validated human labels (e.g. 500)
    predictions_without_ground_truth_count: int  # Predicted leads without ground truth (e.g. 4,500)
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0
    precision: float | None = None
    recall: float | None = None
    f1_score: float | None = None
    false_positive_rate: float | None = None
    false_negative_rate: float | None = None


@dataclass
class SingleFeatureDriftResult:
    """Detailed empirical drift result for a single feature."""

    feature_name: str
    synthetic_value: float | str
    real_value: float | str
    statistic_name: str
    drift_statistic: float
    magnitude: str
    direction: str | None
    interpretation: str  # NO_MEANINGFUL_DRIFT, LOW_DRIFT, MODERATE_DRIFT, HIGH_DRIFT


@dataclass
class ComprehensiveDriftReport:
    """Statistical drift comparison report between synthetic 10k baseline and real 5k corpus."""

    synthetic_dataset_version: str = "dataset_v1.0_10k_offline"
    real_dataset_version: str = "real_leads_v3.0_5000"
    feature_drifts: list[SingleFeatureDriftResult] = None

    def __post_init__(self):
        if self.feature_drifts is None:
            self.feature_drifts = []


class ShadowEvaluator:
    """Evaluates read-only shadow predictions against validated human ground truth on overlapping canonical lead IDs."""

    @staticmethod
    def evaluate_shadow_predictions(
        predictions: list[dict[str, Any]], ground_truth: list[dict[str, Any]] | None = None
    ) -> ShadowEvaluationMetrics:
        pred_coverage = len(predictions)
        if not ground_truth:
            return ShadowEvaluationMetrics(
                prediction_coverage_count=pred_coverage,
                ground_truth_overlap_count=0,
                predictions_without_ground_truth_count=pred_coverage,
            )

        gt_map = {
            g["canonical_lead_id"]: g.get("genuineness_outcome")
            for g in ground_truth
            if g.get("genuineness_outcome") in ("GENUINE", "NOT_GENUINE")
        }
        overlapping_leads = [p for p in predictions if p["canonical_lead_id"] in gt_map]
        overlap_count = len(overlapping_leads)
        without_gt_count = pred_coverage - overlap_count

        tp, fp, tn, fn = 0, 0, 0, 0
        for p in overlapping_leads:
            lead_id = p["canonical_lead_id"]
            actual_gen = gt_map[lead_id] == "GENUINE"
            pred_gen = p.get("predicted_decision") == "GENUINE"

            if pred_gen and actual_gen:
                tp += 1
            elif pred_gen and not actual_gen:
                fp += 1
            elif not pred_gen and not actual_gen:
                tn += 1
            elif not pred_gen and actual_gen:
                fn += 1

        prec = round(tp / (tp + fp), 4) if (tp + fp) > 0 else None
        rec = round(tp / (tp + fn), 4) if (tp + fn) > 0 else None
        f1 = (
            round(2 * prec * rec / (prec + rec), 4) if (prec and rec and (prec + rec) > 0) else None
        )
        fpr = round(fp / (fp + tn), 4) if (fp + tn) > 0 else None
        fnr = round(fn / (fn + tp), 4) if (fn + tp) > 0 else None

        return ShadowEvaluationMetrics(
            prediction_coverage_count=pred_coverage,
            ground_truth_overlap_count=overlap_count,
            predictions_without_ground_truth_count=without_gt_count,
            tp=tp,
            fp=fp,
            fn=fn,
            tn=tn,
            precision=prec,
            recall=rec,
            f1_score=f1,
            false_positive_rate=fpr,
            false_negative_rate=fnr,
        )


class FeatureDriftAnalyzer:
    """Computes distribution statistics and feature drift between synthetic 10k baseline and real 5k corpus."""

    @staticmethod
    def compare_synthetic_vs_real(
        synthetic_stats: dict[str, Any], real_snapshots: list[BusinessEnrichmentSnapshot]
    ) -> ComprehensiveDriftReport:
        total_real = len(real_snapshots)
        results: list[SingleFeatureDriftResult] = []

        if total_real == 0:
            return ComprehensiveDriftReport(feature_drifts=results)

        # 1. Binary Feature: Has Website
        real_has_web_pct = round(
            sum(1 for s in real_snapshots if s.website_evidence.website_exists)
            / total_real
            * 100.0,
            2,
        )
        synth_has_web_pct = float(synthetic_stats.get("website_completeness_pct", 66.67))
        diff_web = round(real_has_web_pct - synth_has_web_pct, 2)
        interp_web = (
            "NO_MEANINGFUL_DRIFT"
            if abs(diff_web) < 1.0
            else ("LOW_DRIFT" if abs(diff_web) < 10.0 else "MODERATE_DRIFT")
        )

        results.append(
            SingleFeatureDriftResult(
                feature_name="has_website",
                synthetic_value=synth_has_web_pct,
                real_value=real_has_web_pct,
                statistic_name="percentage_difference",
                drift_statistic=diff_web,
                magnitude=f"{abs(diff_web)}%",
                direction="higher" if diff_web > 0 else "lower",
                interpretation=interp_web,
            )
        )

        # 2. Binary Feature: Has Phone
        real_has_phone_pct = round(
            sum(1 for s in real_snapshots if any(c.phone for c in s.contacts if c.phone))
            / total_real
            * 100.0,
            2,
        )
        synth_has_phone_pct = float(synthetic_stats.get("phone_completeness_pct", 80.0))
        diff_phone = round(real_has_phone_pct - synth_has_phone_pct, 2)
        interp_phone = "NO_MEANINGFUL_DRIFT" if abs(diff_phone) < 1.0 else "LOW_DRIFT"

        results.append(
            SingleFeatureDriftResult(
                feature_name="has_phone",
                synthetic_value=synth_has_phone_pct,
                real_value=real_has_phone_pct,
                statistic_name="percentage_difference",
                drift_statistic=diff_phone,
                magnitude=f"{abs(diff_phone)}%",
                direction="higher" if diff_phone > 0 else "lower",
                interpretation=interp_phone,
            )
        )

        # 3. Binary Feature: Has Email
        real_has_email_pct = round(
            sum(1 for s in real_snapshots if any(c.email for c in s.contacts if c.email))
            / total_real
            * 100.0,
            2,
        )
        synth_has_email_pct = float(synthetic_stats.get("email_completeness_pct", 50.0))
        diff_email = round(real_has_email_pct - synth_has_email_pct, 2)
        interp_email = "NO_MEANINGFUL_DRIFT" if abs(diff_email) < 1.0 else "LOW_DRIFT"

        results.append(
            SingleFeatureDriftResult(
                feature_name="has_email",
                synthetic_value=synth_has_email_pct,
                real_value=real_has_email_pct,
                statistic_name="percentage_difference",
                drift_statistic=diff_email,
                magnitude=f"{abs(diff_email)}%",
                direction="higher" if diff_email > 0 else "lower",
                interpretation=interp_email,
            )
        )

        # 4. Numerical Feature: Response Time (ms)
        real_resp_times = [
            s.website_evidence.response_time_ms
            for s in real_snapshots
            if s.website_evidence.response_time_ms is not None
        ]
        mean_real_resp = (
            round(sum(real_resp_times) / len(real_resp_times), 2) if real_resp_times else 0.0
        )
        mean_synth_resp = float(synthetic_stats.get("mean_response_time_ms", 450.0))
        diff_resp = round(mean_real_resp - mean_synth_resp, 2)

        results.append(
            SingleFeatureDriftResult(
                feature_name="mean_response_time_ms",
                synthetic_value=mean_synth_resp,
                real_value=mean_real_resp,
                statistic_name="mean_difference",
                drift_statistic=diff_resp,
                magnitude=f"{abs(diff_resp)}ms",
                direction="higher" if diff_resp > 0 else "lower",
                interpretation="NO_MEANINGFUL_DRIFT" if abs(diff_resp) < 5.0 else "LOW_DRIFT",
            )
        )

        return ComprehensiveDriftReport(feature_drifts=results)
