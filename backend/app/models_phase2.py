from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class CanonicalLead(Base):
    """Authoritative canonical business representation across all sources."""

    __tablename__ = "canonical_leads"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    business_name = Column(String(255), nullable=False, index=True)
    canonical_domain = Column(String(255), index=True)
    canonical_phone = Column(String(50), index=True)
    canonical_email = Column(String(255), index=True)
    google_place_id = Column(String(255), index=True)

    industry = Column(String(100), nullable=False, index=True)
    address = Column(Text)
    city = Column(String(100), index=True)
    state = Column(String(100), index=True)
    country = Column(String(100), default="India", index=True)

    website_state = Column(String(50), default="UNKNOWN")
    business_maturity = Column(String(50), default="UNKNOWN")
    is_temporary = Column(Boolean, default=True, nullable=False, server_default="true")
    conflicts = Column(JSON, default=dict)

    observation_count = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    observations = relationship(
        "LeadObservation", back_populates="canonical_lead", cascade="all, delete-orphan"
    )
    identities = relationship(
        "LeadIdentity", back_populates="canonical_lead", cascade="all, delete-orphan"
    )
    change_histories = relationship(
        "LeadChangeHistory", back_populates="canonical_lead", cascade="all, delete-orphan"
    )
    contacts = relationship(
        "LeadContact", back_populates="canonical_lead", cascade="all, delete-orphan"
    )


class LeadObservation(Base):
    """Raw historical source observation tied to a canonical lead."""

    __tablename__ = "lead_observations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    canonical_lead_id = Column(
        String(36), ForeignKey("canonical_leads.id"), nullable=False, index=True
    )
    source_name = Column(String(100), nullable=False, index=True)
    source_record_id = Column(String(255), index=True)
    idempotency_key = Column(String(255), unique=True, index=True)

    observed_business_name = Column(String(255))
    observed_phone = Column(String(50))
    observed_email = Column(String(255))
    observed_website = Column(String(255))
    observed_address = Column(Text)
    observed_city = Column(String(100))

    match_level = Column(String(50))
    match_score = Column(Float)
    match_explanation = Column(Text)  # Structured JSON string of matched signals

    observed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    canonical_lead = relationship("CanonicalLead", back_populates="observations")


class LeadIdentity(Base):
    """Multi-signal canonical identity hashes for fast lookup and resolution."""

    __tablename__ = "lead_identities"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    canonical_lead_id = Column(
        String(36), ForeignKey("canonical_leads.id"), nullable=False, index=True
    )

    identity_hash = Column(String(64), nullable=False, index=True)
    identity_type = Column(String(50), nullable=False)  # PLACE_ID, PHONE, DOMAIN, EMAIL, COMPOSITE
    raw_signal = Column(String(255), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    canonical_lead = relationship("CanonicalLead", back_populates="identities")


class LeadChangeHistory(Base):
    """Audit log tracking historical field value transitions over time."""

    __tablename__ = "lead_change_histories"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    canonical_lead_id = Column(
        String(36), ForeignKey("canonical_leads.id"), nullable=False, index=True
    )
    observation_id = Column(String(36), nullable=False, index=True)

    field_name = Column(String(100), nullable=False)
    old_value = Column(Text)
    new_value = Column(Text)
    changed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    canonical_lead = relationship("CanonicalLead", back_populates="change_histories")


class LeadContact(Base):
    """Individual contact records associated with a canonical lead."""

    __tablename__ = "lead_contacts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    canonical_lead_id = Column(
        String(36), ForeignKey("canonical_leads.id"), nullable=False, index=True
    )

    full_name = Column(String(255))
    role = Column(
        String(50), default="GENERIC", nullable=False, index=True
    )  # OWNER, DECISION_MAKER, RECEPTION, etc.
    priority_level = Column(Integer, default=7)  # 1=Owner, 7=Generic

    phone = Column(String(50))
    email = Column(String(255))
    source_name = Column(String(100))
    confidence = Column(Float, default=0.5)
    evidence_reference = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    canonical_lead = relationship("CanonicalLead", back_populates="contacts")


class HumanOutcomeEventRecord(Base):
    """Separate human feedback events preserved without overwriting ML predictions."""

    __tablename__ = "human_outcome_event_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    canonical_lead_id = Column(String(36), nullable=False, index=True)

    original_prediction = Column(String(50), nullable=False)
    original_probability = Column(Float, nullable=False)
    original_model_version = Column(String(50), nullable=False)

    human_outcome = Column(String(50), nullable=False, index=True)
    reason = Column(Text)
    decision_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
