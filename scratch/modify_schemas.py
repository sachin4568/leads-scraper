with open('backend/app/schemas.py', 'r', encoding='utf-8') as f:
    text = f.read()

new_schemas = '''
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
'''
if "class ServiceOpportunityRead" not in text:
    text += new_schemas

with open('backend/app/schemas.py', 'w', encoding='utf-8') as f:
    f.write(text)
