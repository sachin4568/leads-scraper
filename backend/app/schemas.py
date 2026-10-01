from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str


class LeadCreate(BaseModel):
    business_name: str = Field(min_length=1, max_length=255)
    website: str | None = Field(default=None, max_length=2048)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    notes: str | None = None


class LeadUpdate(LeadCreate):
    business_name: str | None = Field(default=None, min_length=1, max_length=255)


class LeadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    business_name: str
    website: str | None
    email: EmailStr | None
    phone: str | None
    notes: str | None
    created_at: datetime


class ScrapeJobCreate(BaseModel):
    niche: str = Field(min_length=1, max_length=120)
    country: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    target_lead_count: int = Field(default=100, ge=1, le=10000)
    sources: list[str] = Field(default_factory=lambda: ["google_maps"])
    
    # Advanced Options & Compact Configuration (Ignored on DB model insertion where unsupported)
    plain_query: str | None = None
    exact_match: bool | None = None
    related_categories: bool | None = None
    city: str | None = None
    locations: list[str] | None = None
    service: str | None = None
    search_mode: str | None = None
    search_depth: str | None = None
    enrichments: Any = None
    deduplication_mode: str | None = None
    quality_threshold: str | None = None


class ScrapeJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    workspace_id: uuid.UUID
    niche: str
    country: str | None
    region: str | None
    state: str | None
    target_lead_count: int
    status: str
    service: str | None = None
    sources: list[str] | None
    enrichments: Any = None
    leads_scraped: int
    discovered_count: int = 0
    valid_count: int = 0
    new_count: int = 0
    updated_count: int = 0
    duplicate_count: int = 0
    failed_count: int = 0
    current_source: str | None = None
    current_query: str | None = None
    progress_percent: float = 0.0
    error_message: str | None
    completion_reason: str | None = None
    fetched_count: int = 0
    created_at: datetime
    updated_at: datetime


class EvidenceRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    workspace_id: uuid.UUID
    lead_id: uuid.UUID
    field_name: str
    status: str
    confidence_score: int
    source: str
    details: dict | None
    created_at: datetime


class SuppressionCreate(BaseModel):
    entry_type: str = Field(..., description="EMAIL, DOMAIN, or PHONE")
    entry_value: str = Field(..., min_length=1, max_length=320)
    reason: str | None = Field(default=None, max_length=255)


class SuppressionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    workspace_id: uuid.UUID
    entry_type: str
    entry_value: str
    reason: str | None
    created_at: datetime


class LeadEnrichmentResponse(BaseModel):
    lead_id: uuid.UUID
    overall_confidence: int
    field_scores: dict[str, int]
    evidence: list[EvidenceRecordRead]


class LeadQualificationResponse(BaseModel):
    lead_id: uuid.UUID
    overall_smma_score: int
    priority_rank: str
    conversion_probability: float
    breakdown_scores: dict[str, int]
    key_opportunities: list[str]
    llm_summary: str | None = None


class ServiceScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    workspace_id: uuid.UUID
    lead_id: uuid.UUID
    service_type: str
    score: int
    priority: str
    breakdown: dict | None
    created_at: datetime


class OutreachCampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    subject_template: str = Field(min_length=1, max_length=255)
    body_template: str = Field(min_length=1)


class OutreachCampaignRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    subject_template: str
    body_template: str
    status: str
    created_at: datetime
    updated_at: datetime


class EmailDispatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    workspace_id: uuid.UUID
    campaign_id: uuid.UUID
    lead_id: uuid.UUID
    recipient_email: str
    status: str
    sent_at: datetime | None
    error_message: str | None
    created_at: datetime


class CampaignSendResponse(BaseModel):
    campaign_id: uuid.UUID
    dispatches_count: int
    status: str


class HumanFeedbackCreate(BaseModel):
    rating: str = Field(..., description="GOOD, BAD, EXCELLENT, REJECT")
    service_label: str | None = None
    comments: str | None = None


class HumanFeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    workspace_id: uuid.UUID
    lead_id: uuid.UUID
    rating: str
    service_label: str | None
    comments: str | None
    created_at: datetime


