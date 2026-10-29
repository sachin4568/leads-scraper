import uuid
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import select

from backend.app.database import SessionLocal
from backend.app.models import Workspace, ScrapeJob, Lead
from backend.app.sources.base import NormalizedLeadRecord
from backend.app.orchestration.discovery_orchestrator import DiscoveryOrchestrator
from backend.app.enrichment.email_verifier import EmailVerifier, EmailVerificationResult
from backend.app.enrichment.website_enricher import ProductionWebsiteEnricher
from backend.app.intelligence.quality_gate import QualityGateEngine, QualityGateDecision
from backend.app.intelligence.query_expansion import QueryExpansionEngine


# ─────────────────────────────────────────────────────────────────────────────
# 1. Tests for Change 1: Target Completion & Dynamic Expansion (No 20% Stop)
# ─────────────────────────────────────────────────────────────────────────────

def test_initial_action_queue_does_not_pre_mark_queries_as_executed():
    """Verifies that _build_initial_action_queue does NOT pre-mark queries as executed,
    allowing _enqueue_expanded_actions to dynamically refill the action queue."""
    orchestrator = DiscoveryOrchestrator(
        job_id=uuid.uuid4(),
        connectors={"google_maps": MagicMock(), "osm_overpass": MagicMock()},
        job=MagicMock(
            id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            niche="Plumbers",
            country="United Kingdom",
            region="London",
            state="London",
            target_lead_count=10,
            status="PENDING",
            enrichments=[],
            sources=["google_maps", "osm_overpass"],
            service=None,
            leads_scraped=0,
            progress_percent=0.0,
            discovered_count=0,
            valid_count=0,
            error_message=None,
        ),
    )

    orchestrator._build_initial_action_queue()
    initial_queue_len = len(orchestrator.action_queue)
    assert initial_queue_len > 0

    # Ensure none were pre-marked in _executed_query_pages before running
    assert len(orchestrator._executed_query_pages) == 0

    # Simulate actions running out
    orchestrator.action_queue.clear()

    # Now verify that _enqueue_expanded_actions successfully enqueues expanded queries
    added = orchestrator._enqueue_expanded_actions()
    assert added > 0
    assert len(orchestrator.action_queue) > 0


def test_query_expansion_engine_generates_broad_modifiers_and_location():
    """Verifies QueryExpansionEngine generates diverse business and location angles."""
    engine = QueryExpansionEngine()
    queries = engine.expand_query("electrician", location="Manchester", max_queries=30)
    
    query_texts = [q["query"].lower() for q in queries]
    
    # Must contain exact and variations
    assert "electrician" in query_texts
    assert any("electricians" in q for q in query_texts)
    # Must contain service terminology
    assert any("rewiring" in q or "contractor" in q or "commercial" in q for q in query_texts)
    # Must contain location angles
    assert any("manchester" in q for q in query_texts)
    assert len(queries) >= 15


