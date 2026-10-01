from __future__ import annotations

import csv
import io
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Lead, ScrapeJob

logger = logging.getLogger(__name__)


@dataclass
class HumanAuditRow:
    lead_id: str
    business_name: str
    source: str
    website: str
    phone: str
    email: str
    address: str
    system_verification_status: str
    system_trust_score: float
    system_opportunity_score: int
    human_business_real: str = "UNKNOWN"       # YES, NO, UNKNOWN
    human_website_correct: str = "UNKNOWN"     # YES, NO, UNKNOWN
    human_phone_correct: str = "UNKNOWN"       # YES, NO, UNKNOWN
    human_email_correct: str = "UNKNOWN"       # YES, NO, UNKNOWN
    human_address_correct: str = "UNKNOWN"     # YES, NO, UNKNOWN
    human_contactable: str = "UNKNOWN"         # YES, NO, UNKNOWN
    human_opportunity_relevant: str = "UNKNOWN"# YES, NO, UNKNOWN
    human_notes: str = ""


@dataclass
class GroundTruthFieldMetrics:
    field_name: str
    true_positives: int = 0
    true_negatives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    precision: float = 0.0
    recall: float = 0.0
    accuracy: float = 0.0
    f1_score: float = 0.0
    false_positive_rate: float = 0.0  # FP / (TP + FP)
    false_negative_rate: float = 0.0  # FN / (TP + FN)


@dataclass
class GroundTruthAuditEvaluation:
    job_id: str
    total_audited: int = 0
    fields: dict[str, GroundTruthFieldMetrics] = field(default_factory=dict)
    overall_verification: GroundTruthFieldMetrics = field(default_factory=lambda: GroundTruthFieldMetrics("overall_verification"))
    trust_calibration_curve: dict[str, dict[str, Any]] = field(default_factory=dict)
    key_failure_patterns: list[str] = field(default_factory=list)