class ModelTrainResponse(BaseModel):
    model_version: str
    metrics: dict[str, float]
    status: str


class RecommendedChannelInfo(BaseModel):
    channel: str = "NONE"  # WHATSAPP, EMAIL, PHONE, SOCIAL_DM, NONE
    value: str | None = None
    label: str = "No Direct Channel"


class PriorityQueueInfo(BaseModel):
    queue: str = "STANDARD"  # CONTACT_NOW, FOLLOW_UP_OVERDUE, FOLLOW_UP_SCHEDULED, REVIEW, NO_CONTACT_CHANNEL, ARCHIVED, STANDARD
    badge: str = "Standard Priority"
    urgency: int = 30


class ExecutionLink(BaseModel):
    channel: str  # PHONE, EMAIL, WHATSAPP, SOCIAL_DM, CONTACT_PAGE
    label: str
    url: str
    is_direct: bool = True


class TimelineEvent(BaseModel):
    id: str
    event_type: str  # DISCOVERY, WEBSITE_VERIFICATION, ENRICHMENT, OPPORTUNITY_SCORING, OUTREACH_ATTEMPT, RESPONSE_RECEIVED, FOLLOW_UP, MEETING, QUALIFICATION, CONVERSION, LOST
    title: str
    description: str
    channel: str | None = None
    outcome: str | None = None
    timestamp: datetime
    source: str
    metadata: dict = Field(default_factory=dict)


class LeadTimelineResponse(BaseModel):
    lead_id: uuid.UUID
    business_name: str
    current_workflow_status: str
    events: list[TimelineEvent]


class ChannelMetrics(BaseModel):
    channel: str
    attempts: int = 0
    responses: int = 0
    interested: int = 0
    meetings_booked: int = 0
    conversions: int = 0
    response_rate: float = 0.0
    interest_rate: float = 0.0
    conversion_rate: float = 0.0


class ServiceMetrics(BaseModel):
    service: str
    leads_count: int = 0
    attempts: int = 0
    responses: int = 0
    interested: int = 0
    meetings_booked: int = 0
    conversions: int = 0


class PipelineFunnelStage(BaseModel):
    stage: str
    count: int
    conversion_rate_from_previous: float = 0.0
    conversion_rate_from_total: float = 0.0


class OutreachAnalyticsResponse(BaseModel):
    total_leads: int
    contactable_leads: int
    contacted_leads: int
    responded_leads: int
    interested_leads: int
    meeting_booked_leads: int
    qualified_leads: int
    converted_leads: int
    lost_leads: int
    overall_response_rate: float = 0.0
    overall_interest_rate: float = 0.0
    overall_conversion_rate: float = 0.0
    funnel: list[PipelineFunnelStage] = Field(default_factory=list)
    channel_effectiveness: list[ChannelMetrics] = Field(default_factory=list)
    service_effectiveness: list[ServiceMetrics] = Field(default_factory=list)


class LeadActionCreate(BaseModel):
    channel: str = Field(..., pattern="^(PHONE|EMAIL|WHATSAPP|SOCIAL_DM|CONTACT_PAGE|OTHER)$")
    outcome: str = Field(..., pattern="^(CONTACTED|RESPONDED|INTERESTED|NOT_INTERESTED|MEETING_BOOKED|QUALIFIED|CONVERTED|LOST|NO_RESPONSE|WRONG_NUMBER|BOUNCED|FOLLOW_UP_SCHEDULED)$")
    notes: str | None = None
    follow_up_date: datetime | None = None
    next_workflow_status: str | None = Field(default=None, pattern="^(NEW|REVIEWED|CONTACTED|QUALIFIED|CONVERTED|DISMISSED|LOST)$")


class LeadActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    workspace_id: uuid.UUID
    lead_id: uuid.UUID
    channel: str
    outcome: str
    notes: str | None = None
    follow_up_date: datetime | None = None
    created_at: datetime


