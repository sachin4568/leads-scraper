from __future__ import annotations

import json
from typing import Any
from backend.app.benchmark.metrics import BenchmarkReportPayload
from backend.app.benchmark.audit import GroundTruthAuditEvaluation


class BenchmarkReportGenerator:
    """Produces comprehensive human-readable and machine-readable calibration reports."""

    @classmethod
    def generate_markdown(
        cls, report: BenchmarkReportPayload, audit_eval: GroundTruthAuditEvaluation | None = None
    ) -> str:
        lines: list[str] = []
        lines.append(f"# Production Lead Quality Benchmark & Calibration Report")
        lines.append(f"**Job ID:** `{report.job_id}` | **Niche:** `{report.niche}` | **Location:** `{report.location}`")
        lines.append(f"**Status:** `{report.status}` | **Completion Reason:** `{report.completion_reason}`\n")

        lines.append(f"## 1. Executive Summary & Quality Funnel")
        lines.append(f"```text")
        lines.append(f"RAW DISCOVERED      : {report.quality_funnel.raw_discovered}")
        lines.append(f"      ↓")
        lines.append(f"UNIQUE CANDIDATES   : {report.quality_funnel.unique}")
        lines.append(f"      ↓")
        lines.append(f"VERIFIED ENTITIES   : {report.quality_funnel.verified} ({round((report.quality_funnel.verified/max(1,report.quality_funnel.unique))*100,1)}%)")
        lines.append(f"      ↓")
        lines.append(f"CONTACTABLE LEADS   : {report.quality_funnel.contactable} ({round((report.quality_funnel.contactable/max(1,report.quality_funnel.unique))*100,1)}%)")
        lines.append(f"      ↓")
        lines.append(f"OPPORTUNITY MATCH   : {report.quality_funnel.opportunity_match} ({round((report.quality_funnel.opportunity_match/max(1,report.quality_funnel.unique))*100,1)}%)")
        lines.append(f"      ↓")
        lines.append(f"FINAL QUALIFIED     : {report.quality_funnel.qualified} ({round((report.quality_funnel.qualified/max(1,report.quality_funnel.unique))*100,1)}%)")
        lines.append(f"```\n")

        lines.append(f"## 2. Raw Discovery Performance")
        lines.append(f"- **Target Lead Count:** {report.discovery.requested_target}")
        lines.append(f"- **Total Fetched Records:** {report.discovery.fetched_count}")
        lines.append(f"- **Unique Discovered:** {report.discovery.unique_count}")
        lines.append(f"- **Saved Raw Leads:** {report.discovery.saved_raw_count}")
        lines.append(f"- **Duplicates Filtered:** {report.discovery.duplicate_count} ({report.discovery.duplicate_rate}%)")
        lines.append(f"- **Target Completion Rate:** {report.discovery.target_completion_rate}%\n")

        lines.append(f"## 3. Source-Level Yield & Verification Leaderboard")
        lines.append(f"| Provider | Fetched | Unique Contribution | Duplicates | Verified | Contactable | Unique Yield | Verify Rate |")
        lines.append(f"|---|---|---|---|---|---|---|---|")
        for s in report.sources:
            lines.append(
                f"| `{s.source_name}` | {s.fetched} | {s.unique_contribution} | {s.duplicates} | {s.verified_count} | {s.contactable_count} | {s.unique_yield_rate}% | {s.verification_rate}% |"
            )
        lines.append("")

        lines.append(f"## 4. Field-Level Verification & Rejection Breakdown")
        lines.append(f"| Field | Verified | Unverified | Rejected | Inconclusive | Missing | Verification Rate | Rejection Rate |")
        lines.append(f"|---|---|---|---|---|---|---|---|")
        for fn, fm in report.field_verifications.items():
            lines.append(
                f"| `{fn}` | {fm.verified_count} | {fm.unverified_count} | {fm.rejected_count} | {fm.inconclusive_count} | {fm.missing_count} | {fm.verification_rate}% | {fm.rejection_rate}% |"
            )
        lines.append("")

        lines.append(f"## 5. Contactability & Channel Distribution")
        lines.append(f"- **Any Verified Contact:** {report.contactability.contactability_rate}%")
        lines.append(f"- **Phone Contactable:** {report.contactability.phone_contactable} ({round((report.contactability.phone_contactable/max(1,report.contactability.total_leads))*100,1)}%)")
        lines.append(f"- **Email Contactable:** {report.contactability.email_contactable} ({round((report.contactability.email_contactable/max(1,report.contactability.total_leads))*100,1)}%)")
        lines.append(f"- **Website Available:** {report.contactability.website_contactable} ({round((report.contactability.website_contactable/max(1,report.contactability.total_leads))*100,1)}%)")
        lines.append(f"- **Multi-Channel Contactable (Phone + Email/Web):** {report.contactability.multi_channel_contactable} ({report.contactability.multi_channel_rate}%)\n")

        lines.append(f"## 6. Trust Score Calibration Bins")
        lines.append(f"| Score Bin | Count | Share |")
        lines.append(f"|---|---|---|")
        tot = max(1, report.quality_funnel.unique)
        lines.append(f"| `0.90 – 1.00` (High Trust) | {report.trust_calibration.bin_90_100_count} | {round((report.trust_calibration.bin_90_100_count/tot)*100,1)}% |")
        lines.append(f"| `0.70 – 0.89` (Medium-High) | {report.trust_calibration.bin_70_89_count} | {round((report.trust_calibration.bin_70_89_count/tot)*100,1)}% |")
        lines.append(f"| `0.50 – 0.69` (Moderate) | {report.trust_calibration.bin_50_69_count} | {round((report.trust_calibration.bin_50_69_count/tot)*100,1)}% |")
        lines.append(f"| `0.00 – 0.49` (Low / Unverified) | {report.trust_calibration.bin_0_49_count} | {round((report.trust_calibration.bin_0_49_count/tot)*100,1)}% |")
        lines.append(f"**Average System Trust Score:** `{report.trust_calibration.average_trust_score}`\n")

        if audit_eval:
            lines.append(f"## 7. Ground-Truth Calibration & Accuracy (Human Reviewed)")
            lines.append(f"**Total Audited Leads:** `{audit_eval.total_audited}`\n")
            lines.append(f"### Field Precision / Recall Matrix")
            lines.append(f"| Field | TP | FP | FN | TN | Precision | Recall | False Positive Rate |")
            lines.append(f"|---|---|---|---|---|---|---|---|")
            for fn, fm in audit_eval.fields.items():
                lines.append(
                    f"| `{fn}` | {fm.true_positives} | {fm.false_positives} | {fm.false_negatives} | {fm.true_negatives} | {round(fm.precision*100,1)}% | {round(fm.recall*100,1)}% | **{round(fm.false_positive_rate*100,1)}%** |"
                )
            ov = audit_eval.overall_verification
            lines.append(
                f"| **OVERALL VERIFICATION** | **{ov.true_positives}** | **{ov.false_positives}** | **{ov.false_negatives}** | **{ov.true_negatives}** | **{round(ov.precision*100,1)}%** | **{round(ov.recall*100,1)}%** | **{round(ov.false_positive_rate*100,1)}%** |"
            )
            lines.append("")

            lines.append(f"### Empirical Trust Calibration Curve")
            lines.append(f"| Score Bin | Samples Audited | Confirmed Genuine | Empirical Accuracy | Calibration Delta |")
            lines.append(f"|---|---|---|---|---|")
            for b_name, b_data in audit_eval.trust_calibration_curve.items():
                expected = 95.0 if b_name == "0.90-1.00" else 80.0 if b_name == "0.70-0.89" else 60.0 if b_name == "0.50-0.69" else 25.0
                actual = b_data["empirical_accuracy"]
                delta = round(actual - expected, 1)
                delta_str = f"+{delta}%" if delta > 0 else f"{delta}%"
                lines.append(f"| `{b_name}` | {b_data['total_samples']} | {b_data['correct_samples']} | **{actual}%** | `{delta_str}` |")
            lines.append("")

            if audit_eval.key_failure_patterns:
                lines.append(f"### Top Identified Data-Quality Failure Patterns")
                for p in audit_eval.key_failure_patterns:
                    lines.append(f"- ⚠️ {p}")
                lines.append("")

        return "\n".join(lines)
