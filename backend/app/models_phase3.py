from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class PredictionHistoryRecord(Base):
    """Immutable append-only record of every ML prediction."""

    __tablename__ = "prediction_history_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    canonical_lead_id = Column(String(36), nullable=False, index=True)

    model_name = Column(String(100), nullable=False)
    model_version = Column(String(50), nullable=False, index=True)
    feature_version = Column(String(50), nullable=False)

    predicted_probability = Column(Float, nullable=False)
    predicted_decision = Column(String(50), nullable=False)
    operating_threshold = Column(Float, default=0.50)

    feature_snapshot_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    prediction_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    human_outcomes = relationship("HumanOutcomeEvent", back_populates="prediction_record")


class HumanOutcomeEvent(Base):
    """Auditable multi-dimensional human feedback event linked to a prediction."""

    __tablename__ = "human_outcome_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    canonical_lead_id = Column(String(36), nullable=False, index=True)
    prediction_id = Column(
        String(36), ForeignKey("prediction_history_records.id"), nullable=True, index=True
    )
    reviewer_id = Column(String(100), default="system_reviewer")

    genuineness_outcome = Column(String(50), nullable=False)  # GENUINE, NOT_GENUINE, UNCERTAIN
    contactability_outcome = Column(
        String(50), nullable=False
    )  # OWNER_CONTACT, RECEPTION_CONTACT, etc.
    productivity_outcome = Column(
        String(50), nullable=False
    )  # PRODUCTIVE, UNPRODUCTIVE, NOT_ATTEMPTED
    qualification_outcome = Column(
        String(50), nullable=False
    )  # QUALIFIED, NOT_QUALIFIED, WRONG_SERVICE_MATCH
    service_opportunity_flags = Column(
        Text, nullable=False
    )  # JSON array string: ["WEBSITE", "SEO"]
    website_review_state = Column(String(50), default="UNKNOWN")

    reason_code = Column(String(100))
    free_text_notes = Column(Text)
    evidence_reference = Column(Text)

    feedback_state = Column(
        String(50), default="UNREVIEWED", index=True
    )  # UNREVIEWED, VALIDATED, READY_FOR_TRAINING
    human_outcome_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    prediction_record = relationship("PredictionHistoryRecord", back_populates="human_outcomes")


class ActiveLearningCandidate(Base):
    """Queue record for active learning manual review prioritization."""

    __tablename__ = "active_learning_candidates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    canonical_lead_id = Column(String(36), nullable=False, index=True)
    niche = Column(String(100), nullable=False, index=True)
    city = Column(String(100), nullable=False, index=True)

    uncertainty_score = Column(Float, nullable=False)
    model_disagreement_score = Column(Float, default=0.0)
    identity_ambiguity_flag = Column(Boolean, default=False)
    novelty_score = Column(Float, default=0.0)

    composite_priority_score = Column(Float, nullable=False, index=True)
    priority_reason = Column(Text)

    selection_count = Column(Integer, default=1)
    review_status = Column(
        String(50), default="UNREVIEWED", index=True
    )  # UNREVIEWED, SELECTED, REVIEWED
    last_selected_timestamp = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class FeedbackDatasetRecord(Base):
    """Versioned feedback dataset export registry."""

    __tablename__ = "feedback_dataset_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dataset_version = Column(String(50), nullable=False, unique=True, index=True)
    dataset_type = Column(
        String(50), nullable=False
    )  # GENUINENESS, PRODUCTIVITY, SERVICE_OPPORTUNITY
    feature_version = Column(String(50), nullable=False)

    row_count = Column(Integer, nullable=False)
    label_distribution = Column(Text, nullable=False)  # JSON string
    artifact_path = Column(String(255), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