class OperationsLeadRead(BaseModel):
    id: uuid.UUID
    business_name: str
    category: str | None = None
    location: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    website_status: str = "NO_WEBSITE"
    opportunity_score: int = 50
    opportunity_category: str = "MEDIUM"
    genuineness_score: float = 0.85
    recommended_service: str | None = None
    recommended_service_score: float | None = None
    workflow_status: str = "NEW"
    top_reasons: list[str] = Field(default_factory=list)
    has_conflict: bool = False
    has_whatsapp: bool = False
    has_social: bool = False
    recommended_channel: RecommendedChannelInfo = Field(default_factory=RecommendedChannelInfo)
    priority_queue: PriorityQueueInfo = Field(default_factory=PriorityQueueInfo)
    execution_links: list[ExecutionLink] = Field(default_factory=list)
    follow_up_date: datetime | None = None
    actions_count: int = 0
    latest_action: LeadActionRead | None = None
    last_enriched_at: datetime | None = None
    created_at: datetime


class DealCreate(BaseModel):
    lead_id: uuid.UUID
    title: str
    service_type: str = Field(default="WEBSITE_DEVELOPMENT", pattern="^(WEBSITE_DEVELOPMENT|SEO|SMMA|PAID_ADS|CUSTOM)$")
    deal_value: float = Field(default=0.0, ge=0.0)
    currency: str = "INR"
    stage: str = Field(default="QUALIFIED", pattern="^(NEW|CONTACTED|INTERESTED|QUALIFIED|PROPOSAL|NEGOTIATION|WON|LOST)$")
    probability: float | None = Field(default=None, ge=0.0, le=1.0)
    expected_close_date: datetime | None = None
    owner: str | None = "Sales Rep"
    win_loss_reason: str | None = None
    notes: str | None = None


class DealUpdate(BaseModel):
    title: str | None = None
    service_type: str | None = Field(default=None, pattern="^(WEBSITE_DEVELOPMENT|SEO|SMMA|PAID_ADS|CUSTOM)$")
    deal_value: float | None = Field(default=None, ge=0.0)
    currency: str | None = None
    stage: str | None = Field(default=None, pattern="^(NEW|CONTACTED|INTERESTED|QUALIFIED|PROPOSAL|NEGOTIATION|WON|LOST)$")
    probability: float | None = Field(default=None, ge=0.0, le=1.0)
    expected_close_date: datetime | None = None
    owner: str | None = None
    win_loss_reason: str | None = None
    notes: str | None = None


class DealRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    workspace_id: uuid.UUID
    lead_id: uuid.UUID
    business_name: str | None = None
    title: str
    service_type: str
    deal_value: float
    currency: str
    stage: str
    probability: float
    weighted_value: float
    expected_close_date: datetime | None = None
    owner: str | None = None
    win_loss_reason: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None


class CrmStageMetrics(BaseModel):
    stage: str
    count: int = 0
    total_value: float = 0.0
    weighted_value: float = 0.0


class RevenueBreakdownItem(BaseModel):
    category: str
    deals_count: int = 0
    won_revenue: float = 0.0
    pipeline_value: float = 0.0


class CrmPipelineDashboardResponse(BaseModel):
    total_pipeline_value: float
    weighted_pipeline_value: float
    won_revenue: float
    lost_value: float
    total_deals: int
    active_deals_count: int
    won_deals_count: int
    lost_deals_count: int
    avg_deal_size: float
    win_rate: float
    stages: list[CrmStageMetrics] = Field(default_factory=list)
    revenue_by_service: list[RevenueBreakdownItem] = Field(default_factory=list)
    revenue_by_source: list[RevenueBreakdownItem] = Field(default_factory=list)
    recent_deals: list[DealRead] = Field(default_factory=list)


class OperationsLeadDetail(OperationsLeadRead):
    contactability: dict = Field(default_factory=dict)
    website_health: dict = Field(default_factory=dict)
    seo: dict = Field(default_factory=dict)
    social: dict = Field(default_factory=dict)
    technologies: list[str] = Field(default_factory=list)
    service_opportunities: dict = Field(default_factory=dict)
    evidence_records: list[dict] = Field(default_factory=list)
    conflicts: dict = Field(default_factory=dict)
    action_history: list[LeadActionRead] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    deals: list[DealRead] = Field(default_factory=list)


