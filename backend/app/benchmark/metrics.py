from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import EvidenceRecord, Lead, ScrapeJob, ScrapeJobExecutionLog, SourceRecord


@dataclass
class DiscoveryMetrics:
    requested_target: int = 0
    fetched_count: int = 0
    unique_count: int = 0
    saved_raw_count: int = 0
    duplicate_count: int = 0
    failed_count: int = 0
    target_completion_rate: float = 0.0  # (saved / requested) * 100
    unique_discovery_rate: float = 0.0   # (unique / fetched) * 100
    duplicate_rate: float = 0.0          # (duplicates / fetched) * 100


@dataclass
class SourcePerformance:
    source_name: str
    fetched: int = 0
    unique_contribution: int = 0
    duplicates: int = 0
    verified_count: int = 0
    contactable_count: int = 0
    unique_yield_rate: float = 0.0
    verification_rate: float = 0.0
    contactability_rate: float = 0.0


@dataclass
class QueryPerformance:
    query: str
    source: str
    records_received: int = 0
    records_valid: int = 0
    duplicates: int = 0
    new_count: int = 0


@dataclass
class FieldVerificationMetrics:
    field_name: str
    total_records: int = 0
    verified_count: int = 0
    unverified_count: int = 0
    rejected_count: int = 0
    inconclusive_count: int = 0
    missing_count: int = 0
    verification_rate: float = 0.0
    rejection_rate: float = 0.0


@dataclass
class ContactabilityMetrics:
    total_leads: int = 0
    phone_contactable: int = 0
    email_contactable: int = 0
    website_contactable: int = 0
    social_contactable: int = 0
    multi_channel_contactable: int = 0
    contactability_rate: float = 0.0
    multi_channel_rate: float = 0.0


@dataclass
class TrustCalibrationMetrics:
    bin_0_49_count: int = 0
    bin_50_69_count: int = 0
    bin_70_89_count: int = 0
    bin_90_100_count: int = 0
    average_trust_score: float = 0.0


@dataclass
class QualityFunnel:
    raw_discovered: int = 0
    unique: int = 0
    verified: int = 0
    contactable: int = 0
    complete: int = 0
    opportunity_match: int = 0
    qualified: int = 0


@dataclass
class BenchmarkReportPayload:
    job_id: str
    niche: str
    location: str
    status: str
    completion_reason: str | None
    discovery: DiscoveryMetrics
    sources: list[SourcePerformance] = field(default_factory=list)
    queries: list[QueryPerformance] = field(default_factory=list)
    field_verifications: dict[str, FieldVerificationMetrics] = field(default_factory=dict)
    contactability: ContactabilityMetrics = field(default_factory=ContactabilityMetrics)
    trust_calibration: TrustCalibrationMetrics = field(default_factory=TrustCalibrationMetrics)
    quality_funnel: QualityFunnel = field(default_factory=QualityFunnel)


