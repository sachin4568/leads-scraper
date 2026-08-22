from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

EXPORTS_DIR = Path("/Users/sachinchaubey/Desktop/Leads/training_data/corpus_exports")
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


class FalsePositiveErrorReason(str, Enum):
    STALE_LISTING = "STALE_LISTING"
    FAKE_BUSINESS = "FAKE_BUSINESS"
    INVALID_CONTACT = "INVALID_CONTACT"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    PERMANENTLY_CLOSED = "PERMANENTLY_CLOSED"
    DUPLICATE = "DUPLICATE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    OTHER_VALIDATED_REASON = "OTHER_VALIDATED_REASON"


class FalseNegativeErrorReason(str, Enum):
    SPARSE_PRESENCE = "SPARSE_PRESENCE"
    PHONE_ONLY_GENUINE = "PHONE_ONLY_GENUINE"
    EMAIL_ONLY_GENUINE = "EMAIL_ONLY_GENUINE"
    WEAK_PUBLIC_DATA = "WEAK_PUBLIC_DATA"
    FRANCHISE_STRUCTURE = "FRANCHISE_STRUCTURE"
    ENTERPRISE_STRUCTURE = "ENTERPRISE_STRUCTURE"
    MISSING_SOCIAL_SIGNAL = "MISSING_SOCIAL_SIGNAL"
    OTHER_VALIDATED_REASON = "OTHER_VALIDATED_REASON"


@dataclass
class ErrorAnalysisRecord:
    canonical_lead_id: str
    sampling_source: str
    feature_snapshot_version: str
    model_version: str
    probability: float
    model_decision: str
    human_genuineness: str
    disagreement_type: str  # FALSE_POSITIVE or FALSE_NEGATIVE
    validated_error_reason: str
    evidence_reference: str
    reviewer: str
    timestamp: str


class ErrorTaxonomyClassifier:
    """Classifies model disagreements into validated error taxonomy reasons and exports real_model_error_analysis_v1 dataset."""

    @staticmethod
    def classify_disagreement(
        model_decision: str,
        human_genuineness: str,
        feature_signals: dict[str, Any],
    ) -> tuple[str, str]:
        """Returns (disagreement_type, validated_error_reason)."""
        if model_decision == "GENUINE" and human_genuineness == "NOT_GENUINE":
            disagreement_type = "FALSE_POSITIVE"
            if not feature_signals.get("website_exists", False):
                reason = FalsePositiveErrorReason.STALE_LISTING.value
            elif not feature_signals.get("has_phone", False):
                reason = FalsePositiveErrorReason.INVALID_CONTACT.value
            else:
                reason = FalsePositiveErrorReason.FAKE_BUSINESS.value
            return disagreement_type, reason

        elif model_decision == "REJECTED" and human_genuineness == "GENUINE":
            disagreement_type = "FALSE_NEGATIVE"
            if not feature_signals.get("website_exists", False):
                reason = FalseNegativeErrorReason.PHONE_ONLY_GENUINE.value
            elif feature_signals.get("is_sparse", True):
                reason = FalseNegativeErrorReason.SPARSE_PRESENCE.value
            else:
                reason = FalseNegativeErrorReason.WEAK_PUBLIC_DATA.value
            return disagreement_type, reason

        return "NO_DISAGREEMENT", "MATCH"

    @classmethod
    def export_error_analysis_dataset(
        cls, records: list[ErrorAnalysisRecord], dataset_version: str = "v1"
    ) -> dict[str, Any]:
        artifact_path = EXPORTS_DIR / f"real_model_error_analysis_{dataset_version}.json"
        rows = [r.__dict__ for r in records]

        fp_count = sum(1 for r in records if r.disagreement_type == "FALSE_POSITIVE")
        fn_count = sum(1 for r in records if r.disagreement_type == "FALSE_NEGATIVE")

        payload = {
            "dataset_name": f"real_model_error_analysis_{dataset_version}",
            "total_records": len(rows),
            "false_positives_count": fp_count,
            "false_negatives_count": fn_count,
            "records": rows,
        }

        with open(artifact_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        logger.info(
            f"[Error Taxonomy Exporter] Exported {len(rows)} error records to {artifact_path}"
        )
        return payload
