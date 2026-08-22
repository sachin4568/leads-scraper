from __future__ import annotations

import logging
import re
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.enrichment.entity_resolution import EntityResolver
from backend.app.models import Lead, SuppressionList

logger = logging.getLogger(__name__)


class SuppressionService:
    @staticmethod
    def _normalize_value(entry_type: str, entry_value: str) -> str:
        clean_type = entry_type.upper().strip()
        val = entry_value.strip().lower()

        if clean_type == "PHONE":
            val = re.sub(r"\D", "", val)
        elif clean_type == "DOMAIN":
            val = EntityResolver.normalize_domain(val) or val

        return val

    def add_suppression(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        entry_type: str,
        entry_value: str,
        reason: str | None = None,
    ) -> SuppressionList:
        clean_type = entry_type.upper().strip()
        clean_value = self._normalize_value(clean_type, entry_value)

        existing = db.scalar(
            select(SuppressionList).where(
                SuppressionList.workspace_id == workspace_id,
                SuppressionList.entry_type == clean_type,
                SuppressionList.entry_value == clean_value,
            )
        )
        if existing:
            return existing

        entry = SuppressionList(
            workspace_id=workspace_id,
            entry_type=clean_type,
            entry_value=clean_value,
            reason=reason,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    def is_suppressed(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        email: str | None = None,
        domain: str | None = None,
        phone: str | None = None,
    ) -> tuple[bool, str | None]:
        entries = db.scalars(
            select(SuppressionList).where(SuppressionList.workspace_id == workspace_id)
        ).all()

        if not entries:
            return False, None

        clean_email = email.strip().lower() if email else None
        clean_domain = EntityResolver.normalize_domain(domain) if domain else None
        clean_phone = re.sub(r"\D", "", phone) if phone else None

        for entry in entries:
            if entry.entry_type == "EMAIL" and clean_email and entry.entry_value == clean_email:
                return (
                    True,
                    f"Email '{clean_email}' is on suppression list (Reason: {entry.reason})",
                )
            if entry.entry_type == "DOMAIN" and clean_domain and entry.entry_value == clean_domain:
                return (
                    True,
                    f"Domain '{clean_domain}' is on suppression list (Reason: {entry.reason})",
                )
            if entry.entry_type == "PHONE" and clean_phone and entry.entry_value == clean_phone:
                return (
                    True,
                    f"Phone '{clean_phone}' is on suppression list (Reason: {entry.reason})",
                )

        return False, None

    def filter_suppressed_leads(
        self, db: Session, workspace_id: uuid.UUID, leads: list[Lead]
    ) -> list[Lead]:
        filtered: list[Lead] = []
        for lead in leads:
            lead_domain = EntityResolver.normalize_domain(lead.website)
            suppressed, _ = self.is_suppressed(
                db,
                workspace_id,
                email=lead.email,
                domain=lead_domain,
                phone=lead.phone,
            )
            if not suppressed:
                filtered.append(lead)
        return filtered
