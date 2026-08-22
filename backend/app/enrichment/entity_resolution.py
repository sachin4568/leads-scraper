from __future__ import annotations

import difflib
import logging
import re
import uuid
from typing import ClassVar
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import EvidenceRecord, Lead, SourceRecord

logger = logging.getLogger(__name__)


class EntityResolver:
    CORPORATE_SUFFIXES: ClassVar[set[str]] = {
        "inc",
        "llc",
        "corp",
        "corporation",
        "ltd",
        "limited",
        "co",
        "company",
        "pvt",
        "private",
        "group",
        "services",
    }

    @staticmethod
    def normalize_domain(url: str | None) -> str | None:
        if not url or not url.strip():
            return None
        target = url.strip()
        if not target.startswith(("http://", "https://")):
            target = f"https://{target}"
        try:
            parsed = urlparse(target)
            hostname = parsed.hostname or ""
            hostname = hostname.lower().strip()
            if hostname.startswith("www."):
                hostname = hostname[4:]
            return hostname if hostname else None
        except Exception:
            return None

    @classmethod
    def normalize_name(cls, name: str | None) -> str | None:
        if not name or not name.strip():
            return None
        cleaned = re.sub(r"[^\w\s]", "", name.lower()).strip()
        words = [w for w in cleaned.split() if w not in cls.CORPORATE_SUFFIXES]
        return " ".join(words) if words else cleaned

    @classmethod
    def calculate_match_score(cls, lead_a: Lead, lead_b: Lead) -> float:
        # Match check 1: Canonical Domain Match
        dom_a = cls.normalize_domain(lead_a.website)
        dom_b = cls.normalize_domain(lead_b.website)
        if dom_a and dom_b and dom_a == dom_b:
            return 1.0

        # Match check 2: Phone Match
        if lead_a.phone and lead_b.phone:
            clean_p1 = re.sub(r"\D", "", lead_a.phone)
            clean_p2 = re.sub(r"\D", "", lead_b.phone)
            if clean_p1 and clean_p2 and clean_p1 == clean_p2:
                return 1.0

        # Match check 3: Email Match
        if lead_a.email and lead_b.email:
            if lead_a.email.strip().lower() == lead_b.email.strip().lower():
                return 1.0

        # Match check 4: Business Name Similarity
        name_a = cls.normalize_name(lead_a.business_name)
        name_b = cls.normalize_name(lead_b.business_name)
        if name_a and name_b:
            if name_a == name_b:
                return 0.95
            ratio = difflib.SequenceMatcher(None, name_a, name_b).ratio()
            if ratio >= 0.85:
                return round(ratio, 2)

        return 0.0

    def find_duplicate_leads(
        self, db: Session, workspace_id: uuid.UUID, lead: Lead, min_score: float = 0.85
    ) -> list[tuple[Lead, float]]:
        all_leads = db.scalars(
            select(Lead).where(
                Lead.workspace_id == workspace_id,
                Lead.id != lead.id,
                Lead.deleted_at.is_(None),
            )
        ).all()

        duplicates: list[tuple[Lead, float]] = []
        for candidate in all_leads:
            score = self.calculate_match_score(lead, candidate)
            if score >= min_score:
                duplicates.append((candidate, score))

        duplicates.sort(key=lambda item: item[1], reverse=True)
        return duplicates

    def merge_leads(self, db: Session, primary_lead: Lead, duplicate_lead: Lead) -> Lead:
        from datetime import UTC, datetime

        # Copy non-null field values to primary lead if missing
        if not primary_lead.website and duplicate_lead.website:
            primary_lead.website = duplicate_lead.website
        if not primary_lead.phone and duplicate_lead.phone:
            primary_lead.phone = duplicate_lead.phone
        if not primary_lead.email and duplicate_lead.email:
            primary_lead.email = duplicate_lead.email
        if duplicate_lead.notes:
            primary_lead.notes = (
                f"{primary_lead.notes or ''}\n[Merged Note]: {duplicate_lead.notes}".strip()
            )

        # Reassign source records to primary lead
        source_recs = db.scalars(
            select(SourceRecord).where(SourceRecord.lead_id == duplicate_lead.id)
        ).all()
        for src in source_recs:
            src.lead_id = primary_lead.id

        # Reassign evidence records to primary lead
        evidence_recs = db.scalars(
            select(EvidenceRecord).where(EvidenceRecord.lead_id == duplicate_lead.id)
        ).all()
        for ev in evidence_recs:
            ev.lead_id = primary_lead.id

        # Soft-delete duplicate lead
        duplicate_lead.deleted_at = datetime.now(UTC)
        db.commit()
        db.refresh(primary_lead)
        return primary_lead