def test_orchestrator_backfills_and_completes_target_without_stopping_early():
    """Verifies that when only 25% of candidates have verified emails,
    the orchestrator dynamically expands queries and backfills until the full
    target (e.g. N = 4) is completed, instead of stopping after the first batch."""
    with SessionLocal() as db:
        ws = Workspace(name=f"Target Completion WS {uuid.uuid4().hex[:4]}")
        db.add(ws)
        db.commit()

        job = ScrapeJob(
            workspace_id=ws.id,
            niche="Electricians",
            country="Canada",
            region="Ontario",
            state="Toronto",
            target_lead_count=4,  # Target N = 4
            status="PENDING",
            sources=["google_maps"],
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Generate stream of candidates: only 1 in 3 has a valid email (33% email yield)
        candidate_counter = 0

        def mock_search_leads(query=None, location=None, limit=50, page=1, **kwargs):
            nonlocal candidate_counter
            results = []
            for i in range(3):
                candidate_counter += 1
                c_id = f"c_{candidate_counter}_{uuid.uuid4().hex[:4]}"
                # 1 of every 3 candidates has an email
                has_email = (candidate_counter % 3 == 1)
                em = f"contact@{c_id}.ca" if has_email else None
                results.append(
                    NormalizedLeadRecord(
                        source="google_maps",
                        source_id=c_id,
                        business_name=f"Toronto Spark Electric {candidate_counter} {uuid.uuid4().hex[:4]}",
                        category="Electrician",
                        phone=f"+1416555{uuid.uuid4().hex[:4]}",
                        website=f"https://sparkelectric_{c_id}.ca",
                        email=em,
                        address="Toronto, ON, Canada",
                        raw_data={"types": ["electrician"]},
                    )
                )
            return results

        mock_conn = MagicMock()
        mock_conn.supports_category.return_value = True
        mock_conn.search_leads.side_effect = mock_search_leads

        orchestrator = DiscoveryOrchestrator(
            db=db,
            job=job,
            connectors={"google_maps": mock_conn},
            max_request_budget=50,
        )

        with patch(
            "backend.app.orchestration.discovery_orchestrator.EmailVerifier.verify",
            side_effect=lambda email, **kwargs: EmailVerificationResult(is_valid=True, email=email),
        ):
            orchestrator.run_discovery()

        db.refresh(job)
        # MUST complete full target of 4 leads, not stop at 1 lead (25%)!
        assert job.status == "COMPLETED"
        assert job.completion_reason == "TARGET_REACHED"
        assert job.leads_scraped >= 4
        assert orchestrator.metrics.saved_count >= 4


# ─────────────────────────────────────────────────────────────────────────────
# 2. Tests for Change 2: Complete Elimination of Invalid & Synthetic Emails
# ─────────────────────────────────────────────────────────────────────────────

def test_email_verifier_strictly_rejects_numeric_tlds_and_versions():
    """Verifies that numeric TLDs, software package versions, and syntax corruption
    (e.g. 1234r5-234@328380, intl-segmenter@11.7.10) are strictly rejected."""
    bad_emails = [
        "1234r5-234@328380",            # No dot, purely numeric domain
        "intl-segmenter@11.7.10",        # NPM package version in script tags
        "leaflet@1.7.1",                 # Library version
        "bootstrap@5.1.3",               # Library version
        "peak@2.8",                      # Numeric version
        "2022-01-22@13.00.50",           # Timestamp formatted as email
        "13@15.01.45",                   # Numeric time
        "user@192.168.1.1",              # Pure IP address domain
        "item@328380.23",                # Numeric TLD (.23)
        "test@something.400",            # Numeric TLD (.400)
    ]
    for em in bad_emails:
        assert EmailVerifier.is_placeholder_email(em) is True, f"Failed to reject: {em}"
        v_res = EmailVerifier().verify(em)
        assert v_res.is_valid is False, f"Verify passed invalid email: {em}"


def test_email_verifier_strictly_rejects_template_and_dummy_emails():
    """Verifies that placeholder and dummy emails (name@mail.com, you@company.com, etc.)
    are rejected outright."""
    placeholders = [
        "name@mail.com",
        "user@gmail.com",
        "someone@yahoo.com",
        "test@hotmail.com",
        "dummy@outlook.com",
        "filler@godaddy.com",
        "your@email.com",
        "you@company.com",
        "example@email.com",
        "franchise@ijt.8c5.myftpupload.com",
        "email@findhvac.us",
        "someone@example.com",
        "admin@domain.com",
    ]
    for em in placeholders:
        assert EmailVerifier.is_placeholder_email(em) is True, f"Failed to reject placeholder: {em}"


def test_website_enricher_filters_script_tags_and_numeric_tlds():
    """Verifies that ProductionWebsiteEnricher._extract_contacts_from_html strips
    script/code tags and ignores software versions like intl-segmenter@11.7.10."""
    html = """
    <html>
        <head>
            <script src="https://cdn.jsdelivr.net/npm/intl-segmenter@11.7.10/dist/index.js"></script>
            <script>
                var build = "webpack@5.4.1";
                var debugId = "1234r5-234@328380";
            </script>
            <style>
                .icon { background: url('asset@2x.png'); }
            </style>
        </head>
        <body>
            <code>ref_hash: git-commit@88.99.1</code>
            <a href="mailto:name@mail.com">Fake Placeholder</a>
            <p>For plumbing inquiries, contact our master technician:
               <a href="mailto:director@realbusinessplumbing.co.uk">director@realbusinessplumbing.co.uk</a>
            </p>
        </body>
    </html>
    """
    enricher = ProductionWebsiteEnricher(max_pages=1)
    contacts = enricher._extract_contacts_from_html(html, page_url="https://realbusinessplumbing.co.uk")
    extracted_emails = [e["email"] for e in contacts.emails]

    # Must extract the genuine email
    assert "director@realbusinessplumbing.co.uk" in extracted_emails
    # Must NOT extract script versions or placeholders
    assert "intl-segmenter@11.7.10" not in extracted_emails
    assert "1234r5-234@328380" not in extracted_emails
    assert "name@mail.com" not in extracted_emails
    assert "webpack@5.4.1" not in extracted_emails
    assert len(extracted_emails) == 1


def test_quality_gate_validates_email_hygiene():
    """Verifies that QualityGateEngine strictly approves real emails and rejects
    numeric TLDs and placeholders."""
    # Bad emails
    is_ok_1, _ = QualityGateEngine.validate_email("1234r5-234@328380")
    assert is_ok_1 is False

    is_ok_2, _ = QualityGateEngine.validate_email("name@mail.com")
    assert is_ok_2 is False

    is_ok_3, _ = QualityGateEngine.validate_email("intl-segmenter@11.7.10")
    assert is_ok_3 is False

    # Good email
    is_ok_good, val = QualityGateEngine.validate_email("owner@torontoplumbers.ca")
    assert is_ok_good is True
    assert val == "owner@torontoplumbers.ca"

    # Evaluation candidate test
    res = QualityGateEngine.evaluate_candidate(
        business_name="Toronto Plumbers",
        phone=None,
        email="owner@torontoplumbers.ca",
        website="https://torontoplumbers.ca",
        address="Toronto, ON",
        category="Plumber",
        target_niche="Plumbers",
        require_verified_email=True,
    )
    assert res.decision == QualityGateDecision.ACCEPT
