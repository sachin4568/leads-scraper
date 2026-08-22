from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.models import Base as Base1, Lead, ScrapeJob, Workspace
from backend.app.models_phase2 import Base as Base2, CanonicalLead
from backend.app.models_phase3 import Base as Base3
from backend.app.models_services import Base as BaseServices
from backend.app.sources.base import NormalizedLeadRecord, SourceConnector
from backend.app.worker import process_scrape_job_task


class ContaminationTestConnector(SourceConnector):
    @property
    def source_name(self) -> str:
        return "contamination_source"

    def search_leads(
        self, query: str, location: str | None = None, limit: int = 100, page: int = 1
    ) -> list[NormalizedLeadRecord]:
        if page > 1:
            return []
        return [
            NormalizedLeadRecord(
                source=self.source_name,
                source_id="alpha_001",
                business_name="Alpha Dental Clinic",
                website="https://www.alphadental.com",
                phone="+1 555 111 1111",
                address="111 Alpha St",
                category="Dental Clinic",
            ),
            NormalizedLeadRecord(
                source=self.source_name,
                source_id="beta_002",
                business_name="Beta Dental Practice",
                website="https://www.betadental.com",
                phone="+1 555 222 2222",
                address="222 Beta St",
                category="Dental Clinic",
            ),
        ]

    def health_check(self) -> bool:
        return True


def test_zero_field_cross_contamination(monkeypatch, tmp_path):
    db_path = tmp_path / "test_contamination.db"
    engine = create_engine(f"sqlite:///{db_path}")
    TestingSessionLocal = sessionmaker(bind=engine)
    Base1.metadata.create_all(bind=engine)
    Base2.metadata.create_all(bind=engine)
    Base3.metadata.create_all(bind=engine)
    BaseServices.metadata.create_all(bind=engine)

    import backend.app.database
    monkeypatch.setattr(backend.app.database, "SessionLocal", TestingSessionLocal)

    with TestingSessionLocal() as session:
        ws = Workspace(name="Contamination Test WS")
        session.add(ws)
        session.commit()

        job = ScrapeJob(
            workspace_id=ws.id,
            niche="Dental Clinics",
            country="United States",
            region="California",
            target_lead_count=10,
            sources=["contamination_source"],
            status="PENDING",
        )
        session.add(job)
        session.commit()
        job_id_str = str(job.id)

    mock_conn = ContaminationTestConnector()
    connectors_map = {"contamination_source": mock_conn}

    with patch("backend.app.worker_concurrency.workspace_concurrency_guard") as mock_guard, \
         patch("backend.app.websockets.publish_job_progress"), \
         patch("backend.app.worker.get_connectors", return_value=connectors_map):
        mock_guard.return_value.__enter__.return_value = None

        process_scrape_job_task.component = None
        process_scrape_job_task(job_id_str)

    with TestingSessionLocal() as session:
        leads = list(session.scalars(select(CanonicalLead)).all())
        assert len(leads) == 2

        alpha = next(l for l in leads if "Alpha" in l.business_name)
        beta = next(l for l in leads if "Beta" in l.business_name)

        assert "alphadental.com" in alpha.canonical_domain
        assert alpha.canonical_phone == "+1 555 111 1111"
        assert "111 Alpha St" in (alpha.address or "")

        assert "betadental.com" in beta.canonical_domain
        assert beta.canonical_phone == "+1 555 222 2222"
        assert "222 Beta St" in (beta.address or "")

        assert alpha.canonical_phone != beta.canonical_phone
        assert alpha.canonical_domain != beta.canonical_domain
