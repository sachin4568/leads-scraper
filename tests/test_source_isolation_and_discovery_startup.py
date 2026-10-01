import uuid
import pytest
from unittest.mock import MagicMock, patch

from backend.app.database import Base, SessionLocal, engine
from backend.app.models import Workspace, ScrapeJob
from backend.app.sources.base import NormalizedLeadRecord
from backend.app.sources.google_maps import GoogleMapsConnector
from backend.app.sources.osm_overpass import OSMOverpassConnector
from backend.app.orchestration.discovery_orchestrator import DiscoveryOrchestrator


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield


from sqlalchemy import select

def test_google_maps_is_configured():
    """Verifies that GoogleMapsConnector correctly detects whether api_key is present."""
    connector_empty_key = GoogleMapsConnector(api_key="")
    assert connector_empty_key.is_configured() is False

    connector_valid_key = GoogleMapsConnector(api_key="AIzaSyTestKey123")
    assert connector_valid_key.is_configured() is True


def test_osm_overpass_plural_canonical_category():
    """Verifies that OSMOverpassConnector resolves plural and singular categories correctly."""
    connector = OSMOverpassConnector()
    assert connector.get_canonical_category("Electrician") == "craft=electrician"
    assert connector.get_canonical_category("Electricians") == "craft=electrician"
    assert connector.get_canonical_category("Plumbers") == "craft=plumber"
    assert connector.get_canonical_category("Painters") == "craft=painter"


def test_source_isolation_unconfigured_provider_skipped_in_action_queue():
    """Verifies that unconfigured providers (e.g. Google Maps with no API key) are skipped
    during action queue construction, allowing healthy providers to proceed unhindered.
    """
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).limit(1))
        if not ws:
            ws = Workspace(name="Isolation Test Workspace")
            db.add(ws)
            db.commit()
            db.refresh(ws)

        job = ScrapeJob(
            workspace_id=ws.id,
            niche="Electricians",
            country="United Kingdom",
            region="West Yorkshire",
            state="Leeds",
            target_lead_count=25,
            sources=["google_maps", "osm_overpass"],
            enrichments={"locations": ["Leeds", "Liverpool", "London"]},
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Mock connectors: Google Maps has no key (is_configured=False), OSM is healthy
        gmaps_mock = GoogleMapsConnector(api_key="")
        osm_mock = OSMOverpassConnector()

        connectors = {
            "google_maps": gmaps_mock,
            "osm_overpass": osm_mock,
        }

        orchestrator = DiscoveryOrchestrator(
            db=db,
            job=job,
            connectors=connectors,
            max_request_budget=30,
        )

        # Build action queue
        orchestrator._build_initial_action_queue()

        # Google Maps should NOT have any actions in the queue since it's unconfigured
        gmaps_actions = [a for a in orchestrator.action_queue if a.provider == "google_maps"]
        assert len(gmaps_actions) == 0, "Unconfigured google_maps actions should be excluded from queue"

        # OSM Overpass actions should be queued across all 3 locations (Leeds, Liverpool, London)
        osm_actions = [a for a in orchestrator.action_queue if a.provider == "osm_overpass"]
        assert len(osm_actions) > 0, "OSM actions should be queued"

        locations_queued = {a.location for a in osm_actions}
        assert "Leeds" in locations_queued
        assert "Liverpool" in locations_queued
        assert "London" in locations_queued


def test_runtime_source_eviction_when_provider_fails_credentials():
    """Verifies that if a provider encounters missing/invalid credentials at runtime,
    all remaining actions for that provider are immediately evicted from the queue.
    """
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).limit(1))
        if not ws:
            ws = Workspace(name="Eviction Test Workspace")
            db.add(ws)
            db.commit()
            db.refresh(ws)

        job = ScrapeJob(
            workspace_id=ws.id,
            niche="Electricians",
            country="United Kingdom",
            region="England",
            state="Leeds",
            target_lead_count=25,
            sources=["google_maps", "osm_overpass"],
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Mock connectors: Google Maps will throw CREDENTIAL_MISSING at runtime
        mock_gmaps = MagicMock()
        mock_gmaps.is_configured.return_value = True
        mock_gmaps.search_leads.side_effect = ValueError("CREDENTIAL_MISSING")

        # Mock OSM to return a viable lead
        mock_osm = MagicMock()
        mock_osm.search_leads.return_value = [
            NormalizedLeadRecord(
                source="osm_overpass",
                source_id="osm_1",
                business_name="Leeds Expert Electricians Ltd",
                website="https://leedselectricians.co.uk",
                phone="+44 113 222 3344",
                address="10 Commercial St, Leeds, UK",
                category="craft=electrician",
            )
        ]

        connectors = {
            "google_maps": mock_gmaps,
            "osm_overpass": mock_osm,
        }

        orchestrator = DiscoveryOrchestrator(
            db=db,
            job=job,
            connectors=connectors,
            max_request_budget=30,
        )

        viable_candidates = orchestrator.stage_1_discover_viable_candidates()

        # Google Maps failed, but was isolated; OSM succeeded and produced viable candidates
        assert len(viable_candidates) > 0
        assert viable_candidates[0].business_name == "Leeds Expert Electricians Ltd"
        assert orchestrator.metrics.provider_health["google_maps"]["status"] == "UNAVAILABLE_NO_CREDENTIALS"