class WorkflowStatusUpdateRequest(BaseModel):
    workflow_status: str = Field(..., pattern="^(NEW|REVIEWED|CONTACTED|QUALIFIED|CONVERTED|DISMISSED|LOST)$")


class BulkWorkflowStatusUpdateRequest(BaseModel):
    lead_ids: list[uuid.UUID]
    workflow_status: str = Field(..., pattern="^(NEW|REVIEWED|CONTACTED|QUALIFIED|CONVERTED|DISMISSED|LOST)$")


class OperationsLeadListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[OperationsLeadRead]


class OutreachDashboardResponse(BaseModel):
    total_leads: int
    new_leads: int
    ready_to_contact: int
    contacted: int
    follow_up_required: int
    overdue_follow_ups_count: int
    qualified: int
    converted: int
    dismissed: int
    channels_breakdown: dict[str, int]
    recent_actions: list[LeadActionRead] = Field(default_factory=list)


# ─── Phase 15: Production Dashboard & Business Analytics Schemas ───────────────

class ExecutiveKpiSummary(BaseModel):
    total_leads: int
    contactable_leads: int
    contacted_leads: int
    responded_leads: int
    qualified_leads: int
    won_leads: int
    lost_leads: int
    total_pipeline_value: float
    weighted_pipeline_value: float
    won_revenue: float
    lost_value: float
    overall_conversion_rate: float
    overall_response_rate: float
    win_rate: float
    avg_deal_size: float


class QualityTierPerformance(BaseModel):
    tier: str
    leads_count: int
    contactable_count: int
    contactable_pct: float
    contacted_count: int
    contacted_pct: float
    qualified_count: int
    qualified_pct: float
    won_count: int
    won_pct: float
    won_revenue: float
    avg_deal_size: float


class SourcePerformance(BaseModel):
    source: str
    leads_count: int
    contactable_pct: float
    response_pct: float
    qualified_pct: float
    won_pct: float
    won_revenue: float
    pipeline_value: float
    avg_deal_size: float


class ServicePerformanceAnalytics(BaseModel):
    service: str
    leads_pitched: int
    opportunities_count: int
    pipeline_value: float
    won_revenue: float
    win_rate: float
    avg_deal_size: float


class AnalyticsOverviewResponse(BaseModel):
    timeframe: str
    start_date: datetime | None = None
    end_date: datetime | None = None
    kpis: ExecutiveKpiSummary
    funnel: list[PipelineFunnelStage] = Field(default_factory=list)
    quality_performance: list[QualityTierPerformance] = Field(default_factory=list)
    source_performance: list[SourcePerformance] = Field(default_factory=list)
    service_performance: list[ServicePerformanceAnalytics] = Field(default_factory=list)
    channel_effectiveness: list[ChannelMetrics] = Field(default_factory=list)

class ServiceOpportunityRead(BaseModel):
    id: uuid.UUID
    raw_lead_id: uuid.UUID
    service: str
    status: str
    opportunity_score: int
    confidence_score: int
    priority: str
    reasons: list[str]
    signals: dict[str, Any]
    missing_data: list[str]
    evaluated_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True

class RawLeadEvidenceRead(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    raw_lead_id: uuid.UUID | None
    lead_id: uuid.UUID | None
    field_name: str
    status: str
    confidence_score: int
    source: str
    details: dict | None
    created_at: datetime

    class Config:
        from_attributes = True

class EnrichmentStatusResponse(BaseModel):
    emails_found: int
    opportunities_scored: int
    websites_found: int


class EnrichmentStateRead(BaseModel):
    id: uuid.UUID
    raw_lead_id: uuid.UUID
    website_status: str
    email_status: str
    social_status: str
    seo_status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True



class EvidenceRecordUpdate(BaseModel):
    evidence_type: str | None = None
    classification: str | None = None