class HumanAuditExporter:
    """Selects a balanced, stratified representative sample for manual ground-truth auditing."""

    @classmethod
    def create_stratified_sample(
        cls, db: Session, job_id: str, sample_size: int = 20
    ) -> list[Lead]:
        leads = db.scalars(select(Lead).where(Lead.job_id == job_id)).all()
        if not leads:
            return []

        if len(leads) <= sample_size:
            return leads

        # Stratified sampling: high trust, medium trust, low trust, unverified
        high_trust = [l for l in leads if (l.genuineness_score or 0) >= 0.75]
        med_trust = [l for l in leads if 0.50 <= (l.genuineness_score or 0) < 0.75]
        low_trust = [l for l in leads if (l.genuineness_score or 0) < 0.50]
        unverified = [l for l in leads if l.verification_status != "VERIFIED"]

        selected: list[Lead] = []
        target_per_bin = max(1, sample_size // 4)

        selected.extend(high_trust[:target_per_bin])
        selected.extend(med_trust[:target_per_bin])
        selected.extend(low_trust[:target_per_bin])
        selected.extend([u for u in unverified if u not in selected][:target_per_bin])

        # Fill remaining slots with untouched leads
        for l in leads:
            if len(selected) >= sample_size:
                break
            if l not in selected:
                selected.append(l)

        return selected

    @classmethod
    def export_csv(cls, db: Session, job_id: str, sample_size: int = 20) -> str:
        sample_leads = cls.create_stratified_sample(db, job_id, sample_size)
        output = io.StringIO()
        writer = csv.writer(output)

        headers = [
            "lead_id",
            "business_name",
            "source",
            "website",
            "phone",
            "email",
            "address",
            "system_verification_status",
            "system_trust_score",
            "system_opportunity_score",
            "human_business_real",
            "human_website_correct",
            "human_phone_correct",
            "human_email_correct",
            "human_address_correct",
            "human_contactable",
            "human_opportunity_relevant",
            "human_notes",
        ]
        writer.writerow(headers)

        for l in sample_leads:
            writer.writerow([
                str(l.id),
                l.business_name,
                "discovery",
                l.website or "",
                l.phone or "",
                l.email or "",
                l.notes or "",
                l.verification_status,
                l.genuineness_score or 0.0,
                0,
                "",  # human_business_real (YES/NO/UNKNOWN)
                "",  # human_website_correct
                "",  # human_phone_correct
                "",  # human_email_correct
                "",  # human_address_correct
                "",  # human_contactable
                "",  # human_opportunity_relevant
                "",  # human_notes
            ])

        return output.getvalue()


class GroundTruthEvaluator:
    """Evaluates human-reviewed ground truth CSV vs system predictions to measure precision/recall/FPR."""

    @classmethod
    def _compute_binary_metrics(cls, tp: int, tn: int, fp: int, fn: int, field_name: str) -> GroundTruthFieldMetrics:
        total = tp + tn + fp + fn
        precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 1.0
        recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 1.0
        accuracy = round((tp + tn) / total, 4) if total > 0 else 1.0
        f1 = round(2 * (precision * recall) / (precision + recall), 4) if (precision + recall) > 0 else 0.0
        fpr = round(fp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
        fnr = round(fn / (tp + fn), 4) if (tp + fn) > 0 else 0.0

        return GroundTruthFieldMetrics(
            field_name=field_name,
            true_positives=tp,
            true_negatives=tn,
            false_positives=fp,
            false_negatives=fn,
            precision=precision,
            recall=recall,
            accuracy=accuracy,
            f1_score=f1,
            false_positive_rate=fpr,
            false_negative_rate=fnr,
        )

    @classmethod
    def evaluate_audit_csv(cls, csv_text: str, job_id: str) -> GroundTruthAuditEvaluation:
        reader = csv.DictReader(io.StringIO(csv_text))
        rows = list(reader)

        field_counts = {
            "business_name": {"tp": 0, "tn": 0, "fp": 0, "fn": 0},
            "website": {"tp": 0, "tn": 0, "fp": 0, "fn": 0},
            "phone": {"tp": 0, "tn": 0, "fp": 0, "fn": 0},
            "email": {"tp": 0, "tn": 0, "fp": 0, "fn": 0},
            "overall_verification": {"tp": 0, "tn": 0, "fp": 0, "fn": 0},
        }

        trust_bins: dict[str, dict[str, int]] = {
            "0.0-0.49": {"total": 0, "correct": 0},
            "0.50-0.69": {"total": 0, "correct": 0},
            "0.70-0.89": {"total": 0, "correct": 0},
            "0.90-1.00": {"total": 0, "correct": 0},
        }
        failure_patterns: list[str] = []

        for r in rows:
            sys_verif = str(r.get("system_verification_status", "")).upper() == "VERIFIED"
            sys_trust = float(r.get("system_trust_score") or 0.0)
            sys_web = bool(r.get("website") and not str(r.get("website")).lower().startswith("none"))
            sys_phone = bool(r.get("phone") and not str(r.get("phone")).lower().startswith("none"))
            sys_email = bool(r.get("email") and not str(r.get("email")).lower().startswith("none"))

            hum_biz = str(r.get("human_business_real", "")).strip().upper()
            hum_web = str(r.get("human_website_correct", "")).strip().upper()
            hum_phone = str(r.get("human_phone_correct", "")).strip().upper()
            hum_email = str(r.get("human_email_correct", "")).strip().upper()

            # Business entity evaluation
            if hum_biz in ("YES", "NO"):
                actual_biz = hum_biz == "YES"
                if sys_verif and actual_biz:
                    field_counts["business_name"]["tp"] += 1
                elif sys_verif and not actual_biz:
                    field_counts["business_name"]["fp"] += 1
                    failure_patterns.append(f"Fake/defunct business marked verified: '{r.get('business_name')}'")
                elif not sys_verif and actual_biz:
                    field_counts["business_name"]["fn"] += 1
                else:
                    field_counts["business_name"]["tn"] += 1

            # Website evaluation
            if hum_web in ("YES", "NO") and sys_web:
                actual_web = hum_web == "YES"
                if actual_web:
                    field_counts["website"]["tp"] += 1
                else:
                    field_counts["website"]["fp"] += 1
                    failure_patterns.append(f"Third-party/incorrect website marked verified: '{r.get('website')}' for '{r.get('business_name')}'")

            # Phone evaluation
            if hum_phone in ("YES", "NO") and sys_phone:
                actual_p = hum_phone == "YES"
                if actual_p:
                    field_counts["phone"]["tp"] += 1
                else:
                    field_counts["phone"]["fp"] += 1
                    failure_patterns.append(f"Mismatched phone marked verified: '{r.get('phone')}' for '{r.get('business_name')}'")

            # Email evaluation
            if hum_email in ("YES", "NO") and sys_email:
                actual_em = hum_email == "YES"
                if actual_em:
                    field_counts["email"]["tp"] += 1
                else:
                    field_counts["email"]["fp"] += 1
                    failure_patterns.append(f"Unrelated email marked verified: '{r.get('email')}' for '{r.get('business_name')}'")

            # Overall Verification evaluation
            if hum_biz in ("YES", "NO"):
                actual_genuine = hum_biz == "YES" and (hum_phone == "YES" or hum_web == "YES" or hum_email == "YES")
                if sys_verif and actual_genuine:
                    field_counts["overall_verification"]["tp"] += 1
                elif sys_verif and not actual_genuine:
                    field_counts["overall_verification"]["fp"] += 1
                elif not sys_verif and actual_genuine:
                    field_counts["overall_verification"]["fn"] += 1
                else:
                    field_counts["overall_verification"]["tn"] += 1

                # Trust Calibration Binning
                t_bin = (
                    "0.90-1.00" if sys_trust >= 0.90
                    else "0.70-0.89" if sys_trust >= 0.70
                    else "0.50-0.69" if sys_trust >= 0.50
                    else "0.0-0.49"
                )
                trust_bins[t_bin]["total"] += 1
                if actual_genuine:
                    trust_bins[t_bin]["correct"] += 1

        eval_fields: dict[str, GroundTruthFieldMetrics] = {}
        for fn, c in field_counts.items():
            if fn != "overall_verification":
                eval_fields[fn] = cls._compute_binary_metrics(c["tp"], c["tn"], c["fp"], c["fn"], fn)

        ov_c = field_counts["overall_verification"]
        overall_m = cls._compute_binary_metrics(ov_c["tp"], ov_c["tn"], ov_c["fp"], ov_c["fn"], "overall_verification")

        calibration_curve: dict[str, dict[str, Any]] = {}
        for b_name, b_data in trust_bins.items():
            tot = b_data["total"]
            corr = b_data["correct"]
            empirical_acc = round((corr / tot) * 100, 2) if tot > 0 else 0.0
            calibration_curve[b_name] = {
                "total_samples": tot,
                "correct_samples": corr,
                "empirical_accuracy": empirical_acc,
            }

        return GroundTruthAuditEvaluation(
            job_id=job_id,
            total_audited=len(rows),
            fields=eval_fields,
            overall_verification=overall_m,
            trust_calibration_curve=calibration_curve,
            key_failure_patterns=failure_patterns[:10],
        )
