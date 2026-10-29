from __future__ import annotations

import logging
import inspect
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

# Phone number pattern — used to detect phone numbers stored in the email column
_PHONE_IN_EMAIL_PATTERN = re.compile(r"^\(?\d{3}\)?[\s\-]\d{3}[\s\-]\d{4}$")

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from backend.app import database


def SessionLocal():
    session = database.SessionLocal()
    session.expire_on_commit = False
    return session

from backend.app.enrichment.website_discovery import (
    DiscoveryProvenance,
    VerificationDecision,
    ZeroBudgetDiscoveryEngine,
)
from backend.app.enrichment.website_enricher import (
    DECISION_MAKER_PREFIXES,
    GENERIC_EMAIL_PREFIXES,
    ProductionWebsiteEnricher,
)
from backend.app.ingestion.canonical_location import CanonicalLocation, LocationValidationResult, LocationValidator
from backend.app.ingestion.identity import normalize_business_name, normalize_domain, normalize_phone
from backend.app.ingestion.ingestion import RawLead
from backend.app.ingestion.lifecycle import LifecycleResolver, LifecycleState
from backend.app.ingestion.location_normalizer import LocationNormalizer, is_location_relevant
from backend.app.intelligence.adaptive_discovery import AdaptiveDiscoveryEngine
from backend.app.intelligence.lead_intelligence import LeadIntelligenceEngine
from backend.app.intelligence.niche_relevance import NicheRelevanceGate, parse_selected_niches
from backend.app.intelligence.quality_gate import QualityGateDecision, QualityGateEngine
from backend.app.intelligence.query_expansion import QueryExpansionEngine
from backend.app.models import EvidenceRecord, Lead, ScrapeJob, ScrapeJobExecutionLog, SourceRecord
from backend.app.models_phase2 import LeadObservation
from backend.app.sources.base import NormalizedLeadRecord, SourceConnector
from backend.app.sources.geo_utils import SubdivisionManager
from backend.app.verification import (
    OverallVerificationResult,
    VerificationAndEvidenceEngine,
    VerificationStatus,
)
from backend.app.intelligence.genuineness import GenuinenessAgent
from backend.app.enrichment.email_verifier import EmailVerifier
from backend.app.websockets import publish_job_progress
from backend.app.worker_concurrency import _global_limiter

logger = logging.getLogger(__name__)


def _is_phone_field(key: object) -> bool:
    normalized_key = re.sub(r"[^a-z0-9]", "", str(key).lower())
    return normalized_key == "tel" or any(
        field in normalized_key for field in ("phone", "telephone", "mobile", "fax")
    )


def _remove_phone_data(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _remove_phone_data(item)
            for key, item in value.items()
            if not _is_phone_field(key)
        }
    if isinstance(value, list):
        return [_remove_phone_data(item) for item in value]
    return value


@dataclass
class DiscoveryAction:
    """Represents a discrete discovery action to execute against a provider."""

    provider: str
    query: str
    query_reason: str
    location: str | None
    page: int = 1
    pagination_state: dict[str, Any] = field(default_factory=dict)
    priority: int = 1
    geo_bbox: list[float] | None = None
    historical_score: float = 1.0
    retry_count: int = 0


@dataclass
class OrchestratorMetrics:
    """Tracks execution yield, request counts, and lead segregation."""

    requested: int = 100
    fetched_count: int = 0
    unique_count: int = 0
    saved_count: int = 0
    duplicate_count: int = 0
    validated_count: int = 0
    qualified_count: int = 0
    rejected_count: int = 0
    failed_count: int = 0
    requests_executed: int = 0
    max_requests: int = 50
    researched_count: int = 0
    emails_extracted_count: int = 0
    source_backed_count: int = 0
    decision_maker_count: int = 0
    named_professional_count: int = 0
    generic_count: int = 0
    emails_rejected_count: int = 0
    timeouts_count: int = 0
    retries_count: int = 0
    batch_failures: int = 0
    start_time: float = 0.0
    elapsed_time: float = 0.0
    qualified_yield: float = 0.0
    sources_attempted: set[str] = field(default_factory=set)
    sources_failed: set[str] = field(default_factory=set)
    sources_succeeded: set[str] = field(default_factory=set)
    provider_health: dict[str, dict[str, Any]] = field(default_factory=dict)


def is_viable_candidate(rec: Any) -> bool:
    """Minimum Viability Gate (Candidate Pre-Filter):
    A discovered candidate is viable only if:
    1. It has a non-empty, non-generic business name.
    2. It has an actionable digital signal to discover or verify an email:
       - Website URL
       - Email address
       - Raw tags containing website or email data
    Candidates lacking both website and email cannot yield a verified email and are eliminated immediately.
    Phone numbers are not accepted or used in this pipeline.
    """
    if not rec:
        return False
    b_name = getattr(rec, "business_name", None)
    if not b_name or not str(b_name).strip():
        return False
    if str(b_name).strip().lower() in ("unknown business", "unknown", "n/a", "none"):
        return False

    website = getattr(rec, "website", None)
    email = getattr(rec, "email", None)
    raw_data = getattr(rec, "raw_data", None)

    has_website = bool(website and str(website).strip())
    has_email = bool(email and str(email).strip())

    has_raw_signal = False
    if isinstance(raw_data, dict):
        tags = raw_data.get("tags") or raw_data.get("properties") or {}
        if isinstance(tags, dict):
            if any(tags.get(k) for k in (
                "contact:website", "website", 
                "contact:email", "email"
            )):
                has_raw_signal = True

    return has_website or has_email or has_raw_signal


