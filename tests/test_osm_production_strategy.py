import pytest
from unittest.mock import patch, MagicMock
from backend.app.sources.osm_overpass import OSMOverpassConnector, OSMOverpassProviderError
from backend.app.worker import finalize_job_status
from backend.app.models import ScrapeJob, Lead


class MockSession:
    def __init__(self):
        self.refreshed = False
        self.committed = False
        self.leads = []
    
    def refresh(self, obj):
        self.refreshed = True

    def commit(self):
        self.committed = True

    def query(self, model):
        session = self
        class QueryMock:
            def filter(self, *args, **kwargs):
                return self
            def all(self):
                return []
            def count(self):
                return len(session.leads)
        return QueryMock()


def test_single_bbox_is_default_strategy():
    connector = OSMOverpassConnector()
    
    with patch("backend.app.sources.geo_utils.SubdivisionManager.geocode_location") as mock_geo, \
         patch("backend.app.sources.geo_utils.SubdivisionManager.subdivide_location") as mock_subdivide, \
         patch.object(connector, "_execute_query") as mock_exec:
        
        mock_geo.return_value = [19.15, 19.17, 72.84, 72.86]
        mock_exec.return_value = {
            "elements": [
                {
                    "type": "node",
                    "id": 101,
                    "lat": 19.16,
                    "lon": 72.85,
                    "tags": {"name": "Test Restaurant", "amenity": "restaurant"}
                }
            ]
        }
        
        pag_state = {}
        results = connector.search_leads(
            query="restaurant",
            location="Goregaon, Mumbai, India",
            pagination_state=pag_state
        )
        
        # Geocode is called for single-BBox
        mock_geo.assert_called_once_with("Goregaon, Mumbai, India")
        # Subdivide is NOT called for ordinary search
        mock_subdivide.assert_not_called()
        # Only 1 request sent
        assert len(results) == 1
        assert results[0].business_name == "Test Restaurant"
        assert pag_state.get("has_more") is False


def test_zero_result_200_does_not_trigger_subdivision_fallback():
    connector = OSMOverpassConnector()
    
    with patch("backend.app.sources.geo_utils.SubdivisionManager.geocode_location") as mock_geo, \
         patch("backend.app.sources.geo_utils.SubdivisionManager.subdivide_location") as mock_subdivide, \
         patch.object(connector, "_execute_query") as mock_exec:
        
        mock_geo.return_value = [19.15, 19.17, 72.84, 72.86]
        # HTTP 200 with empty elements list
        mock_exec.return_value = {"elements": []}
        
        pag_state = {}
        results = connector.search_leads(
            query="restaurant",
            location="Goregaon, Mumbai, India",
            pagination_state=pag_state
        )
        
        # Returns empty list as legitimate 0 results
        assert results == []
        # Does NOT trigger fallback subdivision
        mock_subdivide.assert_not_called()
        assert pag_state.get("has_more") is False


def test_subdivision_fallback_when_explicitly_requested():
    connector = OSMOverpassConnector()
    
    with patch("backend.app.sources.geo_utils.SubdivisionManager.geocode_location") as mock_geo, \
         patch("backend.app.sources.geo_utils.SubdivisionManager.subdivide_location") as mock_subdivide, \
         patch.object(connector, "_execute_query") as mock_exec:
        
        mock_geo.return_value = [19.15, 19.17, 72.84, 72.86]
        mock_subdivide.return_value = [
            {"bbox": [19.15, 19.16, 72.84, 72.85]},
            {"bbox": [19.16, 19.17, 72.85, 72.86]},
        ]
        mock_exec.return_value = {
            "elements": [
                {
                    "type": "node",
                    "id": 102,
                    "lat": 19.155,
                    "lon": 72.845,
                    "tags": {"name": "Cell Lead", "amenity": "restaurant"}
                }
            ]
        }
        
        pag_state = {"subdivision_fallback": True}
        results = connector.search_leads(
            query="restaurant",
            location="Goregaon, Mumbai, India",
            page=1,
            pagination_state=pag_state
        )
        
        mock_subdivide.assert_called_once_with("Goregaon, Mumbai, India", subdivisions=9)
        assert len(results) == 1
        assert pag_state.get("has_more") is not False


