from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import UniqueConstraint, JSON, DateTime, ForeignKey, Index, String, Text, func, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base


class RawLeadSheet(Base):
    __tablename__ = "raw_lead_sheets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sheet_number: Mapped[int] = mapped_column(nullable=False, default=1, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    niche: Mapped[str] = mapped_column(String(120), nullable=False)
    country: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    service: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_lead_count: Mapped[int] = mapped_column(default=100)
    leads_scraped: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    sources: Mapped[list[str] | None] = mapped_column(JSON(), nullable=True)
    enrichments: Mapped[list[str] | None] = mapped_column(JSON(), nullable=True, default=list)
    discovered_count: Mapped[int] = mapped_column(default=0)
    valid_count: Mapped[int] = mapped_column(default=0)
    new_count: Mapped[int] = mapped_column(default=0)
    updated_count: Mapped[int] = mapped_column(default=0)
    duplicate_count: Mapped[int] = mapped_column(default=0)
    failed_count: Mapped[int] = mapped_column(default=0)
    current_source: Mapped[str | None] = mapped_column(String(64))
    current_query: Mapped[str | None] = mapped_column(String(255))
    progress_percent: Mapped[float] = mapped_column(default=0.0)
    error_message: Mapped[str | None] = mapped_column(Text())
    completion_reason: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    leads = relationship("RawLead", back_populates="sheet", cascade="all, delete-orphan", passive_deletes=True)

    @property
    def formatted_id(self) -> str:
        return f"{self.sheet_number:04d}"


class RawLead(Base):
    __tablename__ = "raw_leads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sheet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("raw_lead_sheets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_number: Mapped[int] = mapped_column(default=1)
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    website: Mapped[str | None] = mapped_column(String(2048))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(50))
    location: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str | None] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text())
    raw_data: Mapped[dict | None] = mapped_column(JSON())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sheet = relationship("RawLeadSheet", back_populates="leads")
    enrichment_state = relationship("EnrichmentState", backref="raw_lead", uselist=False, cascade="all, delete-orphan", passive_deletes=True)

    @property
    def lead_code(self) -> str:
        return f"{self.sheet.sheet_number:04d}-{self.lead_number:02d}" if self.sheet else f"{self.lead_number:02d}"


class SegregatedLeadSheet(Base):
    __tablename__ = "segregated_lead_sheets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    raw_sheet_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("raw_lead_sheets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sheet_number: Mapped[int] = mapped_column(nullable=False, default=1, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    service: Mapped[str] = mapped_column(String(64), nullable=False, default="website_dev")
    niche: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(100))
    sources: Mapped[list[str] | None] = mapped_column(JSON(), nullable=True)
    niches: Mapped[list[str] | None] = mapped_column(JSON(), nullable=True)
    total_leads: Mapped[int] = mapped_column(default=0)
    time_taken_min: Mapped[int] = mapped_column(default=10)
    google_sheets_url: Mapped[str | None] = mapped_column(String(1024))
    caller_name: Mapped[str | None] = mapped_column(String(120))
    caller_email: Mapped[str | None] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    leads = relationship("SegregatedLead", back_populates="sheet", cascade="all, delete-orphan", passive_deletes=True)

    @property
    def formatted_id(self) -> str:
        return f"{self.sheet_number:04d}"


class SegregatedLead(Base):
    __tablename__ = "segregated_leads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sheet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("segregated_lead_sheets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_number: Mapped[int] = mapped_column(default=1)
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    website: Mapped[str | None] = mapped_column(String(2048))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(50))
    location: Mapped[str | None] = mapped_column(String(255))
    instagram_handle: Mapped[str | None] = mapped_column(String(120))
    facebook_handle: Mapped[str | None] = mapped_column(String(120))
    whatsapp_link: Mapped[str | None] = mapped_column(String(255))
    priority_score: Mapped[int] = mapped_column(default=75)
    genuineness_score: Mapped[float] = mapped_column(default=0.9)
    seo_score: Mapped[int | None] = mapped_column(nullable=True)
    contactability_score: Mapped[int | None] = mapped_column(nullable=True)
    social_score: Mapped[int | None] = mapped_column(nullable=True)
    workflow_status: Mapped[str] = mapped_column(String(32), nullable=False, default="NEW")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="new")
    source: Mapped[str | None] = mapped_column(String(64), default="google_maps")
    notes: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sheet = relationship("SegregatedLeadSheet", back_populates="leads")

    @property
    def lead_code(self) -> str:
        return f"{self.sheet.sheet_number:04d}-{self.lead_number:02d}" if self.sheet else f"{self.lead_number:02d}"


