from __future__ import annotations

import pytest
import uuid
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.enrichment.website_validator import WebsiteValidator, WebsiteValidationResult
from backend.app.intelligence.completeness import CompletenessChecker
from backend.app.models import Lead, EvidenceRecord


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_website_domain_token_matching() -> None:
    validator = WebsiteValidator()
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.url = "https://www.apexsolarsystems.com"
    
    # Mock SSRF guard to bypass validation
    with patch("backend.app.enrichment.website_validator.validate_outbound_url"), \
         patch("httpx.Client.get", return_value=mock_response), \
         patch("socket.create_connection"), \
         patch("ssl.create_default_context"):
        
        # 1. Matching business name token
        res1 = validator.validate("https://www.apexsolarsystems.com", "Apex Solar Systems Ltd")
        assert res1.is_valid is True
        assert res1.domain_token_match is True

        # 2. Non-matching name token
        res2 = validator.validate("https://www.apexsolarsystems.com", "Other Dental Studio")
        assert res2.is_valid is True
        assert res2.domain_token_match is False


def test_completeness_checker(db_session) -> None:
    ws_id = uuid.uuid4()
    lead_id = uuid.uuid4()
    
    # Create a lead missing website and phone
    lead1 = Lead(
        id=lead_id,
        workspace_id=ws_id,
        business_name="Test Business",
        website=None,
        phone=None,
        email="info@test.com",
    )
    db_session.add(lead1)
    db_session.commit()
    
    checker = CompletenessChecker(required_fields=["business_name", "website", "phone"])
    # Should be incomplete
    assert checker.check_completeness(lead1, db_session) is False

    # Update lead with website and phone
    lead1.website = "https://www.test.com"
    lead1.phone = "+1234567890"
    db_session.commit()

    # Still incomplete because we lack high-confidence evidence records
    assert checker.check_completeness(lead1, db_session) is False

    # Add verified high-confidence EvidenceRecords
    ev_web = EvidenceRecord(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        lead_id=lead1.id,
        field_name="website",
        status="VERIFIED",
        confidence_score=85,
        source="manual",
    )
    ev_phone = EvidenceRecord(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        lead_id=lead1.id,
        field_name="phone",
        status="VERIFIED",
        confidence_score=90,
        source="manual",
    )
    db_session.add(ev_web)
    db_session.add(ev_phone)
    db_session.commit()

    # Now it should pass completeness check!
    assert checker.check_completeness(lead1, db_session) is True