class BenchmarkMetricsAggregator:
    """Calculates all scientific quality, verification, and discovery metrics from DB state."""

    @classmethod
    def calculate_metrics(cls, db: Session, job: ScrapeJob) -> BenchmarkReportPayload:
        leads = db.scalars(select(Lead).where(Lead.job_id == job.id)).all()
        lead_ids = [l.id for l in leads]
        evidences = db.scalars(select(EvidenceRecord).where(EvidenceRecord.lead_id.in_(lead_ids))).all() if lead_ids else []
        src_records = db.scalars(select(SourceRecord).where(SourceRecord.lead_id.in_(lead_ids))).all() if lead_ids else []
        logs = db.scalars(select(ScrapeJobExecutionLog).where(ScrapeJobExecutionLog.job_id == job.id)).all()

        # 1. Discovery Metrics
        req = job.target_lead_count or 1
        fetched = max(job.discovered_count, len(leads))
        unique = len(leads)
        saved = job.leads_scraped
        dupes = job.duplicate_count
        failed = job.failed_count

        disc_metrics = DiscoveryMetrics(
            requested_target=req,
            fetched_count=fetched,
            unique_count=unique,
            saved_raw_count=saved,
            duplicate_count=dupes,
            failed_count=failed,
            target_completion_rate=round((saved / req) * 100, 2) if req else 0.0,
            unique_discovery_rate=round((unique / fetched) * 100, 2) if fetched else 0.0,
            duplicate_rate=round((dupes / fetched) * 100, 2) if fetched else 0.0,
        )

        # 2. Source-Level Performance
        src_map: dict[str, SourcePerformance] = {}
        for l in logs:
            if l.source not in src_map:
                src_map[l.source] = SourcePerformance(source_name=l.source)
            sp = src_map[l.source]
            sp.fetched += l.records_received
            sp.duplicates += l.duplicate_count
            sp.unique_contribution += l.new_count

        # Map lead verified/contactable back to sources
        lead_by_id = {l.id: l for l in leads}
        for sr in src_records:
            if sr.lead_id in lead_by_id:
                ld = lead_by_id[sr.lead_id]
                sp = src_map.setdefault(sr.source, SourcePerformance(source_name=sr.source))
                if ld.verification_status == "VERIFIED":
                    sp.verified_count += 1
                if ld.phone or ld.email or ld.website:
                    sp.contactable_count += 1

        for sp in src_map.values():
            sp.unique_yield_rate = round((sp.unique_contribution / sp.fetched) * 100, 2) if sp.fetched else 0.0
            sp.verification_rate = round((sp.verified_count / sp.unique_contribution) * 100, 2) if sp.unique_contribution else 0.0
            sp.contactability_rate = round((sp.contactable_count / sp.unique_contribution) * 100, 2) if sp.unique_contribution else 0.0

        # 3. Query Performance
        query_list: list[QueryPerformance] = []
        for l in logs:
            query_list.append(
                QueryPerformance(
                    query=l.query,
                    source=l.source,
                    records_received=l.records_received,
                    records_valid=l.records_valid,
                    duplicates=l.duplicate_count,
                    new_count=l.new_count,
                )
            )

        # 4. Field-Level Verification Metrics
        field_metrics_map: dict[str, FieldVerificationMetrics] = {}
        target_fields = ["business_name", "website", "phone", "email", "location", "social_urls"]
        for fn in target_fields:
            field_metrics_map[fn] = FieldVerificationMetrics(field_name=fn, total_records=len(leads))

        for ev in evidences:
            fn = ev.field_name
            if fn in field_metrics_map:
                fm = field_metrics_map[fn]
                st = ev.status.upper()
                if st == "VERIFIED":
                    fm.verified_count += 1
                elif st == "REJECTED":
                    fm.rejected_count += 1
                elif st == "INCONCLUSIVE":
                    fm.inconclusive_count += 1
                else:
                    fm.unverified_count += 1

        for fn, fm in field_metrics_map.items():
            evaluated = fm.verified_count + fm.rejected_count + fm.inconclusive_count + fm.unverified_count
            fm.missing_count = max(0, len(leads) - evaluated)
            fm.verification_rate = round((fm.verified_count / len(leads)) * 100, 2) if leads else 0.0
            fm.rejection_rate = round((fm.rejected_count / len(leads)) * 100, 2) if leads else 0.0

        # 5. Contactability Metrics
        total_l = len(leads)
        p_cont = sum(1 for l in leads if l.phone and not l.phone.startswith("None"))
        e_cont = sum(1 for l in leads if l.email and not l.email.startswith("None"))
        w_cont = sum(1 for l in leads if l.website and not l.website.startswith("None"))
        multi_cont = sum(1 for l in leads if (l.phone and l.email) or (l.phone and l.website) or (l.email and l.website))
        any_cont = sum(1 for l in leads if l.phone or l.email or l.website)

        contact_metrics = ContactabilityMetrics(
            total_leads=total_l,
            phone_contactable=p_cont,
            email_contactable=e_cont,
            website_contactable=w_cont,
            social_contactable=0,
            multi_channel_contactable=multi_cont,
            contactability_rate=round((any_cont / total_l) * 100, 2) if total_l else 0.0,
            multi_channel_rate=round((multi_cont / total_l) * 100, 2) if total_l else 0.0,
        )

        # 6. Trust Calibration Metrics
        b0 = sum(1 for l in leads if (l.genuineness_score or 0.0) < 0.50)
        b1 = sum(1 for l in leads if 0.50 <= (l.genuineness_score or 0.0) < 0.70)
        b2 = sum(1 for l in leads if 0.70 <= (l.genuineness_score or 0.0) < 0.90)
        b3 = sum(1 for l in leads if (l.genuineness_score or 0.0) >= 0.90)
        avg_t = sum((l.genuineness_score or 0.0) for l in leads) / total_l if total_l else 0.0

        trust_metrics = TrustCalibrationMetrics(
            bin_0_49_count=b0,
            bin_50_69_count=b1,
            bin_70_89_count=b2,
            bin_90_100_count=b3,
            average_trust_score=round(avg_t, 2),
        )

        # 7. Quality Funnel
        verified_count = sum(1 for l in leads if l.verification_status == "VERIFIED")
        complete_count = sum(1 for l in leads if l.business_name and l.notes and (l.phone or l.email or l.website))
        opp_match = sum(1 for l in leads if (l.genuineness_score or 0.0) >= 0.50)
        qualified_count = sum(1 for l in leads if l.verification_status == "VERIFIED" and (l.genuineness_score or 0.0) >= 0.65)

        funnel = QualityFunnel(
            raw_discovered=fetched,
            unique=unique,
            verified=verified_count,
            contactable=any_cont,
            complete=complete_count,
            opportunity_match=opp_match,
            qualified=qualified_count,
        )

        return BenchmarkReportPayload(
            job_id=str(job.id),
            niche=job.niche,
            location=job.state or job.region or "Unknown",
            status=job.status,
            completion_reason=job.completion_reason,
            discovery=disc_metrics,
            sources=list(src_map.values()),
            queries=query_list,
            field_verifications=field_metrics_map,
            contactability=contact_metrics,
            trust_calibration=trust_metrics,
            quality_funnel=funnel,
        )