def get_next_raw_sheet_number(session) -> int:
    max_num = session.scalar(select(func.max(RawLeadSheet.sheet_number)))
    return (max_num or 0) + 1


def get_next_segregated_sheet_number(session) -> int:
    max_num = session.scalar(select(func.max(SegregatedLeadSheet.sheet_number)))
    return (max_num or 0) + 1



class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    google_subject: Mapped[str | None] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="member")


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    website: Mapped[str | None] = mapped_column(String(2048))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text())
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scrape_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    lead_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    raw_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PERSISTED")
    verification_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="UNVERIFIED"
    )
    genuineness_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="NEEDS_REVIEW"
    )
    genuineness_score: Mapped[float] = mapped_column(nullable=False, default=0.5)
    workflow_status: Mapped[str] = mapped_column(String(32), nullable=False, default="NEW", server_default="NEW")
    follow_up_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_leads_ws_deleted_created", "workspace_id", "deleted_at", "created_at"),
        Index("ix_leads_ws_status", "workspace_id", "workflow_status"),
    )


class ScrapeJob(Base):
    __tablename__ = "scrape_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    niche: Mapped[str] = mapped_column(String(120), nullable=False)
    country: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    target_lead_count: Mapped[int] = mapped_column(default=100)
    sheet_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    service: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    sources: Mapped[list[str] | None] = mapped_column(JSON())
    enrichments: Mapped[list[str] | None] = mapped_column(JSON(), nullable=True, default=list)
    leads_scraped: Mapped[int] = mapped_column(default=0)
    discovered_count: Mapped[int] = mapped_column(default=0)
    valid_count: Mapped[int] = mapped_column(default=0)
    new_count: Mapped[int] = mapped_column(default=0)
    updated_count: Mapped[int] = mapped_column(default=0)
    duplicate_count: Mapped[int] = mapped_column(default=0)
    failed_count: Mapped[int] = mapped_column(default=0)
    current_source: Mapped[str | None] = mapped_column(String(64))
    current_query: Mapped[str | None] = mapped_column(String(255))
    progress_percent: Mapped[float] = mapped_column(default=0.0)
    error_message: Mapped[str | None] = mapped_column(Text())
    completion_reason: Mapped[str | None] = mapped_column(String(64))
    fetched_count: Mapped[int] = mapped_column(default=0)
    last_progress_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_scrape_jobs_ws_status", "workspace_id", "status"),
    )


