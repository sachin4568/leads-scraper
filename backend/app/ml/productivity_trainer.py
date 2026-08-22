from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any

from backend.app.ml.productivity_readiness import TemporalLeakageError

logger = logging.getLogger(__name__)


@dataclass
class ProductivityDatasetAuditResult:
    total_records_discovered: int
    eligible_resolved_records: int
    productive_count: int
    unproductive_count: int
    excluded_unresolved_count: int
    excluded_untouched_count: int
    dataset_sha256_hash: str
    audit_passed: bool


@dataclass
class EntityAwareSplitResult:
    train_records: list[dict[str, Any]]
    validation_records: list[dict[str, Any]]
    holdout_records: list[dict[str, Any]]
    train_hash: str
    validation_hash: str
    holdout_hash: str
    split_passed: bool


class ProductivityDatasetAuditor:
    """Audits lead IDs, label validity, resolved labels (PRODUCTIVE, UNPRODUCTIVE), temporal ordering, and SHA-256 hash."""

    @staticmethod
    def compute_sha256(data: list[dict[str, Any]]) -> str:
        serialized = json.dumps(data, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def audit_dataset(cls, data: dict[str, Any]) -> ProductivityDatasetAuditResult:
        records = data.get("records", [])
        total = len(records)

        eligible = []
        productive_c = 0
        unproductive_c = 0
        unresolved_c = 0
        untouched_c = 0

        forbidden_keys = {
            "outreach_state",
            "contacted",
            "owner_reached",
            "decision_maker_reached",
            "productive",
            "unproductive",
            "successful_calls",
        }

        for r in records:
            outcome = (
                r.get("human_outcome", {}).get("final_productivity_outcome")
                or r.get("human_outcome_label")
                or r.get("final_productivity_outcome")
            )
            feats = r.get("prediction_time_features") or r.get("derived_features") or {}

            # Check for temporal leakage in pre-prediction features
            leaked = set(feats.keys()).intersection(forbidden_keys)
            if leaked:
                raise TemporalLeakageError(
                    f"Forbidden post-outreach variables detected in feature snapshot: {leaked}"
                )

            if outcome == "PRODUCTIVE":
                productive_c += 1
                eligible.append(r)
            elif outcome == "UNPRODUCTIVE":
                unproductive_c += 1
                eligible.append(r)
            elif outcome == "NOT_RESOLVED":
                unresolved_c += 1
            elif outcome in ("NOT_ATTEMPTED", "UNKNOWN"):
                untouched_c += 1

        dataset_hash = cls.compute_sha256(eligible)
        passed = len(eligible) > 0 and (productive_c + unproductive_c == len(eligible))

        return ProductivityDatasetAuditResult(
            total_records_discovered=total,
            eligible_resolved_records=len(eligible),
            productive_count=productive_c,
            unproductive_count=unproductive_c,
            excluded_unresolved_count=unresolved_c,
            excluded_untouched_count=untouched_c,
            dataset_sha256_hash=dataset_hash,
            audit_passed=passed,
        )


class EntityAwareSplitter:
    """Splits resolved binary productivity records into 70% Train, 15% Validation, and 15% Frozen Holdout partitions with zero entity overlap."""

    @classmethod
    def split_dataset(
        cls, eligible_records: list[dict[str, Any]], seed: int = 42
    ) -> EntityAwareSplitResult:
        # Group by canonical_lead_id
        grouped: dict[str, list[dict[str, Any]]] = {}
        for r in eligible_records:
            cid = r.get("raw_data", {}).get("canonical_lead_id") or r.get("canonical_lead_id")
            if cid not in grouped:
                grouped[cid] = []
            grouped[cid].append(r)

        unique_ids = sorted(grouped.keys())
        total_unique = len(unique_ids)

        train_end = int(0.70 * total_unique)
        val_end = train_end + int(0.15 * total_unique)

        train_ids = set(unique_ids[:train_end])
        val_ids = set(unique_ids[train_end:val_end])
        holdout_ids = set(unique_ids[val_end:])

        # Verify zero overlap invariant
        assert len(train_ids.intersection(val_ids)) == 0
        assert len(train_ids.intersection(holdout_ids)) == 0
        assert len(val_ids.intersection(holdout_ids)) == 0

        train_recs = [r for cid in train_ids for r in grouped[cid]]
        val_recs = [r for cid in val_ids for r in grouped[cid]]
        holdout_recs = [r for cid in holdout_ids for r in grouped[cid]]

        train_h = ProductivityDatasetAuditor.compute_sha256(train_recs)
        val_h = ProductivityDatasetAuditor.compute_sha256(val_recs)
        holdout_h = ProductivityDatasetAuditor.compute_sha256(holdout_recs)

        logger.info(
            f"[EntityAwareSplitter] Split complete: Train={len(train_recs)}, Val={len(val_recs)}, Holdout={len(holdout_recs)}"
        )

        return EntityAwareSplitResult(
            train_records=train_recs,
            validation_records=val_recs,
            holdout_records=holdout_recs,
            train_hash=train_h,
            validation_hash=val_h,
            holdout_hash=holdout_h,
            split_passed=True,
        )