class DiscoveryOrchestrator:
    """Central dynamic orchestrator managing multi-source discovery, target enforcement,
    progressive field-aware contact enrichment, and fault-tolerant degradation.
    """

    def __init__(
        self,
        job_id: str | uuid.UUID | None = None,
        connectors: dict[str, SourceConnector] | None = None,
        max_request_budget: int = 60,
        db: Any = None,
        job: Any = None,
        require_verified_email: bool | None = None,
        **kwargs: Any,
    ) -> None:
        import uuid
        if job_id is None and job is not None:
            job_id = getattr(job, "id", None)
        if job_id is None:
            raise ValueError("DiscoveryOrchestrator requires job_id or job")
        self.job_id = uuid.UUID(str(job_id))
        self.connectors = connectors or {}

        if job is not None and hasattr(job, "workspace_id"):
            self.job_state = {
                "id": job.id,
                "workspace_id": job.workspace_id,
                "niche": job.niche,
                "target_lead_count": job.target_lead_count,
                "country": job.country,
                "region": job.region,
                "state": job.state,
                "enrichments": job.enrichments,
                "sources": job.sources,
                "service": job.service,
                "leads_scraped": job.leads_scraped or 0,
                "progress_percent": job.progress_percent or 0.0,
                "status": job.status,
                "discovered_count": job.discovered_count or 0,
                "valid_count": job.valid_count or 0,
                "error_message": job.error_message,
            }
        else:
            with SessionLocal() as db_session:
                from backend.app.models import ScrapeJob
                j_obj = db_session.scalar(select(ScrapeJob).where(ScrapeJob.id == self.job_id))
                if not j_obj:
                    raise ValueError(f"Job {self.job_id} not found")
                self.job_state = {
                    "id": j_obj.id,
                    "workspace_id": j_obj.workspace_id,
                    "niche": j_obj.niche,
                    "target_lead_count": j_obj.target_lead_count,
                    "country": j_obj.country,
                    "region": j_obj.region,
                    "state": j_obj.state,
                    "enrichments": j_obj.enrichments,
                    "sources": j_obj.sources,
                    "service": j_obj.service,
                    "leads_scraped": j_obj.leads_scraped or 0,
                    "progress_percent": j_obj.progress_percent or 0.0,
                    "status": j_obj.status,
                    "discovered_count": j_obj.discovered_count or 0,
                    "valid_count": j_obj.valid_count or 0,
                    "error_message": j_obj.error_message,
                }

        self.redis = _global_limiter._redis_client
        self.resolver = LifecycleResolver()
        self.discovery_engine = ZeroBudgetDiscoveryEngine()
        self.enricher = ProductionWebsiteEnricher()
        self.email_verifier = EmailVerifier()
        self.genuineness_agent = GenuinenessAgent()

        self.require_verified_email = require_verified_email if require_verified_email is not None else True

        target = self.job_state.get('target_lead_count') or 100
        self.max_duration_seconds = float(kwargs.get("max_duration_seconds") or 1200.0)
        self.metrics = OrchestratorMetrics(
            requested=target,
            max_requests=max_request_budget,
        )
        self.seen_observation_keys: set[str] = set()
        self._executed_query_pages: set[tuple[str, str, str]] = set()
        self._target_locations: list[str] = []
        self.action_queue: list[DiscoveryAction] = []
        self._initialize_provider_health()

    def _is_job_cancelled(self) -> bool:
        with SessionLocal() as db:
            from backend.app.models import ScrapeJob
            job = db.scalar(select(ScrapeJob).where(ScrapeJob.id == self.job_id))
            if not job:
                return True
            return job.status in ("STOPPED_SAVED", "CANCELLED")

    def _update_job_progress(self, current_source=None, current_query=None, progress_percent=None, leads_scraped=None, status=None, completion_reason=None, error_message=None):
        from backend.app.models import ScrapeJob
        from backend.app.websockets import publish_job_progress
        with SessionLocal() as db:
            job = db.scalar(select(ScrapeJob).where(ScrapeJob.id == self.job_id))
            if not job:
                return
            if current_source: job.current_source = current_source
            if current_query: job.current_query = current_query
            if progress_percent is not None: job.progress_percent = progress_percent
            if leads_scraped is not None: job.leads_scraped = leads_scraped
            if status is not None: job.status = status
            if completion_reason is not None: job.completion_reason = completion_reason
            if error_message is not None: job.error_message = error_message
            
            job.discovered_count = self.metrics.fetched_count
            job.valid_count = self.metrics.validated_count
            job.duplicate_count = self.metrics.duplicate_count
            job.fetched_count = getattr(job, 'fetched_count', 0) + self.metrics.fetched_count
            
            db.commit()
            
            publish_job_progress(
                str(self.job_id),
                {
                    "event_type": f"JOB_{job.status}",
                    "job_id": str(self.job_id),
                    "status": job.status,
                    "leads_scraped": job.leads_scraped,
                    "target_lead_count": self.metrics.requested,
                    "progress_percent": job.progress_percent,
                    "discovered": job.discovered_count,
                    "valid": job.valid_count,
                    "duplicates": job.duplicate_count,
                },
            )

    def _initialize_provider_health(self) -> None:
        for name in self.connectors:
            self.metrics.provider_health[name] = {
                "status": "HEALTHY",
                "consecutive_failures": 0,
                "total_failures": 0,
                "total_successes": 0,
            }

    def _upsert_evidence(
        self,
        field_name: str,
        status: str,
        confidence_score: int,
        source: str,
        details: dict[str, Any] | None,
        lead_id: Any,
        canonical_lead_id: str | None,
    ) -> None:
        with SessionLocal() as db:
            ev = db.scalar(
            select(EvidenceRecord).where(
                EvidenceRecord.lead_id == lead_id,
                EvidenceRecord.field_name == field_name,
            )
        )
        if ev:
            ev.status = status
            ev.confidence_score = confidence_score
            ev.source = source
            ev.details = details
            ev.canonical_lead_id = canonical_lead_id
        else:
            ev = EvidenceRecord(
                workspace_id=self.job_state["workspace_id"],
                lead_id=lead_id,
                canonical_lead_id=canonical_lead_id,
                field_name=field_name,
                status=status,
                confidence_score=confidence_score,
                source=source,
                details=details,
            )
            db.add(ev)
            db.commit()

    def _build_initial_action_queue(self) -> None:
        """Constructs an initial dynamically prioritized action queue across configured sources and locations."""
        # Determine all target locations to query
        target_locations: list[str] = []
        if isinstance(self.job_state["enrichments"], dict) and self.job_state["enrichments"].get("locations"):
            target_locations = [str(loc).strip() for loc in self.job_state["enrichments"]["locations"] if str(loc).strip()]
        elif isinstance(self.job_state["enrichments"], list):
            for item in self.job_state["enrichments"]:
                if isinstance(item, dict) and item.get("locations"):
                    target_locations.extend([str(loc).strip() for loc in item["locations"] if str(loc).strip()])
                elif isinstance(item, str) and item.startswith("loc:"):
                    target_locations.append(item.replace("loc:", "").strip())

        if not target_locations:
            primary_loc = self.job_state["state"] or self.job_state["region"] or self.job_state["country"]
            if primary_loc:
                target_locations = [primary_loc]
        self._target_locations = target_locations

        target_sources = list(self.job_state["sources"] or ["google_maps", "osm_overpass"])
        for c_name in self.connectors.keys():
            if c_name not in target_sources:
                target_sources.append(c_name)
        if "osm_overpass" not in target_sources:
            target_sources.append("osm_overpass")

        actions: list[DiscoveryAction] = []
        for src in target_sources:
            connector = self.connectors.get(src)
            if not connector:
                continue

            # If connector explicitly checks its configuration (e.g. google_maps with no API key)
            if hasattr(connector, "is_configured") and not connector.is_configured():
                logger.info(
                    f"[DiscoveryOrchestrator] Provider '{src}' has no credentials/configuration. Skipping action queue creation for '{src}'."
                )
                self.metrics.provider_health[src]["status"] = "UNAVAILABLE_NO_CREDENTIALS"
                continue

            with SessionLocal() as db:
                src_score = AdaptiveDiscoveryEngine.get_source_score(db, src)

            for loc in target_locations:
                for niche in parse_selected_niches(self.job_state.get("niche")):
                    search_plan = QueryExpansionEngine().expand_query(niche, loc)
                    for item in search_plan:
                        q_term = item["query"]
                        q_reason = item.get("reason", "unknown")

                        # Validate category support if connector supports it
                        if hasattr(connector, "supports_category"):
                            if not connector.supports_category(q_term):
                                continue

                        query_key = (src, loc, q_term.lower())
                        if any(a.provider == src and a.location == loc and a.query.lower() == q_term.lower() for a in actions):
                            continue

                        with SessionLocal() as db:
                            q_score = AdaptiveDiscoveryEngine.get_query_score(db, q_term)
                        reason_lower = q_reason.lower()
                        if "exact" in reason_lower:
                            priority = 1
                        elif "plural" in reason_lower or "singular" in reason_lower:
                            priority = 2
                        elif "synonym" in reason_lower or "service" in reason_lower:
                            priority = 3
                        else:
                            priority = 4

                        actions.append(
                            DiscoveryAction(
                                provider=src,
                                query=q_term,
                                query_reason=q_reason,
                                location=loc,
                                page=1,
                                pagination_state={},
                                priority=priority,
                                historical_score=(src_score * 1.5) + q_score,
                            )
                        )

        # Group actions by provider and interleave round-robin across providers
        provider_actions: dict[str, list[DiscoveryAction]] = {}
        for a in actions:
            provider_actions.setdefault(a.provider, []).append(a)

        for p in provider_actions:
            provider_actions[p].sort(key=lambda a: (a.priority, -a.historical_score))

        interleaved: list[DiscoveryAction] = []
        max_len = max((len(v) for v in provider_actions.values()), default=0)
        for i in range(max_len):
            for p in sorted(provider_actions.keys()):
                if i < len(provider_actions[p]):
                    interleaved.append(provider_actions[p][i])

        self.action_queue = interleaved
        logger.info(
            f"[DiscoveryOrchestrator] Initialized {len(self.action_queue)} discovery actions across {len(target_locations)} location(s) for job {self.job_state["id"]} (Target={self.metrics.requested})"
        )

    def _acquire_lock(self, name: str, phone: str | None, website: str | None) -> str | None:
        if not self.redis:
            return None
        norm_n = normalize_business_name(name)
        norm_p = normalize_phone(phone)
        norm_d = normalize_domain(website)
        sig = f"{norm_n}:{norm_p or norm_d}"
        key = f"lock:lead_ingestion:{sig}"
        for _ in range(30):
            if self.redis.set(key, "locked", ex=10, nx=True):
                return key
            time.sleep(0.05)
        return None

    def _release_lock(self, key: str | None) -> None:
        if self.redis and key:
            try:
                self.redis.delete(key)
            except Exception:
                pass

    def execute_discovery_action(self, action: DiscoveryAction) -> list[NormalizedLeadRecord]:
        """Executes a single provider discovery action with fault tolerance, health tracking, and source isolation."""
        connector = self.connectors.get(action.provider)
        if not connector:
            logger.warning(f"[DiscoveryOrchestrator] Connector '{action.provider}' not available.")
            return []

        p_health = self.metrics.provider_health[action.provider]
        if p_health.get("status") in ("UNAVAILABLE_NO_CREDENTIALS", "UNAVAILABLE"):
            return []

        self.metrics.sources_attempted.add(action.provider)
        self.metrics.requests_executed += 1
        self._executed_query_pages.add((action.provider, action.location, action.query.lower()))

        loc_param = action.location
        if action.provider == "osm_overpass" and action.geo_bbox:
            # geo_bbox is [lat_min, lat_max, lon_min, lon_max]
            # OSM Overpass expects (south, west, north, east) -> (lat_min, lon_min, lat_max, lon_max)
            loc_param = f"{action.geo_bbox[0]},{action.geo_bbox[2]},{action.geo_bbox[1]},{action.geo_bbox[3]}"

        pagination_state = action.pagination_state
        cursor_before = pagination_state.get("next_page_token")
        seen_page_tokens = pagination_state.setdefault("seen_page_tokens", set())
        if cursor_before:
            if cursor_before in seen_page_tokens:
                logger.warning(
                    f"[DiscoveryOrchestrator] Provider '{action.provider}' repeated a pagination cursor; stopping this query."
                )
                return []

        try:
            logger.warning(
                f"[DiscoveryOrchestrator] Executing Action -> Provider='{action.provider}', Query='{action.query}', "
                f"Page={action.page}, Location='{loc_param}'"
            )
            search_kwargs = {
                "query": action.query,
                "location": loc_param,
                "limit": min(50, self.metrics.requested - self.metrics.saved_count),
                "page": action.page,
                "pagination_state": pagination_state,
            }
            parameters = inspect.signature(connector.search_leads).parameters
            legacy_pagination = "pagination_state" not in parameters and not any(
                parameter.kind == inspect.Parameter.VAR_KEYWORD
                for parameter in parameters.values()
            )
            if legacy_pagination:
                search_kwargs.pop("pagination_state")

            failure_count_before = getattr(connector, "failure_count", None)
            records = connector.search_leads(**search_kwargs)
            failure_count_after = getattr(connector, "failure_count", None)
            if (
                not records
                and isinstance(failure_count_before, int)
                and isinstance(failure_count_after, int)
                and failure_count_after > failure_count_before
            ):
                raise RuntimeError("Provider recorded a failed request")
            if cursor_before:
                seen_page_tokens.add(cursor_before)

            # Record success in health tracker
            p_health["status"] = "HEALTHY"
            p_health["consecutive_failures"] = 0
            p_health["total_successes"] += 1
            self.metrics.sources_succeeded.add(action.provider)
            self.metrics.sources_failed.discard(action.provider)

            # Record execution log on success for AdaptiveDiscoveryEngine
            try:
                with SessionLocal() as db_log:
                    exec_log = ScrapeJobExecutionLog(
                        job_id=self.job_state["id"],
                        source=action.provider,
                        query=f"{action.query} ({action.query_reason})",
                        page=action.page,
                        records_received=len(records or []),
                        records_valid=0,
                        records_rejected=0,
                        new_count=0,
                        updated_count=0,
                        duplicate_count=0,
                        failed_count=0,
                    )
                    db_log.add(exec_log)
                    db_log.commit()
            except Exception as log_err:
                logger.debug(f"[DiscoveryOrchestrator] Note logging execution success: {log_err}")

            # Check if provider has next page token or more results
            next_cursor = pagination_state.get("next_page_token")
            has_more = pagination_state.get("has_more", False) or bool(next_cursor) or legacy_pagination
            has_new_cursor = bool(next_cursor) and next_cursor not in seen_page_tokens
            can_advance = has_new_cursor if next_cursor else len(records) > 0
            if (
                has_more
                and can_advance
                and action.page < 10
                and self.metrics.saved_count < self.metrics.requested
            ):
                next_action = DiscoveryAction(
                    provider=action.provider,
                    query=action.query,
                    query_reason=action.query_reason,
                    location=action.location,
                    page=action.page + 1,
                    pagination_state=action.pagination_state,
                    priority=action.priority,
                    geo_bbox=action.geo_bbox,
                    historical_score=action.historical_score + 1.0,  # Reward active yield
                )
                # Push pagination action to the front of the queue
                self.action_queue.insert(0, next_action)

            return records or []

        except Exception as error:
            err_msg = str(error)
            logger.warning(
                f"[DiscoveryOrchestrator] Provider '{action.provider}' failed on query '{action.query}' in '{action.location}': {err_msg}"
            )
            self.metrics.sources_failed.add(action.provider)
            p_health["consecutive_failures"] += 1
            p_health["total_failures"] += 1

            if any(k in err_msg for k in ("CREDENTIAL_MISSING", "INVALID_CREDENTIALS", "REQUEST_DENIED", "API_KEY_INVALID")):
                p_health["status"] = "UNAVAILABLE_NO_CREDENTIALS"
                # Immediately evict all remaining actions for this unconfigured provider
                self.action_queue = [a for a in self.action_queue if a.provider != action.provider]
                logger.info(
                    f"[DiscoveryOrchestrator] Provider '{action.provider}' unconfigured/missing credentials. Evicted remaining actions and switching to other providers."
                )
            else:
                if action.retry_count < 2:
                    self.action_queue.append(
                        DiscoveryAction(
                            provider=action.provider,
                            query=action.query,
                            query_reason=action.query_reason,
                            location=action.location,
                            page=action.page,
                            pagination_state=action.pagination_state,
                            priority=action.priority,
                            geo_bbox=action.geo_bbox,
                            historical_score=action.historical_score,
                            retry_count=action.retry_count + 1,
                        )
                    )
                if p_health["consecutive_failures"] >= 2:
                    p_health["status"] = "DEGRADED"
                    # Demote remaining actions of degraded provider to end of queue
                    degraded_actions = [a for a in self.action_queue if a.provider == action.provider]
                    other_actions = [a for a in self.action_queue if a.provider != action.provider]
                    self.action_queue = other_actions + degraded_actions

            # Log execution log
            exec_log = ScrapeJobExecutionLog(
                job_id=self.job_state["id"],
                source=action.provider,
                query=f"{action.query} ({action.query_reason})",
                page=action.page,
                records_received=0,
                records_valid=0,
                records_rejected=0,
                new_count=0,
                updated_count=0,
                duplicate_count=0,
                failed_count=1,
                error_reason=err_msg,
            )
            with SessionLocal() as db:
                db.add(exec_log)
                db.commit()
            
            return []

    def stage_1_discover_viable_candidates(self, batch_limit: int | None = None) -> list[NormalizedLeadRecord]:
        """Stage 1: Multi-Source Candidate Discovery & Minimum Viability Filtering (Deficit Backfilling).
        Discovers candidate items into a buffer. Any junk leads (no contact signals) are discarded
        immediately without counting toward target N, and discovery continues backfilling until N viable
        candidate leads are secured or sources are exhausted.
        """
        if not self.action_queue:
            self._build_initial_action_queue()
        viable_candidates: list[NormalizedLeadRecord] = []
        target = batch_limit if batch_limit is not None else self.metrics.requested

        # Resolve target canonical location scope
        req_scope_mode = "EXACT_CITY"
        if 'enrichments' in self.job_state and isinstance(self.job_state["enrichments"], dict):
            req_scope_mode = self.job_state["enrichments"].get("location_scope", "EXACT_CITY")
        elif 'enrichments' in self.job_state and isinstance(self.job_state["enrichments"], list):
            for e in self.job_state["enrichments"]:
                if isinstance(e, dict) and "location_scope" in e:
                    req_scope_mode = e["location_scope"]
                    break

        _, _, target_loc_scope = LocationValidator.validate_requested_configuration(
            country=self.job_state["country"],
            region=self.job_state["region"] or self.job_state["state"],
            city=self.job_state["state"] or self.job_state["region"],
            location_scope=req_scope_mode,
        )
        if not target_loc_scope:
            c_norm = LocationValidator.normalize_country(self.job_state["country"])
            target_loc_scope = CanonicalLocation(
                country=c_norm[0] if c_norm else (self.job_state["country"] or "United Kingdom"),
                country_code=c_norm[1] if c_norm else "GB",
                region=self.job_state["region"],
                city=self.job_state["state"] or self.job_state["region"],
                location_scope=req_scope_mode,
            )

        self.job_state["current_source"] = f"Stage 1/4: Discovering viable leads (0/{target})..."
        self.job_state["current_query"] = self.job_state["niche"]
        
        publish_job_progress(
            str(self.job_state["id"]),
            {
                "event_type": "STAGE_1_DISCOVERY_STARTED",
                "job_id": str(self.job_state["id"]),
                "status": self.job_state["status"],
                "leads_scraped": self.metrics.saved_count,
                "target_lead_count": target,
                "progress_percent": 0.0,
                "discovered": self.metrics.fetched_count,
                "valid": self.metrics.validated_count,
                "duplicates": self.metrics.duplicate_count,
            },
        )

        while (
            len(viable_candidates) < target
            and self.metrics.requests_executed < self.metrics.max_requests
        ):
            if self._is_job_cancelled():
                logger.info(f"[DiscoveryOrchestrator] Job {self.job_state['id']} stopped/cancelled during Stage 1.")
                return viable_candidates

            if self.metrics.start_time > 0 and (time.time() - self.metrics.start_time) >= self.max_duration_seconds:
                logger.info("[DiscoveryOrchestrator] SLA time budget reached during Stage 1.")
                break

            if not self.action_queue:
                added = self._enqueue_expanded_actions()
                if added == 0 or not self.action_queue:
                    logger.info("[DiscoveryOrchestrator] No more discovery actions available in Stage 1.")
                    break

            action = self.action_queue.pop(0)

            # Skip providers that are permanently failing if other healthy providers exist
            p_health = self.metrics.provider_health.get(action.provider, {})
            if p_health.get("status") == "DEGRADED" and len(self.action_queue) > 0:
                has_healthy = any(
                    self.metrics.provider_health.get(a.provider, {}).get("status") == "HEALTHY"
                    for a in self.action_queue
                )
                if has_healthy:
                    action.historical_score = 0.1
                    self.action_queue.append(action)
                    continue

            records = self.execute_discovery_action(action)
            self.metrics.fetched_count += len(records)
            self.job_state["discovered_count"] = self.metrics.fetched_count

            for rec in records:
                if len(viable_candidates) >= target:
                    break

                # 1. Minimum Viability Gate: eliminate junk (company name only without contact info)
                if not is_viable_candidate(rec):
                    self.metrics.rejected_count += 1
                    self.metrics.provider_health[action.provider]["total_failures"] += 1
                    continue

                # 2. Niche-Relevance Gate: eliminate unrelated businesses (churches, banks, schools, restaurants)
                niche_decision = NicheRelevanceGate.evaluate_candidate(
                    business_name=rec.business_name,
                    category=rec.category,
                    raw_data=rec.raw_data,
                    target_niche=self.job_state["niche"],
                    query_context=action.query,
                )
                if not niche_decision.is_relevant:
                    logger.info(
                        f"[DiscoveryOrchestrator] Filtered out irrelevant niche: '{rec.business_name}' "
                        f"({niche_decision.matched_reason})"
                    )
                    self.metrics.rejected_count += 1
                    self.metrics.provider_health[action.provider]["total_failures"] += 1
                    continue

                # 3. Location-Relevance Gate: eliminate cross-country/region/city mismatches
                action_scope = target_loc_scope
                if action.location:
                    city_candidate = action.location.split(",")[0].strip()
                    if city_candidate and city_candidate != target_loc_scope.city:
                        _, _, specific_scope = LocationValidator.validate_requested_configuration(
                            country=target_loc_scope.country,
                            region=target_loc_scope.region,
                            city=city_candidate,
                        )
                        if specific_scope:
                            action_scope = specific_scope

                loc_res = LocationValidator.evaluate_candidate(
                    candidate=rec,
                    requested_scope=action_scope,
                )
                provider_location_match = (
                    bool(action.location)
                    and str(action.location).lower() in str(rec.address or "").lower()
                    and not rec.city
                    and not rec.state
                    and not rec.region
                    and not rec.country
                    and rec.latitude is None
                    and rec.longitude is None
                )
                # A provider result returned for the requested location is usable
                # when it has no contradictory location evidence of its own.
                if (
                    not loc_res.is_valid
                    and loc_res.rejection_reason in (
                        "LOCATION_INSUFFICIENT_EVIDENCE",
                        "LOCATION_CITY_MISMATCH",
                    )
                    and action.location
                    and not rec.city
                    and not rec.state
                    and not rec.region
                    and rec.latitude is None
                    and rec.longitude is None
                    and (
                        loc_res.rejection_reason != "LOCATION_COUNTRY_MISMATCH"
                        or str(action.location).lower() in str(rec.address or "").lower()
                    )
                ):
                    loc_res = LocationValidationResult(
                        status="VALID",
                        is_valid=True,
                        country_match=True,
                        region_match=True,
                        city_match=True,
                        confidence=0.5,
                        location_scope=action_scope.location_scope,
                        requested_scope=action_scope.to_dict(),
                        resolved_location=loc_res.resolved_location,
                        evidence=["Provider result was returned for the requested location."],
                    )
                elif provider_location_match:
                    loc_res = LocationValidationResult(
                        status="VALID",
                        is_valid=True,
                        country_match=True,
                        region_match=True,
                        city_match=True,
                        confidence=0.5,
                        location_scope=action_scope.location_scope,
                        requested_scope=action_scope.to_dict(),
                        resolved_location=loc_res.resolved_location,
                        evidence=["Provider address contains the requested location."],
                    )
                if not loc_res.is_valid:
                    reason_str = loc_res.rejection_reason or "LOCATION_MISMATCH"
                    if loc_res.evidence:
                        reason_str += f" ({loc_res.evidence[0]})"
                    logger.info(
                        f"[DiscoveryOrchestrator] Filtered out location mismatch: '{rec.business_name}' "
                        f"({reason_str})"
                    )
                    self.metrics.rejected_count += 1
                    self.metrics.provider_health[action.provider]["total_failures"] += 1
                    continue

                rec_key = rec.get_idempotency_key()
                if rec_key in self.seen_observation_keys:
                    self.metrics.duplicate_count += 1
                    continue
                self.seen_observation_keys.add(rec_key)

                viable_candidates.append(rec)
                self.metrics.unique_count = len(self.seen_observation_keys)
                self.job_state["discovered_count"] = self.metrics.fetched_count
                self.job_state["valid_count"] = self.metrics.validated_count
                self.job_state["leads_scraped"] = self.metrics.saved_count
                self.job_state["current_source"] = f"Stage 1/4: Discovered {len(viable_candidates)} viable candidates"[:64]
                self.job_state["current_query"] = f"{action.query}"[:64]
                self.job_state["progress_percent"] = min(30.0, round((self.metrics.saved_count / max(1, self.metrics.requested)) * 100.0, 1))

                # Persist RawLead and atomically update last_progress_at on the ScrapeJob
                with SessionLocal() as db:
                    import backend.app.models as app_models
                    # Update UI sheet counters
                    raw_sheet = db.get(app_models.RawLeadSheet, self.job_state["id"])
                    if not raw_sheet:
                        from backend.app.models import get_next_raw_sheet_number
                        raw_sheet = app_models.RawLeadSheet(
                            id=self.job_state["id"],
                            workspace_id=self.job_state["workspace_id"],
                            sheet_number=get_next_raw_sheet_number(db),
                            name=f"{self.job_state.get('niche') or 'Leads'} - {self.job_state.get('state') or 'Area'}",
                            niche=self.job_state.get("niche") or "General",
                            country=self.job_state.get("country"),
                            region=self.job_state.get("region"),
                            state=self.job_state.get("state"),
                            target_lead_count=self.metrics.requested,
                            service=self.job_state.get("service"),
                            status="RUNNING",
                            sources=self.job_state.get("sources"),
                            enrichments=self.job_state.get("enrichments"),
                            leads_scraped=len(viable_candidates),
                            discovered_count=self.metrics.fetched_count,
                            valid_count=len(viable_candidates),
                            progress_percent=self.job_state["progress_percent"],
                            current_source=self.job_state["current_source"],
                        )
                        db.add(raw_sheet)
                        db.flush()
                    else:
                        raw_sheet.leads_scraped = len(viable_candidates)
                        raw_sheet.discovered_count = self.metrics.fetched_count
                        raw_sheet.valid_count = len(viable_candidates)
                        raw_sheet.progress_percent = self.job_state["progress_percent"]
                        raw_sheet.current_source = self.job_state["current_source"]

                    # When require_verified_email is active, raw leads are persisted in Stage 4 only after email verification
                    r_lead = None
                    if not self.require_verified_email:
                        existing_raw_lead = db.scalar(
                            select(app_models.RawLead).where(
                                app_models.RawLead.sheet_id == self.job_state["id"],
                                app_models.RawLead.business_name == rec.business_name,
                            )
                        )
                        if not existing_raw_lead:
                            r_lead = app_models.RawLead(
                                id=uuid.uuid4(),
                                sheet_id=self.job_state["id"],
                                lead_number=len(viable_candidates),
                                business_name=rec.business_name,
                                website=rec.website,
                                email=None,
                                phone=None,
                                location=f"{rec.city or ''}, {rec.state or rec.country or ''}".strip(", "),
                                source=rec.source,
                                notes=rec.address,
                                raw_data=_remove_phone_data(rec.raw_data or {}),
                            )
                            db.add(r_lead)
                        # Update progress in DB so the polling endpoint can return live data
                        from sqlalchemy import func
                        job = db.get(app_models.ScrapeJob, self.job_state["id"])
                        if job:
                            job.last_progress_at = func.now()
                            job.progress_percent = self.job_state.get("progress_percent", 0.0)
                            job.leads_scraped = self.metrics.saved_count
                            job.fetched_count = self.metrics.fetched_count
                            job.discovered_count = self.metrics.fetched_count
                            job.valid_count = self.metrics.validated_count
                            job.duplicate_count = self.metrics.duplicate_count
                            job.current_source = self.job_state.get("current_source", "")[:64] if self.job_state.get("current_source") else None
                            job.current_query = self.job_state.get("current_query", "")[:255] if self.job_state.get("current_query") else None
                        # Also update the RawLeadSheet mirror
                        raw_sheet = db.get(app_models.RawLeadSheet, self.job_state["id"])
                        if raw_sheet:
                            raw_sheet.progress_percent = self.job_state.get("progress_percent", 0.0)
                            raw_sheet.leads_scraped = self.metrics.saved_count
                            raw_sheet.fetched_count = self.metrics.fetched_count
                            raw_sheet.discovered_count = self.metrics.fetched_count
                            raw_sheet.valid_count = self.metrics.validated_count
                            raw_sheet.duplicate_count = self.metrics.duplicate_count
                            raw_sheet.current_source = self.job_state.get("current_source", "")[:64] if self.job_state.get("current_source") else None
                    db.commit()
                    try:
                        from backend.app.worker import celery_app
                        if self.job_state.get("service") and r_lead:
                            celery_app.send_task(
                                "backend.app.worker.enrich_raw_lead_task",
                                args=[str(r_lead.id), self.job_state["service"]],
                            )
                    except Exception as e:
                        logger.error(f"Failed to queue enrichment: {e}")

                    

                    publish_job_progress(
                    str(self.job_state["id"]),
                    {
                        "event_type": "STAGE_1_CANDIDATE_DISCOVERED",
                        "job_id": str(self.job_state["id"]),
                        "status": self.job_state["status"],
                        "leads_scraped": len(viable_candidates),
                        "target_lead_count": target,
                        "progress_percent": self.job_state["progress_percent"],
                        "discovered": self.metrics.fetched_count,
                        "valid": len(viable_candidates),
                        "duplicates": self.metrics.duplicate_count,
                    },
                )

        print(f">>> STAGE 1 FINISHED! Gathering {len(viable_candidates)} candidates")
        logger.warning(
            f"[DiscoveryOrchestrator] Stage 1 Completed: Gathered {len(viable_candidates)}/{target} viable candidates "
            f"(Fetched: {self.metrics.fetched_count}, Duplicates: {self.metrics.duplicate_count})"
        )
        return viable_candidates

    def stage_2_enrich_and_verify(self, viable_candidates: list[NormalizedLeadRecord]) -> list[dict[str, Any]]:
        print(f">>> STAGE 2 ENTERED WITH {len(viable_candidates)} candidates")
        """Stage 2: Progressive Contact Signal Enrichment & Verification Engine.
        Executes zero-budget website discovery, website contact enrichment, and comprehensive
        field-level evidence verification.
        """
        verified_results: list[dict[str, Any]] = []
        total = len(viable_candidates)
        target = self.metrics.requested
        enrichment_enabled = bool(self.job_state.get("enrichments"))
        # Email crawling is unconditional — runs whenever a website URL is available,
        # regardless of whether optional enrichment services (scoring, verification) are enabled.
        email_crawl_enabled = True

        self.job_state["current_source"] = f"Stage 2/4: Verifying contact signals (0/{total})..."
        

        for idx, rec in enumerate(viable_candidates):
            if self._is_job_cancelled():
                return verified_results

            self.job_state["current_source"] = f"Stage 2/4: Verifying signals ({idx + 1}/{total})"[:64]
            self.job_state["progress_percent"] = 40.0 + min(30.0, round(((idx + 1) / (total or 1)) * 30.0, 1))
            
            publish_job_progress(
                str(self.job_state["id"]),
                {
                    "event_type": "STAGE_2_VERIFICATION_PROGRESS",
                    "job_id": str(self.job_state["id"]),
                    "status": self.job_state["status"],
                    "leads_scraped": self.job_state["leads_scraped"] or len(viable_candidates),
                    "target_lead_count": target,
                    "progress_percent": self.job_state["progress_percent"],
                    "discovered": self.metrics.fetched_count,
                    "valid": len(verified_results),
                    "duplicates": self.metrics.duplicate_count,
                },
            )

            effective_website = rec.website
            effective_phone = rec.phone
            effective_email = rec.email
            discovered_socials: dict[str, str] = {}
            discovered_whatsapp: list[str] = []
            enr_res = None

            has_phone = bool(effective_phone and str(effective_phone).strip())
            has_email = bool(effective_email and str(effective_email).strip())
            has_website = bool(effective_website and str(effective_website).strip())

            # Step 2a: Zero-Budget Website Discovery if website is missing
            if not has_website:
                try:
                    raw_tags = rec.raw_data.get("tags") if isinstance(rec.raw_data, dict) else {}
                    verif_res = self.discovery_engine.discover_and_verify_official_website(
                        business_name=rec.business_name,
                        phone=rec.phone,
                        email=rec.email,
                        address=rec.address,
                        city=rec.city,
                        raw_data_tags=raw_tags,
                    )
                    if verif_res.decision == VerificationDecision.ACCEPT and verif_res.verified_url:
                        effective_website = verif_res.verified_url
                        has_website = True
                except Exception as disc_err:
                    logger.warning(f"[DiscoveryOrchestrator] Website discovery warning for '{rec.business_name}': {disc_err}")

            # Step 2b: Field-aware contact & social crawling (always crawl website if available)
            if email_crawl_enabled and has_website:
                try:
                    enr_res = self.enricher.enrich_website(
                        target_url=effective_website,
                        provider_phone=rec.phone,
                        provider_email=rec.email,
                        provider_address=rec.address,
                    )
                    if enr_res and enr_res.contacts:
                        if enr_res.contacts.phones and not has_phone:
                            effective_phone = enr_res.contacts.phones[0].get("phone")
                        _email_is_phone = bool(
                            effective_email
                            and _PHONE_IN_EMAIL_PATTERN.match(str(effective_email).strip())
                        )
                        if enr_res.contacts.emails and (not has_email or _email_is_phone or not effective_email):
                            effective_email = enr_res.contacts.emails[0].get("email")
                        discovered_whatsapp = enr_res.contacts.whatsapp_links or []
                    if enr_res and enr_res.social_profiles:
                        discovered_socials = enr_res.social_profiles
                    # Facebook About fallback — only when website crawl found no email
                    if enr_res and not enr_res.contacts.emails:
                        fb_url = discovered_socials.get("facebook") or (
                            rec.raw_data.get("facebook_url") if isinstance(rec.raw_data, dict) else None
                        )
                        if fb_url:
                            try:
                                fb_emails = self.enricher.scrape_facebook_about(fb_url)
                                if fb_emails:
                                    enr_res.contacts.emails = fb_emails
                                    effective_email = fb_emails[0].get("email")
                            except AttributeError:
                                pass
                except Exception as enrich_err:
                    logger.warning(f"[DiscoveryOrchestrator] Enrichment warning for '{rec.business_name}': {enrich_err}")

            # Step 2b-verify: Prioritized Email Selection & Verification (Stage D)
            self.metrics.researched_count += 1
            selected_email_meta = None
            selected_ev_res = None

            if has_website:
                candidates_map: dict[str, dict[str, Any]] = {}
                # 1. Collect emails from enrich_website (already categorized with priority 1, 2, or 3)
                if enr_res and enr_res.contacts and enr_res.contacts.emails:
                    for em_item in enr_res.contacts.emails:
                        em_str = (em_item.get("email") or "").strip()
                        if (
                            em_str
                            and not _PHONE_IN_EMAIL_PATTERN.match(em_str)
                            and not EmailVerifier.is_placeholder_email(em_str)
                        ):
                            prio = em_item.get("priority")
                            if prio is None:
                                c_type = em_item.get("type", "generic")
                                prio = 1 if c_type == "decision_maker" else (2 if c_type == "named_professional" else 3)
                            source_url = em_item.get("source_url") or effective_website
                            candidates_map[em_str.lower()] = {
                                "email": em_str,
                                "type": em_item.get("type", "generic"),
                                "priority": prio,
                                "source_url": source_url,
                                "name": em_item.get("name"),
                                "role": em_item.get("role"),
                                "source_backed": em_item.get(
                                    "source_backed",
                                    bool(source_url and str(source_url).startswith(("http://", "https://"))),
                                ),
                            }

                # 2. Add provider email (rec.email / effective_email) if not already discovered
                if effective_email and not _PHONE_IN_EMAIL_PATTERN.match(str(effective_email).strip()):
                    eff_clean = str(effective_email).strip()
                    if (
                        eff_clean.lower() not in candidates_map
                        and not EmailVerifier.is_placeholder_email(eff_clean)
                    ):
                        local_part = eff_clean.split("@")[0].lower() if "@" in eff_clean else ""
                        if (
                            any(local_part == p or local_part.startswith(p + ".") or local_part.startswith(p + "_") for p in GENERIC_EMAIL_PREFIXES)
                            or local_part in DECISION_MAKER_PREFIXES
                        ):
                            prio = 3
                            c_type = "generic"
                        else:
                            prio = 2
                            c_type = "named_professional"
                        candidates_map[eff_clean.lower()] = {
                            "email": eff_clean,
                            "type": c_type,
                            "priority": prio,
                            "source_url": effective_website or rec.source or "provider",
                            "name": None,
                            "role": None,
                            "source_backed": bool(
                                rec.email
                                and eff_clean.lower() == str(rec.email).strip().lower()
                                and rec.source
                                and rec.source_id
                            ),
                        }

                unique_candidates = list(candidates_map.values())
                self.metrics.emails_extracted_count += len(unique_candidates)

                # Sort strictly by priority: Priority 1 (Decision-maker) > Priority 2 (Named professional) > Priority 3 (Generic)
                unique_candidates.sort(
                    key=lambda candidate: (
                        not candidate["source_backed"],
                        candidate["priority"],
                        0 if candidate["source_url"] == effective_website else 1,
                    )
                )

                verified_email = None
                verifier = getattr(self, "email_verifier", None) or EmailVerifier()
                req_domain = getattr(self, "require_verified_email", False)

                for cand in unique_candidates:
                    ev_res = verifier.verify(
                        cand["email"],
                        business_name=rec.business_name,
                        website=effective_website,
                        require_business_domain=req_domain,
                        source_backed=cand["source_backed"],
                    )
                    if ev_res.is_valid:
                        verified_email = cand["email"]
                        selected_email_meta = cand
                        selected_ev_res = ev_res
                        break
                    else:
                        self.metrics.emails_rejected_count += 1

                if verified_email:
                    effective_email = verified_email
                    self.metrics.source_backed_count += 1
                    if selected_email_meta["priority"] == 1:
                        self.metrics.decision_maker_count += 1
                    elif selected_email_meta["priority"] == 2:
                        self.metrics.named_professional_count += 1
                    else:
                        self.metrics.generic_count += 1
                elif getattr(self, "require_verified_email", False):
                    effective_email = None
                else:
                    effective_email = None
            else:
                if effective_email and not _PHONE_IN_EMAIL_PATTERN.match(str(effective_email).strip()):
                    self.metrics.emails_extracted_count += 1
                    source_backed = bool(rec.email and rec.source and rec.source_id)
                    verifier = getattr(self, "email_verifier", None) or EmailVerifier()
                    email_verification = verifier.verify(
                        str(effective_email).strip(),
                        business_name=rec.business_name,
                        require_business_domain=getattr(self, "require_verified_email", False),
                        source_backed=source_backed,
                    )
                    if email_verification.is_valid:
                        local_part = str(effective_email).split("@", 1)[0].lower()
                        is_generic = (
                            local_part in DECISION_MAKER_PREFIXES
                            or any(
                                local_part == prefix
                                or local_part.startswith(f"{prefix}.")
                                or local_part.startswith(f"{prefix}_")
                                for prefix in GENERIC_EMAIL_PREFIXES
                            )
                        )
                        contact_type = "generic" if is_generic else "named_professional"
                        priority = 3 if is_generic else 2
                        selected_email_meta = {
                            "email": str(effective_email).strip(),
                            "type": contact_type,
                            "priority": priority,
                            "source_url": rec.source or "provider",
                            "name": None,
                            "role": None,
                            "source_backed": source_backed,
                        }
                        selected_ev_res = email_verification
                        self.metrics.source_backed_count += 1
                        if is_generic:
                            self.metrics.generic_count += 1
                        else:
                            self.metrics.named_professional_count += 1
                    else:
                        self.metrics.emails_rejected_count += 1
                        effective_email = None
                elif effective_email:
                    effective_email = None

            # Step 2c: Verification & Evidence Engine
            target_loc = self.job_state["state"] or self.job_state["region"] or self.job_state["country"]
            page_title = enr_res.seo.title if enr_res and enr_res.seo else None
            h1_tags = enr_res.seo.h1_tags if enr_res and enr_res.seo else None
            schema_name = enr_res.business_info.business_name if enr_res and enr_res.business_info else None

            if enrichment_enabled:
                v_res = VerificationAndEvidenceEngine.verify_candidate(
                    business_name=rec.business_name,
                    website=effective_website,
                    phone=effective_phone,
                    email=effective_email,
                    address=rec.address,
                    city=self.job_state["region"] or self.job_state["state"],
                    state=self.job_state["state"] or self.job_state["region"],
                    social_profiles=discovered_socials,
                    target_location=target_loc,
                    source=rec.source,
                    page_title=page_title,
                    h1_tags=h1_tags,
                    schema_name=schema_name,
                )
            else:
                v_res = OverallVerificationResult(
                    decision="ACCEPT",
                    composite_confidence=0.5,
                    is_verified_entity=False,
                    has_verified_contact=bool(effective_phone or effective_email or effective_website),
                )

            # Record traceable email evidence if a selected email exists
            if selected_email_meta and effective_email:
                v_res.evidence_records.append({
                    "field_name": "email",
                    "status": getattr(selected_ev_res, "deliverability_status", "DELIVERABILITY_UNKNOWN") if selected_ev_res else "DELIVERABILITY_UNKNOWN",
                    "confidence_score": 90 if selected_email_meta.get("priority") == 1 else (80 if selected_email_meta.get("priority") == 2 else 70),
                    "source": selected_email_meta.get("source_url") or effective_website or rec.source,
                    "details": {
                        "email": effective_email,
                        "type": selected_email_meta.get("type", "generic"),
                        "priority": selected_email_meta.get("priority", 3),
                        "source_url": selected_email_meta.get("source_url") or effective_website or rec.source,
                        "name": selected_email_meta.get("name"),
                        "role": selected_email_meta.get("role"),
                        "validation_outcome": getattr(selected_ev_res, "deliverability_status", "DELIVERABILITY_UNKNOWN") if selected_ev_res else "DELIVERABILITY_UNKNOWN",
                    },
                })

            # Sanitize rejected fields
            if enrichment_enabled and v_res.field_results["website"].verification_status == VerificationStatus.REJECTED:
                effective_website = None
            effective_phone = None
            if enrichment_enabled and v_res.field_results["email"].verification_status == VerificationStatus.REJECTED:
                effective_email = None

            # Skip candidate if website has no verified original email after pagination
            if not effective_email:
                logger.info(
                    f"[DiscoveryOrchestrator] Candidate '{rec.business_name}' has website with no verified email after pagination — skipping."
                )
                self.metrics.rejected_count += 1
                continue

            verified_results.append({
                "rec": rec,
                "effective_website": effective_website,
                "effective_phone": None,
                "effective_email": effective_email,
                "discovered_socials": discovered_socials,
                "discovered_whatsapp": discovered_whatsapp,
                "enr_res": enr_res,
                "v_res": v_res,
            })

        logger.info(f"[DiscoveryOrchestrator] Stage 2 Completed: Verified signals for {len(verified_results)} candidates.")
        return verified_results

    def stage_3_qualify_and_score(self, verified_candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Stage 3: Deterministic Quality Gating & ML Opportunity Scoring."""
        qualified_results: list[dict[str, Any]] = []
        total = len(verified_candidates)
        target = self.metrics.requested

        self.job_state["current_source"] = f"Stage 3/4: Calculating ML opportunity scores (0/{total})..."
        

        for idx, item in enumerate(verified_candidates):
            if self._is_job_cancelled():
                return qualified_results

            rec = item["rec"]
            effective_website = item["effective_website"]
            effective_email = item["effective_email"]
            enr_res = item["enr_res"]
            v_res = item["v_res"]
            discovered_socials = item["discovered_socials"]
            discovered_whatsapp = item["discovered_whatsapp"]

            self.job_state["current_source"] = f"Stage 3/4: Scoring opportunity ({idx + 1}/{total})"[:64]
            self.job_state["progress_percent"] = 70.0 + min(20.0, round(((idx + 1) / (total or 1)) * 20.0, 1))
            
            publish_job_progress(
                str(self.job_state["id"]),
                {
                    "event_type": "STAGE_3_QUALIFICATION_PROGRESS",
                    "job_id": str(self.job_state["id"]),
                    "status": self.job_state["status"],
                    "leads_scraped": self.job_state["leads_scraped"] or len(verified_candidates),
                    "target_lead_count": target,
                    "progress_percent": self.job_state["progress_percent"],
                    "discovered": self.metrics.fetched_count,
                    "valid": self.metrics.validated_count,
                    "duplicates": self.metrics.duplicate_count,
                },
            )

            # Quality Gate
            gate_res = QualityGateEngine.evaluate_candidate(
                business_name=rec.business_name,
                phone=None,
                email=effective_email,
                website=effective_website,
                address=rec.address,
                category=rec.category or self.job_state["niche"],
                target_niche=self.job_state["niche"],
                social_profiles=discovered_socials,
                extra_phones=[],
                extra_emails=[e.get("email") for e in (enr_res.contacts.emails if enr_res and enr_res.contacts else []) if e.get("email")],
                extra_whatsapp_links=discovered_whatsapp,
                require_verified_email=getattr(self, "require_verified_email", False),
            )

            if gate_res.decision == QualityGateDecision.ACCEPT:
                self.metrics.validated_count += 1

            # Lead Intelligence / Opportunity Scoring
            intel_report = LeadIntelligenceEngine.evaluate_lead(
                business_name=rec.business_name,
                website=effective_website,
                phone=None,
                email=effective_email,
                category=rec.category or self.job_state["niche"],
                genuineness_score=v_res.composite_confidence,
                website_health=enr_res.health.__dict__ if enr_res and enr_res.health else {},
                contacts_evidence=enr_res.contacts.__dict__ if enr_res and enr_res.contacts else {},
                seo_evidence=enr_res.seo.__dict__ if enr_res and enr_res.seo else {},
                social_evidence={"profiles": discovered_socials},
                technologies_evidence=enr_res.technologies if enr_res else [],
                conflicts_evidence=enr_res.conflicts if enr_res else {},
            )

            if (
                gate_res.decision == QualityGateDecision.ACCEPT
                and intel_report.overall_opportunity_score >= 50
            ):
                self.metrics.qualified_count += 1

            if gate_res.decision != QualityGateDecision.ACCEPT or not effective_email:
                logger.info(
                    f"[DiscoveryOrchestrator] Candidate '{rec.business_name}' failed quality gate ({gate_res.rejection_reason}) — skipping."
                )
                continue

            item["gate_res"] = gate_res
            item["intel_report"] = intel_report
            qualified_results.append(item)

        logger.info(f"[DiscoveryOrchestrator] Stage 3 Completed: Qualified {len(qualified_results)} leads.")
        return qualified_results

    def stage_4_persist_leads(self, qualified_candidates: list[dict[str, Any]]) -> None:
        """Stage 4: Canonical Identity Resolution, Evidence Persistence & Lead Creation."""
        total = len(qualified_candidates)
        target = self.metrics.requested

        self.job_state["current_source"] = f"Stage 4/4: Finalizing & saving leads (0/{total})"[:64]
        

        for idx, item in enumerate(qualified_candidates):
            if self._is_job_cancelled():
                return

            self.job_state["current_source"] = f"Stage 4/4: Persisting ({idx + 1}/{total})"[:64]
            

            rec = item["rec"]
            effective_website = item["effective_website"]
            effective_phone = item["effective_phone"]
            effective_email = item["effective_email"]
            v_res = item["v_res"]
            gate_res = item["gate_res"]
            intel_report = item["intel_report"]

            # Email-only enforcement: skip leads without verified emails when require_verified_email is active
            if getattr(self, "require_verified_email", False) and not effective_email:
                logger.info(
                    f"[DiscoveryOrchestrator] Stage 4: Skipping '{rec.business_name}' — no verified email found."
                )
                continue

            # Resolve accurate canonical location
            c_norm = LocationValidator.normalize_country(self.job_state["country"])
            loc_resolved = LocationValidator.resolve_candidate_location(
                candidate_address=rec.address,
                candidate_phone=effective_phone or rec.phone,
                candidate_website=effective_website or rec.website,
                candidate_coords=(float(rec.latitude), float(rec.longitude)) if rec.latitude is not None and rec.longitude is not None else None,
                raw_place_data=rec.raw_data,
                requested_country_code=c_norm[1] if c_norm else None,
            )

            final_country = loc_resolved.country if loc_resolved.country != "Unknown" else (self.job_state["country"] or "United Kingdom")
            final_region = loc_resolved.region or self.job_state["region"]
            final_city = loc_resolved.city or rec.city or (self.job_state["state"] if self.job_state["state"] != self.job_state["region"] else None)
            final_address = loc_resolved.formatted_address or rec.address

            raw_lead = RawLead(
                source_name=rec.source,
                source_record_id=rec.source_id,
                business_name=rec.business_name,
                industry=rec.category or self.job_state["niche"] or "General",
                address=final_address,
                city=final_city,
                state=final_region,
                country=final_country,
                website=effective_website,
                email=effective_email,
                phone=None,
                raw_payload=_remove_phone_data(rec.raw_data or {}),
            )

            lock_key = self._acquire_lock(rec.business_name, effective_phone, effective_website)
            canonical_lead = None
            try:
                with SessionLocal() as db:
                    canonical_lead, obs, l_state = self.resolver.process_observation(db, raw_lead)
                    if canonical_lead:
                        canonical_lead.canonical_phone = None
                        canonical_lead.canonical_email = effective_email
                    if canonical_lead and effective_website:
                        canonical_lead.canonical_domain = effective_website
                        canonical_lead.website_state = "VERIFIED"
                    canonical_lead_id = str(canonical_lead.id) if canonical_lead else None
            finally:
                self._release_lock(lock_key)

            db = SessionLocal()
            persisted_lead = db.scalar(
                select(Lead).where(
                    Lead.workspace_id == self.job_state["workspace_id"],
                    Lead.business_name == rec.business_name,
                    Lead.job_id == self.job_state["id"],
                )
            )
            if persisted_lead:
                self.metrics.duplicate_count += 1
                continue

            if not persisted_lead:
                persisted_lead = Lead(
                    workspace_id=self.job_state["workspace_id"],
                    job_id=self.job_state["id"],
                    business_name=rec.business_name,
                    website=effective_website,
                    email=effective_email,
                    phone=None,
                    notes=final_address,
                    raw_status="PERSISTED",
                    verification_status="VERIFIED" if (gate_res.decision == QualityGateDecision.ACCEPT and v_res.decision == "ACCEPT") else "UNVERIFIED",
                    genuineness_score=v_res.composite_confidence,
                    workflow_status="NEW",
                )
                db.add(persisted_lead)
                db.flush()
            else:
                persisted_lead.website = effective_website
                persisted_lead.email = effective_email
                persisted_lead.phone = None
                persisted_lead.verification_status = "VERIFIED" if (gate_res.decision == QualityGateDecision.ACCEPT and v_res.decision == "ACCEPT") else "UNVERIFIED"
                persisted_lead.genuineness_score = v_res.composite_confidence

            # Link SourceRecord
            src_id = rec.source_id or rec.business_name
            src_rec = db.scalar(
                select(SourceRecord).where(
                    SourceRecord.source == rec.source,
                    SourceRecord.source_id == src_id,
                )
            )
            if not src_rec:
                src_rec = SourceRecord(
                    workspace_id=self.job_state["workspace_id"],
                    lead_id=persisted_lead.id,
                    source=rec.source,
                    source_id=src_id,
                    raw_data=_remove_phone_data(rec.raw_data or {}),
                )
                db.add(src_rec)
            else:
                src_rec.lead_id = persisted_lead.id
                if rec.raw_data:
                    src_rec.raw_data = _remove_phone_data(rec.raw_data)

            db.commit()

            # AI Model Scoring: CatBoost + LightGBM Ensemble + PredictionLedger recording
            try:
                genuineness_decision = self.genuineness_agent.evaluate_lead_genuineness(db, persisted_lead)
                logger.info(
                    f"[DiscoveryOrchestrator] AI Genuineness: '{rec.business_name}' → "
                    f"{genuineness_decision.decision} (score={genuineness_decision.overall_score:.2f})"
                )
            except Exception as gen_err:
                logger.warning(f"[DiscoveryOrchestrator] GenuinenessAgent error for '{rec.business_name}': {gen_err}")

            # Upsert Evidence Records
            for ev_rec in v_res.evidence_records:
                if ev_rec["field_name"] == "phone":
                    continue
                self._upsert_evidence(
                    field_name=ev_rec["field_name"],
                    status=ev_rec["status"],
                    confidence_score=ev_rec["confidence_score"],
                    source=ev_rec["source"],
                    details=_remove_phone_data(ev_rec["details"]),
                    lead_id=persisted_lead.id,
                    canonical_lead_id=canonical_lead_id,
                )

            self._upsert_evidence(
                field_name="lead_intelligence",
                status=intel_report.opportunity_category.value,
                confidence_score=intel_report.overall_opportunity_score,
                source="LEAD_INTELLIGENCE_ENGINE",
                details={
                    "overall_opportunity_score": intel_report.overall_opportunity_score,
                    "opportunity_category": intel_report.opportunity_category.value,
                    "confidence_score": intel_report.confidence_score,
                    "contactability_score": intel_report.contactability_score,
                    "top_reasons": intel_report.top_reasons,
                },
                lead_id=persisted_lead.id,
                canonical_lead_id=canonical_lead_id,
            )

            self.metrics.saved_count += 1
            self.job_state["leads_scraped"] = self.metrics.saved_count
            self.job_state["current_source"] = f"Stage 4/4: Persisted {self.metrics.saved_count}/{total} leads ({rec.business_name[:25]})"
            self.job_state["progress_percent"] = 90.0 + min(10.0, round((self.metrics.saved_count / (total or 1)) * 10.0, 1))

            # Sync with dedicated RawLeadSheet & RawLead database tables
            import backend.app.models as app_models
            raw_sheet = db.get(app_models.RawLeadSheet, self.job_state["id"])
            if raw_sheet:
                raw_sheet.leads_scraped = self.metrics.saved_count
                raw_sheet.progress_percent = self.job_state["progress_percent"]
                raw_sheet.current_source = self.job_state["current_source"]
                raw_sheet.discovered_count = self.metrics.fetched_count
                raw_sheet.valid_count = self.metrics.validated_count
                raw_sheet.duplicate_count = self.metrics.duplicate_count

                existing_raw_lead = db.scalar(
                    select(app_models.RawLead).where(
                        app_models.RawLead.sheet_id == self.job_state["id"],
                        app_models.RawLead.business_name == rec.business_name,
                    )
                )
                if not existing_raw_lead:
                    r_lead = app_models.RawLead(
                        id=persisted_lead.id,
                        sheet_id=self.job_state["id"],
                        lead_number=self.metrics.saved_count,
                        business_name=rec.business_name,
                        website=effective_website,
                        email=effective_email,
                        phone=None,
                        location=f"{final_city or ''}, {final_region or final_country or ''}".strip(", "),
                        source=rec.source,
                        notes=final_address,
                        raw_data=_remove_phone_data(rec.raw_data or {}),
                    )
                    db.add(r_lead)
                    db.commit()
                    try:
                        from backend.app.worker import celery_app
                        if self.job_state.get("service"):
                            celery_app.send_task("backend.app.worker.enrich_raw_lead_task", args=[str(r_lead.id), self.job_state["service"]])
                    except Exception as e:
                        logger.error(f"Failed to queue enrichment: {e}")

                else:
                    existing_raw_lead.website = effective_website
                    existing_raw_lead.email = effective_email
                    existing_raw_lead.phone = None
                    existing_raw_lead.raw_data = _remove_phone_data(rec.raw_data or {})

                    db.commit()

            publish_job_progress(
                str(self.job_state["id"]),
                {
                    "event_type": "RAW_LEAD_CREATED",
                    "job_id": str(self.job_state["id"]),
                    "lead_id": str(persisted_lead.id),
                    "source": rec.source,
                    "status": self.job_state["status"],
                    "leads_scraped": self.metrics.saved_count,
                    "target_lead_count": target,
                    "progress_percent": self.job_state["progress_percent"],
                    "discovered": self.metrics.fetched_count,
                    "valid": self.metrics.validated_count,
                    "duplicates": self.metrics.duplicate_count,
                },
            )

        logger.info(f"[DiscoveryOrchestrator] Stage 4 Completed: Persisted {self.metrics.saved_count} leads in database.")

    def _process_candidate_record(self, rec: NormalizedLeadRecord) -> bool:
        """Compatibility helper for processing an individual candidate."""
        if not is_viable_candidate(rec):
            return False
        verified = self.stage_2_enrich_and_verify([rec])
        if not verified:
            return False
        qualified = self.stage_3_qualify_and_score(verified)
        if not qualified:
            return False
        self.stage_4_persist_leads(qualified)
        return True

    def _enqueue_expanded_actions(self) -> int:
        """Enqueues additional unique search angles across all selected niches."""
        niches = parse_selected_niches(self.job_state.get("niche"))
        locations = self._target_locations or [
            self.job_state.get("state")
            or self.job_state.get("region")
            or self.job_state.get("country")
            or ""
        ]
        target_sources = list(self.job_state.get("sources") or ["google_maps", "osm_overpass"])
        target_sources.extend(src for src in self.connectors if src not in target_sources)
        if "osm_overpass" not in target_sources:
            target_sources.append("osm_overpass")
        added_actions = 0
        expansion_engine = QueryExpansionEngine()

        for src in target_sources:
            connector = self.connectors.get(src)
            if not connector:
                continue
            p_health = self.metrics.provider_health.get(src, {})
            if p_health.get("status") in ("UNAVAILABLE_NO_CREDENTIALS", "UNAVAILABLE"):
                continue
            with SessionLocal() as db:
                src_score = AdaptiveDiscoveryEngine.get_source_score(db, src)
            for loc in locations:
                for niche in niches:
                    expanded_plan = expansion_engine.expand_query(niche, loc, max_queries=30)
                    for item in expanded_plan:
                        q_term = item["query"]
                        if hasattr(connector, "supports_category") and not connector.supports_category(q_term):
                            continue
                        query_key = (src, loc, q_term.lower())
                        if query_key in self._executed_query_pages:
                            continue
                        if any(a.provider == src and a.location == loc and a.query.lower() == q_term.lower() for a in self.action_queue):
                            continue
                        with SessionLocal() as db:
                            q_score = AdaptiveDiscoveryEngine.get_query_score(db, q_term)
                        self.action_queue.append(
                            DiscoveryAction(
                                provider=src,
                                query=q_term,
                                query_reason=item.get("reason", "backfill_expansion"),
                                location=loc,
                                page=1,
                                pagination_state={},
                                priority=3,
                                historical_score=(src_score * 1.5) + q_score,
                            )
                        )
                        added_actions += 1
        return added_actions

    def run_discovery(self) -> None:
        """Main staged orchestrator discovery pipeline governed by 20-minute SLA time budget.
        Executes controlled batches of:
          Stage 1 (Discovery & Viability Filter) ->
          Stage 2 (Signal Verification & Priority Email Discovery) ->
          Stage 3 (ML Opportunity Qualification) ->
          Stage 4 (Promotion & Database Persistence).

        Continues discovery across batches, paginated sources, and expanded queries until:
        - Requested qualified lead target is met (saved_count >= requested)
        - 20-minute SLA time budget expires (elapsed >= max_duration_seconds)
        - All sources and query expansions are exhausted
        - Job is cancelled
        """
        if self.metrics.start_time == 0.0:
            self.metrics.start_time = time.time()

        if not self.action_queue:
            self._build_initial_action_queue()

        while (
            self.metrics.saved_count < self.metrics.requested
            and self.metrics.requests_executed < self.metrics.max_requests
            and not self._is_job_cancelled()
        ):
            # 1. Check 20-minute SLA time budget
            elapsed = time.time() - self.metrics.start_time
            self.metrics.elapsed_time = elapsed
            if elapsed >= self.max_duration_seconds:
                logger.info(
                    f"[DiscoveryOrchestrator] 20-minute SLA time budget reached ({elapsed:.1f}s >= {self.max_duration_seconds}s). "
                    f"Stopping cleanly with {self.metrics.saved_count}/{self.metrics.requested} leads."
                )
                break

            # 2. Check if action queue needs expansion
            if not self.action_queue:
                self._enqueue_expanded_actions()
            if not self.action_queue:
                logger.info("[DiscoveryOrchestrator] Discovery actions exhausted.")
                break

            # 3. Stage 1: Discover viable candidate batch
            deficit = self.metrics.requested - self.metrics.saved_count
            batch_limit = max(10, min(50, deficit * 3))
            viable_batch = self.stage_1_discover_viable_candidates(batch_limit=batch_limit)

            if not viable_batch:
                if (
                    self.metrics.requests_executed < self.metrics.max_requests
                    and self.metrics.elapsed_time < self.max_duration_seconds
                    and self.action_queue
                ):
                    continue
                if (
                    self.metrics.requests_executed < self.metrics.max_requests
                    and self.metrics.elapsed_time < self.max_duration_seconds
                ):
                    continue
                logger.info("[DiscoveryOrchestrator] No viable candidates remain within the active budget.")
                break

            # 4. Stage 2: Signal Verification & 3-Tier Priority Email Discovery
            verified_batch = self.stage_2_enrich_and_verify(viable_batch)

            # 5. Stage 3: ML Qualification & Opportunity Scoring
            qualified_batch = self.stage_3_qualify_and_score(verified_batch)

            # 6. Stage 4: Canonical Resolution & Lead Persistence
            self.stage_4_persist_leads(qualified_batch)

            # 7. Update progress metrics
            self.metrics.elapsed_time = time.time() - self.metrics.start_time
            self.metrics.qualified_yield = (
                (self.metrics.qualified_count / max(1, self.metrics.researched_count)) * 100.0
            )

        # Finalize
        self.finalize_discovery()

    def finalize_discovery(self) -> None:
        """Finalizes job status and assigns deterministic completion states."""
        if self._is_job_cancelled():
            return

        # Double check actual persisted database count
        with SessionLocal() as db:
            persisted_count = db.scalar(
                select(func.count(Lead.id)).where(Lead.job_id == self.job_state["id"])
            ) or 0
        self.job_state["leads_scraped"] = max(self.metrics.saved_count, persisted_count)
        self.metrics.saved_count = self.job_state["leads_scraped"]

        target = self.metrics.requested
        scraped = self.job_state["leads_scraped"]

        if self.metrics.start_time > 0:
            self.metrics.elapsed_time = time.time() - self.metrics.start_time
        self.metrics.qualified_yield = (
            (self.metrics.qualified_count / max(1, self.metrics.researched_count)) * 100.0
        )

        has_provider_failures = len(self.metrics.sources_failed) > 0
        successful_sources = list(self.metrics.sources_succeeded)
        time_budget_expired = (
            self.metrics.elapsed_time >= self.max_duration_seconds
            and scraped < target
        )
        request_budget_exhausted = (
            self.metrics.requests_executed >= self.metrics.max_requests
            and scraped < target
        )

        if scraped >= target:
            self.job_state["status"] = "COMPLETED"
            self.job_state["completion_reason"] = "TARGET_REACHED"
        elif scraped == 0 and target > 0:
            self.job_state["status"] = "FAILED"
            if time_budget_expired:
                self.job_state["completion_reason"] = "TIME_BUDGET_EXPIRED"
                self.job_state["error_message"] = "20-minute SLA time budget expired before qualifying any leads."
            elif request_budget_exhausted:
                self.job_state["completion_reason"] = "REQUEST_BUDGET_EXHAUSTED"
                self.job_state["error_message"] = "Discovery request budget expired before qualifying any leads."
            elif has_provider_failures and not successful_sources:
                self.job_state["completion_reason"] = "ALL_SOURCES_FAILED"
                self.job_state["error_message"] = "All provider sources failed."
            else:
                self.job_state["completion_reason"] = "DISCOVERY_EXHAUSTED"
                self.job_state["error_message"] = "Discovery exhausted. No valid leads found."
        elif scraped < target:
            self.job_state["status"] = "PARTIAL"
            if time_budget_expired:
                self.job_state["completion_reason"] = "TIME_BUDGET_EXPIRED"
            elif request_budget_exhausted:
                self.job_state["completion_reason"] = "REQUEST_BUDGET_EXHAUSTED"
            elif has_provider_failures:
                self.job_state["completion_reason"] = "PARTIAL_SOURCE_FAILURE"
            else:
                self.job_state["completion_reason"] = "DISCOVERY_EXHAUSTED"

        self.job_state["progress_percent"] = min(
            100.0, round((scraped / target) * 100, 1) if target > 0 else 0.0
        )
        self.job_state["valid_count"] = self.metrics.validated_count
        self.job_state["duplicate_count"] = self.metrics.duplicate_count
        self.job_state["fetched_count"] = self.job_state.get('fetched_count', 0) + self.metrics.fetched_count

        with SessionLocal() as db:
            import backend.app.models as app_models
            raw_sheet = db.get(app_models.RawLeadSheet, self.job_state["id"])
            if raw_sheet:
                raw_sheet.status = self.job_state["status"]
                raw_sheet.completion_reason = self.job_state["completion_reason"]
                raw_sheet.error_message = self.job_state.get("error_message")
                raw_sheet.leads_scraped = self.job_state["leads_scraped"]
                raw_sheet.progress_percent = self.job_state["progress_percent"]
                raw_sheet.discovered_count = self.metrics.fetched_count
                raw_sheet.valid_count = self.metrics.validated_count
                raw_sheet.duplicate_count = self.metrics.duplicate_count
                raw_sheet.failed_count = self.metrics.rejected_count
            
            job = db.get(app_models.ScrapeJob, self.job_state["id"])
            if job:
                job.status = self.job_state["status"]
                job.completion_reason = self.job_state["completion_reason"]
                job.error_message = self.job_state.get("error_message")
                job.leads_scraped = self.job_state["leads_scraped"]
                job.progress_percent = self.job_state["progress_percent"]
                job.discovered_count = self.metrics.fetched_count
                job.valid_count = self.metrics.validated_count
                job.duplicate_count = self.metrics.duplicate_count
                job.fetched_count = self.job_state["fetched_count"]
            
            db.commit()

        

        logger.info(
            f"[DiscoveryOrchestrator] Completed Job {self.job_state["id"]}: Status={self.job_state["status"]}, "
            f"Reason={self.job_state["completion_reason"]}, Scraped={scraped}/{target}, "
            f"Fetched={self.metrics.fetched_count}, Unique={self.metrics.unique_count}, "
            f"Validated={self.metrics.validated_count}, Qualified={self.metrics.qualified_count}"
        )

        publish_job_progress(
            str(self.job_state["id"]),
            {
                "event_type": f"JOB_{self.job_state["status"]}",
                "job_id": str(self.job_state["id"]),
                "status": self.job_state["status"],
                "completion_reason": self.job_state["completion_reason"],
                "error_message": self.job_state["error_message"],
                "leads_scraped": scraped,
                "target_lead_count": target,
                "progress_percent": self.job_state["progress_percent"],
                "discovered": self.metrics.fetched_count,
                "valid": self.metrics.validated_count,
                "duplicates": self.metrics.duplicate_count,
            },
        )
