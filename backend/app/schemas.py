from __future__ import annotations

import uuid
from datetime import datetime

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
    enrichments: list[str] | None = None
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
    sources: list[str] | None
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
