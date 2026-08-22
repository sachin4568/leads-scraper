from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from backend.app.services.formatter import LeadDataFormatter
from backend.app.services.service_engine import ServiceOpportunityEngine

logger = logging.getLogger(__name__)


class DataLossViolationError(Exception):
    """Raised when lead count changes during service classification segregation."""

    pass


@dataclass
class ClassificationSummaryResult:
    total_master_leads: int
    website_development_count: int
    website_seo_count: int
    social_media_management_count: int
    social_media_marketing_count: int
    multi_label_coverage_pct: float
    data_loss_audit_passed: bool


class MultiLabelClassificationAgent:
    """Executes multi-label 4-service classification across Master Raw Leads without mutating master dataset."""

    @staticmethod
    def classify_lead(lead_payload: dict[str, Any]) -> dict[str, Any]:
        formatted = LeadDataFormatter.format_master_lead_payload(lead_payload)
        eval_scores = ServiceOpportunityEngine.evaluate_all_services(lead_payload)

        classifications = {}
        for stype, sres in eval_scores.items():
            classifications[stype.lower()] = {
                "eligible": sres.eligible,
                "score": sres.score,
                "confidence": sres.confidence,
                "reasons": sres.reasons,
                "facebook_ads_detected": sres.facebook_ads_detected,
                "ssl_valid": sres.ssl_valid,
            }

        formatted["service_classifications"] = classifications
        formatted["service_classification_status"] = "CLASSIFIED"
        formatted["website_development_score"] = eval_scores["WEBSITE_DEVELOPMENT"].score
        formatted["website_seo_score"] = eval_scores["WEBSITE_SEO"].score
        formatted["social_media_management_score"] = eval_scores["SOCIAL_MEDIA_MANAGEMENT"].score
        formatted["social_media_marketing_score"] = eval_scores["SOCIAL_MEDIA_MARKETING"].score

        # Overall Lead Priority Score: Max opportunity score weighted by genuineness
        max_opp = max(
            eval_scores["WEBSITE_DEVELOPMENT"].score,
            eval_scores["WEBSITE_SEO"].score,
            eval_scores["SOCIAL_MEDIA_MANAGEMENT"].score,
            eval_scores["SOCIAL_MEDIA_MARKETING"].score,
        )
        gen_prob = formatted.get("genuineness_probability", 0.85)
        formatted["overall_lead_priority_score"] = round(max_opp * gen_prob, 1)

        return formatted

    @classmethod
    def process_master_batch(
        cls, master_leads: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], ClassificationSummaryResult]:
        raw_count_before = len(master_leads)
        classified_leads = []

        dev_c = 0
        seo_c = 0
        smm_c = 0
        ads_c = 0
        multi_c = 0

        for r in master_leads:
            res = cls.classify_lead(r)
            classified_leads.append(res)

            c_map = res["service_classifications"]
            active_services = sum(1 for v in c_map.values() if v["eligible"])

            if c_map["website_development"]["eligible"]:
                dev_c += 1
            if c_map["website_seo"]["eligible"]:
                seo_c += 1
            if c_map["social_media_management"]["eligible"]:
                smm_c += 1
            if c_map["social_media_marketing"]["eligible"]:
                ads_c += 1

            if active_services >= 2:
                multi_c += 1

        raw_count_after = len(classified_leads)
        if raw_count_before != raw_count_after:
            raise DataLossViolationError(
                f"Data Loss Invariant Violated! Raw count before ({raw_count_before}) != Raw count after ({raw_count_after})"
            )

        cov_pct = round((multi_c / raw_count_before * 100.0), 2) if raw_count_before > 0 else 0.0

        summary = ClassificationSummaryResult(
            total_master_leads=raw_count_after,
            website_development_count=dev_c,
            website_seo_count=seo_c,
            social_media_management_count=smm_c,
            social_media_marketing_count=ads_c,
            multi_label_coverage_pct=cov_pct,
            data_loss_audit_passed=True,
        )

        logger.info(
            f"[MultiLabelClassificationAgent] Batch complete: Total={raw_count_after}, Dev={dev_c}, SEO={seo_c}, SMM={smm_c}, Ads={ads_c}"
        )
        return classified_leads, summary
