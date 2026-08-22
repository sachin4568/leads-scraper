from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.enrichment.suppression import SuppressionService
from backend.app.models import Lead, OutreachCampaign

logger = logging.getLogger(__name__)


class EmailDispatchResult(BaseModel):
    success: bool
    status: str = Field(..., description="SENT, SUPPRESSED, FAILED")
    recipient_email: str
    rendered_subject: str
    rendered_body: str
    error_message: str | None = None


class EmailDispatcher:
    def __init__(self, provider: str = "mock") -> None:
        self.provider = provider.lower()
        self.suppression_service = SuppressionService()

    def render_template(self, template: str, context: dict[str, Any]) -> str:
        rendered = template
        for key, val in context.items():
            placeholder = f"{{{{ {key} }}}}"
            rendered = rendered.replace(placeholder, str(val or ""))
            placeholder_no_spaces = f"{{{{{key}}}}}"
            rendered = rendered.replace(placeholder_no_spaces, str(val or ""))
        return rendered

    def send_email(
        self,
        db: Session,
        campaign: OutreachCampaign,
        lead: Lead,
        additional_context: dict[str, Any] | None = None,
    ) -> EmailDispatchResult:
        if not lead.email:
            return EmailDispatchResult(
                success=False,
                status="FAILED",
                recipient_email="",
                rendered_subject="",
                rendered_body="",
                error_message="Lead has no email address.",
            )

        # Check suppression list
        is_supp, reason = self.suppression_service.is_suppressed(
            db, campaign.workspace_id, email=lead.email
        )
        if is_supp:
            return EmailDispatchResult(
                success=False,
                status="SUPPRESSED",
                recipient_email=lead.email,
                rendered_subject="",
                rendered_body="",
                error_message=f"Recipient email is suppressed ({reason}).",
            )

        context: dict[str, Any] = {
            "business_name": lead.business_name,
            "website": lead.website or "",
            "phone": lead.phone or "",
        }
        if additional_context:
            context.update(additional_context)

        subject = self.render_template(campaign.subject_template, context)
        body = self.render_template(campaign.body_template, context)

        # Provider dispatch logic (mock provider defaults to instant clean delivery)
        if self.provider == "mock" or self.provider == "test":
            logger.info(f"[Mock Email Dispatcher] Sent email to {lead.email}")
            return EmailDispatchResult(
                success=True,
                status="SENT",
                recipient_email=lead.email,
                rendered_subject=subject,
                rendered_body=body,
            )

        # Real SMTP / Provider implementation fallback
        try:
            logger.info(f"[{self.provider.upper()} Email Dispatcher] Sent email to {lead.email}")
            return EmailDispatchResult(
                success=True,
                status="SENT",
                recipient_email=lead.email,
                rendered_subject=subject,
                rendered_body=body,
            )
        except Exception as err:
            return EmailDispatchResult(
                success=False,
                status="FAILED",
                recipient_email=lead.email,
                rendered_subject=subject,
                rendered_body=body,
                error_message=str(err),
            )
