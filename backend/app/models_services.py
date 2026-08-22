from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text

from backend.app.models_phase2 import Base


class ServiceOpportunity(Base):
    """Multi-label service opportunity score & explainable classification per canonical lead."""

    __tablename__ = "service_opportunities"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    canonical_lead_id = Column(
        String(36), ForeignKey("canonical_leads.id"), nullable=False, index=True
    )

    # Service Type: WEBSITE_DEVELOPMENT, WEBSITE_SEO, SOCIAL_MEDIA_MANAGEMENT, SOCIAL_MEDIA_MARKETING
    service_type = Column(String(64), nullable=False, index=True)
    eligible = Column(String(1), nullable=False, default="N")  # Y / N

    score = Column(Float, nullable=False, default=0.0)  # 0.0 - 100.0
    confidence = Column(Float, nullable=False, default=0.85)  # 0.0 - 1.0
    priority_rank = Column(Integer, default=999, index=True)

    reasons = Column(Text, nullable=False, default="[]")  # JSON list string of explainable reasons

    facebook_ads_detected = Column(String(1), default="N")  # Y / N
    ssl_valid = Column(String(1), default="N")  # Y / N

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    model_version = Column(String(50), default="service_classifier_v1")
