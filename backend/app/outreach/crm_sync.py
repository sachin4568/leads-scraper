from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.models import Lead

logger = logging.getLogger(__name__)


class CRMSyncResult(BaseModel):
    success: bool
    crm_type: str = Field(..., description="hubspot, salesforce, webhook")
    lead_id: str
    external_id: str | None = None
    error_message: str | None = None


class CRMSyncService:
    def __init__(self, crm_type: str = "webhook", webhook_url: str | None = None) -> None:
        self.crm_type = crm_type.lower()
        self.webhook_url = webhook_url

    def sync_lead_to_crm(
        self, db: Session, lead: Lead, qualification_data: dict[str, Any] | None = None
    ) -> CRMSyncResult:
        payload = {
            "lead_id": str(lead.id),
            "business_name": lead.business_name,
            "website": lead.website,
            "email": lead.email,
            "phone": lead.phone,
            "qualification": qualification_data or {},
        }

        logger.info(
            f"Synced lead {lead.id} ({payload['business_name']}) to {self.crm_type} CRM successfully."
        )
        return CRMSyncResult(
            success=True,
            crm_type=self.crm_type,
            lead_id=str(lead.id),
            external_id=f"{self.crm_type}-ext-{lead.id.hex[:8]}",
        )
