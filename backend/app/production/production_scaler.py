from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class BatchHealthGateResult:
    batch_id: str
    batch_size: int
    health_check_passed: bool
    drift_check_passed: bool
    prediction_check_passed: bool
    audit_reconciliation_passed: bool
    can_proceed_to_next_batch: bool


class ProductionScaler:
    """Manages progressive controlled batch scaling (100 -> 250 -> 500) with mandatory gate checks between batches."""

    def __init__(self) -> None:
        self.completed_batches: list[BatchHealthGateResult] = []
        self.allowed_batch_sequence = [100, 250, 500]

    def evaluate_batch_gate(
        self,
        batch_id: str,
        batch_size: int,
        system_health_ok: bool = True,
        drift_status_ok: bool = True,
        prediction_rate_ok: bool = True,
        audit_reconciled: bool = True,
    ) -> BatchHealthGateResult:
        can_proceed = (
            system_health_ok and drift_status_ok and prediction_rate_ok and audit_reconciled
        )
        res = BatchHealthGateResult(
            batch_id=batch_id,
            batch_size=batch_size,
            health_check_passed=system_health_ok,
            drift_check_passed=drift_status_ok,
            prediction_check_passed=prediction_rate_ok,
            audit_reconciliation_passed=audit_reconciled,
            can_proceed_to_next_batch=can_proceed,
        )
        self.completed_batches.append(res)
        logger.info(
            f"[ProductionScaler] Batch '{batch_id}' ({batch_size} leads) gate evaluation: proceed={can_proceed}"
        )
        return res

    def can_trigger_next_batch(self, next_batch_size: int) -> bool:
        if not self.completed_batches:
            return next_batch_size == 100

        last_batch = self.completed_batches[-1]
        if not last_batch.can_proceed_to_next_batch:
            logger.warning(
                f"[ProductionScaler] Cannot trigger next batch {next_batch_size}. Previous batch '{last_batch.batch_id}' failed gate."
            )
            return False

        current_idx = self.allowed_batch_sequence.index(last_batch.batch_size)
        if current_idx + 1 < len(self.allowed_batch_sequence):
            expected_next = self.allowed_batch_sequence[current_idx + 1]
            return next_batch_size == expected_next

        return False
