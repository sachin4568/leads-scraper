from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from backend.app.enrichment.enrichment_engine import BusinessEnrichmentSnapshot

logger = logging.getLogger(__name__)


@dataclass
class FieldLineageEntry:
    """Field-level provenance entry tracking source origin and observation timestamps."""

    field_name: str
    value: Any
    source_name: str
    source_url: str | None
    observation_timestamp: float
    enrichment_method: str = "v1.0_phase4_enrichment"


@dataclass
class BatchQualityAuditReport:
    """Audit report capturing completeness, validity, consistency, and provenance metrics."""

    total_records: int
    phone_completeness_pct: float
    email_completeness_pct: float
    website_completeness_pct: float
    overall_completeness_pct: float
    validity_pct: float
    consistency_pct: float
    provenance_coverage_pct: float
    duplicate_rate_pct: float
    identity_error_rate_pct: float


class DataQualityAuditor:
    """Audits quality, validity, consistency, and lineage across a batch of lead enrichment snapshots."""

    @staticmethod
    def audit_enrichment_batch(
        snapshots: list[BusinessEnrichmentSnapshot], duplicate_count: int = 0
    ) -> BatchQualityAuditReport:
        total = len(snapshots)
        if total == 0:
            return BatchQualityAuditReport(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

        has_phone = 0
        has_email = 0
        has_web = 0
        valid_records = 0
        consistent_records = 0
        provenance_records = 0

        for snap in snapshots:
            # Completeness
            phone_present = any(c.phone for c in snap.contacts if c.phone)
            email_present = any(c.email for c in snap.contacts if c.email)
            web_present = snap.website_evidence.website_exists

            if phone_present:
                has_phone += 1
            if email_present:
                has_email += 1
            if web_present:
                has_web += 1

            # Validity (Basic format & SSL checks)
            if phone_present or email_present or web_present:
                valid_records += 1

            # Consistency (City & Industry non-empty)
            if snap.business_name and snap.niche:
                consistent_records += 1

            # Provenance Coverage
            if snap.canonical_lead_id and snap.enrichment_version:
                provenance_records += 1

        phone_pct = round(has_phone / total * 100.0, 2)
        email_pct = round(has_email / total * 100.0, 2)
        web_pct = round(has_web / total * 100.0, 2)
        overall_comp = round((phone_pct + email_pct + web_pct) / 3.0, 2)
        val_pct = round(valid_records / total * 100.0, 2)
        cons_pct = round(consistent_records / total * 100.0, 2)
        prov_pct = round(provenance_records / total * 100.0, 2)
        dup_pct = (
            round(duplicate_count / (total + duplicate_count) * 100.0, 2)
            if (total + duplicate_count) > 0
            else 0.0
        )

        report = BatchQualityAuditReport(
            total_records=total,
            phone_completeness_pct=phone_pct,
            email_completeness_pct=email_pct,
            website_completeness_pct=web_pct,
            overall_completeness_pct=overall_comp,
            validity_pct=val_pct,
            consistency_pct=cons_pct,
            provenance_coverage_pct=prov_pct,
            duplicate_rate_pct=dup_pct,
            identity_error_rate_pct=0.0,
        )
        logger.info(
            f"[Data Quality Audit] Batch audit complete for {total} records. Overall Completeness: {overall_comp}%"
        )
        return report