def test_completion_semantics_target_reached():
    job = MagicMock()
    job.id = "00000000-0000-0000-0000-000000000001"
    job.workspace_id = "00000000-0000-0000-0000-000000000002"
    job.target_lead_count = 10
    job.leads_scraped = 10
    job.status = "RUNNING"
    job.discovered_count = 10
    job.valid_count = 10
    job.new_count = 10
    job.updated_count = 0
    job.duplicate_count = 0
    job.failed_count = 0

    db = MockSession()
    
    with patch("backend.app.worker_concurrency._global_limiter._redis_client", None), \
         patch("backend.app.websockets.publish_job_progress"):
        finalize_job_status(db, job, str(job.id))
        
    assert job.status == "COMPLETED"
    assert job.completion_reason == "TARGET_REACHED"


def test_completion_semantics_region_exhausted():
    job = MagicMock()
    job.id = "00000000-0000-0000-0000-000000000001"
    job.workspace_id = "00000000-0000-0000-0000-000000000002"
    job.target_lead_count = 25
    job.leads_scraped = 6
    job.status = "RUNNING"
    job.discovered_count = 6
    job.valid_count = 6
    job.new_count = 6
    job.updated_count = 0
    job.duplicate_count = 0
    job.failed_count = 0

    db = MockSession()
    
    with patch("backend.app.worker_concurrency._global_limiter._redis_client", None), \
         patch("backend.app.websockets.publish_job_progress"):
        finalize_job_status(db, job, str(job.id))
        
    assert job.status == "PARTIAL"
    assert job.completion_reason == "DISCOVERY_EXHAUSTED"


def test_completion_semantics_partial_provider_failure():
    job = MagicMock()
    job.id = "00000000-0000-0000-0000-000000000001"
    job.workspace_id = "00000000-0000-0000-0000-000000000002"
    job.target_lead_count = 25
    job.leads_scraped = 6
    job.status = "RUNNING"
    job.discovered_count = 6
    job.valid_count = 6
    job.new_count = 6
    job.updated_count = 0
    job.duplicate_count = 0
    job.failed_count = 1

    db = MockSession()
    mock_redis = MagicMock()
    mock_redis.smembers.side_effect = lambda k: {b"osm_overpass"} if "failed" in k else set()
    
    with patch("backend.app.worker_concurrency._global_limiter._redis_client", mock_redis), \
         patch("backend.app.websockets.publish_job_progress"):
        finalize_job_status(db, job, str(job.id))
        
    assert job.status == "PARTIAL"
    assert job.completion_reason == "PARTIAL_SOURCE_FAILURE"


def test_completion_semantics_complete_provider_failure():
    job = MagicMock()
    job.id = "00000000-0000-0000-0000-000000000001"
    job.workspace_id = "00000000-0000-0000-0000-000000000002"
    job.target_lead_count = 25
    job.leads_scraped = 0
    job.status = "RUNNING"
    job.discovered_count = 0
    job.valid_count = 0
    job.new_count = 0
    job.updated_count = 0
    job.duplicate_count = 0
    job.failed_count = 1

    db = MockSession()
    mock_redis = MagicMock()
    mock_redis.smembers.side_effect = lambda k: {b"osm_overpass"} if "failed" in k else set()
    
    with patch("backend.app.worker_concurrency._global_limiter._redis_client", mock_redis), \
         patch("backend.app.websockets.publish_job_progress"):
        finalize_job_status(db, job, str(job.id))
        
    assert job.status == "FAILED"
    assert job.completion_reason == "ALL_SOURCES_FAILED"
