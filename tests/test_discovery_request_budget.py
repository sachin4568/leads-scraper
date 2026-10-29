import uuid
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from backend.app.api import create_lead
from backend.app.orchestration.discovery_orchestrator import _remove_phone_data
from backend.app.schemas import LeadCreate, LeadRead
from backend.app.worker import discovery_request_budget


def test_request_budget_scales_with_email_only_target() -> None:
    assert discovery_request_budget(100) == 1000


def test_request_budget_retains_minimum_for_small_targets() -> None:
    assert discovery_request_budget(5) == 60


def test_request_budget_is_capped() -> None:
    assert discovery_request_budget(10000) == 1000


def test_lead_api_schema_hides_legacy_phone_values() -> None:
    lead = LeadRead(
        id=uuid.uuid4(),
        business_name="Example Business",
        website="https://example.com",
        email="contact@example.com",
        phone="+1 555 0100",
        notes=None,
        created_at=datetime.now(UTC),
    )

    assert lead.model_dump()["phone"] is None


def test_phone_scrubber_removes_nested_and_camel_case_fields() -> None:
    sanitized = _remove_phone_data(
        {
            "nationalPhoneNumber": "+1 555 0100",
            "contact": {"telephone": "+1 555 0101", "email": "contact@example.com"},
            "business_name": "Example Business",
        }
    )

    assert sanitized == {
        "contact": {"email": "contact@example.com"},
        "business_name": "Example Business",
    }


def test_manual_lead_creation_rejects_phone_only_leads() -> None:
    with pytest.raises(HTTPException) as error:
        create_lead(LeadCreate(business_name="Phone Only Business"), uuid.uuid4(), object())

    assert error.value.status_code == 422
    assert "email is required" in error.value.detail


def test_manual_lead_creation_rejects_phone_even_with_email() -> None:
    with pytest.raises(HTTPException) as error:
        create_lead(
            LeadCreate(
                business_name="Example Business",
                email="contact@example.com",
                phone="+1 555 0100",
            ),
            uuid.uuid4(),
            object(),
        )

    assert error.value.status_code == 422
    assert "Phone numbers are not accepted" in error.value.detail
