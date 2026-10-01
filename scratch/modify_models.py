with open('backend/app/models.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Update EvidenceRecord
old_evidence = '''    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )'''
new_evidence = '''    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=True, index=True
    )
    raw_lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw_leads.id", ondelete="CASCADE"), nullable=True, index=True
    )'''
text = text.replace(old_evidence, new_evidence)

# Add ServiceOpportunity at the end
service_opportunity_model = '''

class ServiceOpportunity(Base):
    __tablename__ = "service_opportunities"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw_leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    service: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="INSUFFICIENT_DATA")
    opportunity_score: Mapped[int] = mapped_column(default=0)
    confidence_score: Mapped[int] = mapped_column(default=0)
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="LOW")
    reasons: Mapped[list[str]] = mapped_column(JSON(), default=list)
    signals: Mapped[dict] = mapped_column(JSON(), default=dict)
    missing_data: Mapped[list[str]] = mapped_column(JSON(), default=list)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('raw_lead_id', 'service', name='uq_raw_lead_service'),
    )
'''
if "class ServiceOpportunity" not in text:
    text += service_opportunity_model

# Need to add UniqueConstraint to imports if not there
if 'UniqueConstraint' not in text:
    text = text.replace('from sqlalchemy import ', 'from sqlalchemy import UniqueConstraint, ')

with open('backend/app/models.py', 'w', encoding='utf-8') as f:
    f.write(text)