class ScrapeJobExecutionLog(Base):
    __tablename__ = "scrape_job_execution_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scrape_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    query: Mapped[str] = mapped_column(String(255), nullable=False)
    page: Mapped[int] = mapped_column(default=1)
    records_received: Mapped[int] = mapped_column(default=0)
    records_valid: Mapped[int] = mapped_column(default=0)
    records_rejected: Mapped[int] = mapped_column(default=0)
    new_count: Mapped[int] = mapped_column(default=0)
    updated_count: Mapped[int] = mapped_column(default=0)
    duplicate_count: Mapped[int] = mapped_column(default=0)
    failed_count: Mapped[int] = mapped_column(default=0)
    error_reason: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SourceRecord(Base):
    __tablename__ = "source_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), index=True
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_data: Mapped[dict | None] = mapped_column(JSON())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=True, index=True
    )
    raw_lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw_leads.id", ondelete="CASCADE"), nullable=True, index=True
    )
    canonical_lead_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    field_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="UNVERIFIED")
    evidence_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    classification: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence_score: Mapped[int] = mapped_column(default=0)
    source: Mapped[str] = mapped_column(Text(), nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_evidence_ws_lead_field", "workspace_id", "lead_id", "field_name"),
        Index("ix_evidence_lead_field", "lead_id", "field_name"),
        Index("ix_evidence_type", "lead_id", "evidence_type"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource: Mapped[str] = mapped_column(String(120), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    payload: Mapped[dict | None] = mapped_column(JSON())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SuppressionList(Base):
    __tablename__ = "suppression_lists"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entry_type: Mapped[str] = mapped_column(String(32), nullable=False)  # EMAIL, DOMAIN, PHONE
    entry_value: Mapped[str] = mapped_column(String(320), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ServiceScore(Base):
    __tablename__ = "service_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=True, index=True
    )
    raw_lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw_leads.id", ondelete="CASCADE"), nullable=True, index=True
    )
    service_type: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # smma, web_design, seo, paid_ads
    score: Mapped[int] = mapped_column(nullable=False, default=0)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="LOW")
    breakdown: Mapped[dict | None] = mapped_column(JSON())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OutreachCampaign(Base):
    __tablename__ = "outreach_campaigns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    subject_template: Mapped[str] = mapped_column(String(255), nullable=False)
    body_template: Mapped[str] = mapped_column(Text(), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EmailDispatch(Base):
    __tablename__ = "email_dispatches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("outreach_campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=True, index=True
    )
    raw_lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw_leads.id", ondelete="CASCADE"), nullable=True, index=True
    )
    recipient_email: Mapped[str] = mapped_column(String(320), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HumanFeedback(Base):
    __tablename__ = "human_feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=True, index=True
    )
    raw_lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw_leads.id", ondelete="CASCADE"), nullable=True, index=True
    )
    rating: Mapped[str] = mapped_column(String(32), nullable=False)
    service_label: Mapped[str | None] = mapped_column(String(64))
    comments: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FeatureSnapshot(Base):
    __tablename__ = "feature_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=True, index=True
    )
    raw_lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw_leads.id", ondelete="CASCADE"), nullable=True, index=True
    )
    feature_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v3.0")
    snapshot_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PredictionLedger(Base):
    __tablename__ = "prediction_ledger"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=True, index=True
    )
    raw_lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw_leads.id", ondelete="CASCADE"), nullable=True, index=True
    )
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    feature_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v3.0")
    prediction: Mapped[float] = mapped_column(nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LeadAction(Base):
    __tablename__ = "lead_actions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=True, index=True
    )
    raw_lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw_leads.id", ondelete="CASCADE"), nullable=True, index=True
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)  # PHONE, EMAIL, WHATSAPP, SOCIAL_DM, CONTACT_PAGE, OTHER
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)  # NO_RESPONSE, INTERESTED, NOT_INTERESTED, FOLLOW_UP_SCHEDULED, WRONG_NUMBER, BOUNCED, MEETING_BOOKED, CONVERTED
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    follow_up_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now())

    __table_args__ = (
        Index("ix_actions_ws_lead_created", "workspace_id", "lead_id", "created_at"),
    )


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=True, index=True
    )
    raw_lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw_leads.id", ondelete="CASCADE"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    service_type: Mapped[str] = mapped_column(String(64), nullable=False)  # WEBSITE_DEVELOPMENT, SEO, SMMA, PAID_ADS, CUSTOM
    deal_value: Mapped[float] = mapped_column(nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="INR")
    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="QUALIFIED")  # NEW, CONTACTED, INTERESTED, QUALIFIED, PROPOSAL, NEGOTIATION, WON, LOST
    probability: Mapped[float] = mapped_column(nullable=False, default=0.4)
    expected_close_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(120), nullable=True, default="Sales Rep")
    win_loss_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now(), onupdate=lambda: datetime.now(UTC))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_deals_ws_stage", "workspace_id", "stage"),
        Index("ix_deals_ws_lead", "workspace_id", "lead_id"),
    )


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worker_id: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="HEALTHY")  # HEALTHY, BUSY, IDLE, STALE, DEAD
    current_job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    jobs_processed: Mapped[int] = mapped_column(default=0)
    jobs_failed: Mapped[int] = mapped_column(default=0)
    last_heartbeat: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now())
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now())
    last_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON(), nullable=True)


