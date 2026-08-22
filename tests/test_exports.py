from __future__ import annotations

import uuid

from backend.app.exports import leads_to_csv, leads_to_xlsx, sanitize_cell
from backend.app.models import Lead


def test_formula_injection_sanitization() -> None:
    assert sanitize_cell("=1+1") == "'=1+1"
    assert sanitize_cell("+cmd") == "'+cmd"
    assert sanitize_cell("-100") == "'-100"
    assert sanitize_cell("@SUM(A1)") == "'@SUM(A1)"
    assert sanitize_cell("Normal Text") == "Normal Text"
    assert sanitize_cell(None) == ""


def test_leads_to_csv_export() -> None:
    lead = Lead(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        business_name="=Malicious Inc",
        website="https://example.com",
        email="test@example.com",
        phone="+1234567890",
        notes="Safe note",
    )
    csv_data = leads_to_csv([lead])
    assert "'=Malicious Inc" in csv_data
    assert "'+1234567890" in csv_data
    assert "https://example.com" in csv_data


def test_leads_to_xlsx_export() -> None:
    lead = Lead(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        business_name="=Formula Co",
        website="https://example.com",
        email="info@example.com",
        phone="123",
        notes="Note",
    )
    xlsx_bytes = leads_to_xlsx([lead])
    assert isinstance(xlsx_bytes, bytes)
    assert len(xlsx_bytes) > 0
