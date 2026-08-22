from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.app.ingestion.ingestion import RawLead
from backend.app.ingestion.lifecycle import LifecycleResolver, LifecycleState
from backend.app.models_phase2 import CanonicalLead, LeadObservation

logger = logging.getLogger(__name__)


@dataclass
class ProductionBatchRecord:
    batch_id: str
    source_name: str
    target_quota: int
    received_count: int = 0
    new_count: int = 0
    existing_count: int = 0
    updated_count: int = 0
    duplicate_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.datetime.now(datetime.UTC).isoformat())


class BatchQuotaExceededError(Exception):
    """Raised when an ingestion batch exceeds its allocated quota."""

    pass


class BatchQuotaController:
    """Enforces strict batch volume limits during controlled production rollout."""

    def __init__(self, default_max_quota: int = 500) -> None:
        self.default_max_quota = default_max_quota

    def validate_quota(self, requested_size: int, quota_limit: int | None = None) -> bool:
        limit = quota_limit if quota_limit is not None else self.default_max_quota
        if requested_size > limit:
            raise BatchQuotaExceededError(
                f"Batch size {requested_size} exceeds maximum quota limit of {limit}."
            )
        return True


class SourceBatchManager:
    """Tracks active production source batches and their ingestion statistics."""

    def __init__(self) -> None:
        self.active_batches: dict[str, ProductionBatchRecord] = {}

    def create_batch(self, batch_id: str, source_name: str, quota: int) -> ProductionBatchRecord:
        rec = ProductionBatchRecord(batch_id=batch_id, source_name=source_name, target_quota=quota)
        self.active_batches[batch_id] = rec
        logger.info(
            f"[SourceBatchManager] Created batch {batch_id} for source '{source_name}' with quota {quota}"
        )
        return rec

    def get_batch(self, batch_id: str) -> ProductionBatchRecord | None:
        return self.active_batches.get(batch_id)


class ProductionCohortTracker:
    """Tracks unique canonical businesses ingested per production cohort."""

    def __init__(self) -> None:
        self.cohort_leads: dict[str, list[str]] = {}

    def record_lead_ingestion(self, cohort_id: str, canonical_lead_id: str) -> None:
        if cohort_id not in self.cohort_leads:
            self.cohort_leads[cohort_id] = []
        if canonical_lead_id not in self.cohort_leads[cohort_id]:
            self.cohort_leads[cohort_id].append(canonical_lead_id)


class ControlledProductionIngestion:
    """Production ingestion workflow integrating lifecycle resolution, batch quotas, and change tracking."""

    def __init__(self, default_quota: int = 500) -> None:
        self.resolver = LifecycleResolver()
        self.quota_controller = BatchQuotaController(default_max_quota=default_quota)
        self.batch_manager = SourceBatchManager()
        self.cohort_tracker = ProductionCohortTracker()

    def process_production_batch(
        self,
        db: Session,
        batch_id: str,
        source_name: str,
        raw_leads: list[RawLead],
        quota_limit: int | None = None,
    ) -> tuple[ProductionBatchRecord, list[tuple[CanonicalLead, LeadObservation, LifecycleState]]]:
        self.quota_controller.validate_quota(len(raw_leads), quota_limit=quota_limit)
        batch = self.batch_manager.create_batch(batch_id, source_name, len(raw_leads))

        results = []
        for raw in raw_leads:
            canonical, obs, state = self.resolver.process_observation(db, raw)
            batch.received_count += 1

            if state == LifecycleState.NEW:
                batch.new_count += 1
            elif state == LifecycleState.EXISTING:
                batch.existing_count += 1
            elif state == LifecycleState.UPDATED:
                batch.updated_count += 1
            elif state == LifecycleState.DUPLICATE:
                batch.duplicate_count += 1

            self.cohort_tracker.record_lead_ingestion(batch_id, canonical.id)
            results.append((canonical, obs, state))

        logger.info(
            f"[ControlledProductionIngestion] Batch {batch_id} complete: {batch.new_count} NEW, "
            f"{batch.existing_count} EXISTING, {batch.updated_count} UPDATED, {batch.duplicate_count} DUPLICATE."
        )
        return batch, results