class JobStageLog(Base):
    __tablename__ = "job_stage_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scrape_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage: Mapped[str] = mapped_column(String(64), nullable=False)  # QUEUED, STARTED, DISCOVERY, IDENTITY_RESOLUTION, PERSISTENCE, WEBSITE_DISCOVERY, WEBSITE_ENRICHMENT, INTELLIGENCE, COMPLETED, PARTIAL, FAILED, CANCELLED
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="RUNNING")  # RUNNING, SUCCESS, FAILED, SKIPPED
    duration_ms: Mapped[float] = mapped_column(default=0.0)
    error_category: Mapped[str | None] = mapped_column(String(64), nullable=True)  # PROVIDER_TIMEOUT, DATABASE_ERROR, etc.
    error_detail: Mapped[str | None] = mapped_column(Text(), nullable=True)
    retry_count: Mapped[int] = mapped_column(default=0)
    metrics: Mapped[dict | None] = mapped_column(JSON(), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_job_stage_logs_job_stage", "job_id", "stage"),
        Index("ix_job_stage_logs_ws_created", "workspace_id", "started_at"),
    )


class Proposal(Base):
    __tablename__ = "proposals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    deal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("deals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    proposal_number: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    service_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PROPOSAL_DRAFT"
    )  # PROPOSAL_DRAFT, PROPOSAL_SENT, VIEWED, NEGOTIATION, ACCEPTED, REJECTED, EXPIRED
    current_version: Mapped[int] = mapped_column(default=1)
    base_price: Mapped[float] = mapped_column(nullable=False, default=0.0)
    addons_total: Mapped[float] = mapped_column(nullable=False, default=0.0)
    discount_amount: Mapped[float] = mapped_column(nullable=False, default=0.0)
    quoted_amount: Mapped[float] = mapped_column(nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="INR")
    scope_of_work: Mapped[str | None] = mapped_column(Text(), nullable=True)
    deliverables: Mapped[list | None] = mapped_column(JSON(), nullable=True)
    timeline: Mapped[str | None] = mapped_column(String(120), nullable=True)
    terms_and_conditions: Mapped[str | None] = mapped_column(Text(), nullable=True)
    expected_start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expiry_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index("ix_proposals_ws_status", "workspace_id", "status"),
        Index("ix_proposals_ws_deal", "workspace_id", "deal_id"),
        Index("ix_proposals_ws_lead", "workspace_id", "lead_id"),
    )


class ProposalVersion(Base):
    __tablename__ = "proposal_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("proposals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(nullable=False, default=1)
    base_price: Mapped[float] = mapped_column(nullable=False, default=0.0)
    addons_total: Mapped[float] = mapped_column(nullable=False, default=0.0)
    discount_amount: Mapped[float] = mapped_column(nullable=False, default=0.0)
    quoted_amount: Mapped[float] = mapped_column(nullable=False, default=0.0)
    scope_of_work: Mapped[str | None] = mapped_column(Text(), nullable=True)
    deliverables: Mapped[list | None] = mapped_column(JSON(), nullable=True)
    timeline: Mapped[str | None] = mapped_column(String(120), nullable=True)
    change_summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_proposal_versions_prop_ver", "proposal_id", "version_number"),
        Index("ix_proposal_versions_ws_created", "workspace_id", "created_at"),
    )


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ACTIVE"
    )  # ONBOARDING, ACTIVE, CHURNED, COMPLETED
    health_score: Mapped[str] = mapped_column(
        String(32), nullable=False, default="HEALTHY"
    )  # HEALTHY, AT_RISK, CRITICAL, DORMANT
    health_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mrr: Mapped[float] = mapped_column(nullable=False, default=0.0)
    arr: Mapped[float] = mapped_column(nullable=False, default=0.0)
    lifetime_value: Mapped[float] = mapped_column(nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="INR")
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_renewal_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    onboarded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index("ix_customers_ws_status", "workspace_id", "status"),
        Index("ix_customers_ws_health", "workspace_id", "health_score"),
        Index("ix_customers_ws_lead", "workspace_id", "lead_id"),
    )


