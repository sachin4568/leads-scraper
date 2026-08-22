from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import openpyxl

logger = logging.getLogger(__name__)


class DataQualityValidator:
    """Performs strict data quality validation on input Excel workbooks."""

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.raw_rows: list[dict[str, Any]] = []
        self.report: dict[str, Any] = {}

    def load_and_validate(self) -> dict[str, Any]:
        path = Path(self.file_path)
        if not path.exists():
            raise FileNotFoundError(f"Workbook not found at {self.file_path}")

        wb = openpyxl.load_workbook(self.file_path, read_only=True)
        sheet = wb.active
        rows = list(sheet.iter_rows(values_only=True))
        headers = [str(h).strip() for h in rows[0]]

        self.raw_rows = [dict(zip(headers, r, strict=False)) for r in rows[1:]]
        total_count = len(self.raw_rows)

        # Duplicate Checks
        lead_ids = [r.get("Lead ID") for r in self.raw_rows if r.get("Lead ID")]
        dup_lead_ids = total_count - len(set(lead_ids))

        biz_names = [r.get("Business Name") for r in self.raw_rows if r.get("Business Name")]
        dup_names = total_count - len(set(biz_names))

        phones = [r.get("Phone") for r in self.raw_rows if r.get("Phone")]
        dup_phones = len(phones) - len(set(phones))

        emails = [r.get("Email") for r in self.raw_rows if r.get("Email")]
        dup_emails = len(emails) - len(set(emails))

        websites = [r.get("Website") for r in self.raw_rows if r.get("Website")]
        dup_websites = len(websites) - len(set(websites))

        # Value Range & Boolean Contradictions
        invalid_ratings = 0
        invalid_reviews = 0
        boolean_contradictions = 0

        for r in self.raw_rows:
            try:
                rating = float(r.get("Google Rating", 0))
                if rating < 1.0 or rating > 5.0:
                    invalid_ratings += 1
            except (ValueError, TypeError):
                invalid_ratings += 1

            try:
                review_count = int(r.get("Review Count", 0))
                if review_count < 0:
                    invalid_reviews += 1
            except (ValueError, TypeError):
                invalid_reviews += 1

            has_web = str(r.get("Has Website", "")).upper() == "TRUE"
            web_val = bool(r.get("Website"))
            if has_web != web_val:
                boolean_contradictions += 1

        self.report = {
            "file_path": self.file_path,
            "total_rows": total_count,
            "duplicate_lead_ids": dup_lead_ids,
            "duplicate_business_names": dup_names,
            "duplicate_phones": dup_phones,
            "duplicate_emails": dup_emails,
            "duplicate_websites": dup_websites,
            "invalid_rating_values": invalid_ratings,
            "invalid_review_counts": invalid_reviews,
            "boolean_contradictions": boolean_contradictions,
            "validation_passed": (
                dup_lead_ids == 0
                and dup_names == 0
                and invalid_ratings == 0
                and invalid_reviews == 0
            ),
        }

        # Save data quality report to disk
        out_path = Path("training_data/data_quality_report.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(self.report, f, indent=2)

        return self.report