class DeliveryProject(Base):
    __tablename__ = "delivery_projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    deal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("deals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    proposal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("proposals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    service_type: Mapped[str] = mapped_column(String(64), nullable=False)
    contract_value: Mapped[float] = mapped_column(nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="INR")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ONBOARDING"
    )  # ONBOARDING, REQUIREMENTS, IN_PROGRESS, REVIEW, CLIENT_APPROVAL, COMPLETED, ON_HOLD, CANCELLED
    progress_percent: Mapped[float] = mapped_column(nullable=False, default=0.0)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    target_completion_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_completion_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(120), nullable=True, default="Project Lead")
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index("ix_delivery_projects_ws_status", "workspace_id", "status"),
        Index("ix_delivery_projects_ws_customer", "workspace_id", "customer_id"),
    )


class ProjectDeliverable(Base):
    __tablename__ = "project_deliverables"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("delivery_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING"
    )  # PENDING, IN_PROGRESS, COMPLETED, BLOCKED
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=1)
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_project_deliverables_proj_status", "project_id", "status"),
        Index("ix_project_deliverables_ws_created", "workspace_id", "created_at"),
    )


class CustomerRetainer(Base):
    __tablename__ = "customer_retainers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_type: Mapped[str] = mapped_column(String(64), nullable=False)  # SEO_RETAINER, SMMA_RETAINER, WEBSITE_MAINTENANCE, HOSTING_MAINTENANCE, PAID_ADS_MANAGEMENT
    billing_frequency: Mapped[str] = mapped_column(String(32), nullable=False, default="MONTHLY")  # MONTHLY, QUARTERLY, ANNUAL
    billing_amount: Mapped[float] = mapped_column(nullable=False, default=0.0)
    monthly_mrr: Mapped[float] = mapped_column(nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="INR")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ACTIVE"
    )  # ACTIVE, EXPIRING_SOON, RENEWED, EXPIRED, CANCELLED
    start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
    renewal_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    auto_renew: Mapped[bool] = mapped_column(nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index("ix_customer_retainers_ws_status", "workspace_id", "status"),
        Index("ix_customer_retainers_cust_renewal", "customer_id", "renewal_date"),
    )


class UpsellOpportunity(Base):
    __tablename__ = "upsell_opportunities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_type: Mapped[str] = mapped_column(String(64), nullable=False)
    estimated_mrr: Mapped[float] = mapped_column(nullable=False, default=0.0)
    estimated_value: Mapped[float] = mapped_column(nullable=False, default=0.0)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="IDENTIFIED"
    )  # IDENTIFIED, PITCHED, ACCEPTED, DECLINED
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index("ix_upsell_opps_ws_status", "workspace_id", "status"),
        Index("ix_upsell_opps_cust", "workspace_id", "customer_id"),
    )


class ServiceOpportunity(Base):
    __tablename__ = "service_opportunities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Canonical lead compatibility for the phase 2 / worker pipeline.
    canonical_lead_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    raw_lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw_leads.id", ondelete="CASCADE"), nullable=True, index=True
    )

    service: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="INSUFFICIENT_DATA")
    opportunity_score: Mapped[int | None] = mapped_column(default=0)
    confidence_score: Mapped[int | None] = mapped_column(default=0)
    priority: Mapped[str | None] = mapped_column(String(32), nullable=True, default="LOW")
    reasons: Mapped[str | None] = mapped_column(Text(), nullable=True, default="[]")
    signals: Mapped[dict | None] = mapped_column(JSON(), default=dict)
    missing_data: Mapped[list[str] | None] = mapped_column(JSON(), default=list)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Canonical-lead classification compatibility.
    service_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    eligible: Mapped[str | None] = mapped_column(String(1), nullable=True, default="N")
    score: Mapped[float | None] = mapped_column(default=0.0)
    confidence: Mapped[float | None] = mapped_column(default=0.85)
    priority_rank: Mapped[int | None] = mapped_column(default=999)
    facebook_ads_detected: Mapped[str | None] = mapped_column(String(1), default="N")
    ssl_valid: Mapped[str | None] = mapped_column(String(1), default="N")
    model_version: Mapped[str | None] = mapped_column(String(50), default="service_classifier_v1")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("raw_lead_id", "service", name="uq_raw_lead_service"),
        UniqueConstraint("canonical_lead_id", "service_type", name="uq_canonical_lead_service_type"),
    )


class EnrichmentState(Base):
    __tablename__ = "enrichment_states"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw_leads.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    website_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    email_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    instagram_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    facebook_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    seo_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
