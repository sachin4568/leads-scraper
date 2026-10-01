from __future__ import annotations

import logging
from typing import Any
from backend.app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

def get_broker_url() -> str:
    try:
        url = settings.redis_url.get_secret_value()
        import redis
        r = redis.Redis.from_url(url, socket_timeout=0.5, socket_connect_timeout=0.5)
        r.ping()
        return url
    except Exception:
        return "memory://"

try:
    from celery import Celery
    celery_app = Celery("lead_intelligence", broker=get_broker_url())
    celery_app.conf.update(task_acks_late=True, task_reject_on_worker_lost=True)
except (ImportError, Exception):
    class DummyCelery:
        def task(self, *args, **kwargs):
            def decorator(f):
                f.delay = f
                return f
            return decorator
    celery_app = DummyCelery()


@celery_app.task(bind=True, ignore_result=True)
def healthcheck_task(self) -> None:
    """Idempotent Phase 1 worker health task."""


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def sync_leads_to_google_sheets_task(
    self,
    token_info: dict[str, str | None],
    spreadsheet_id: str,
    sheet_name: str,
    rows: list[list[str]],
) -> dict[str, object]:
    """Idempotent background task for syncing leads to Google Sheets."""
    from backend.app.google_sheets import GoogleSheetsSyncService

    service = GoogleSheetsSyncService(token_info)
    return service.sync_leads(spreadsheet_id, sheet_name, rows)


def _upsert_evidence_record(
    db: Any,
    workspace_id: Any,
    lead_id: Any,
    canonical_lead_id: str | None,
    field_name: str,
    status: str,
    confidence_score: int,
    source: str,
    details: dict[str, Any] | None,
) -> EvidenceRecord:
    from sqlalchemy import select
    from backend.app.models import EvidenceRecord

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
            workspace_id=workspace_id,
            lead_id=lead_id,
            canonical_lead_id=canonical_lead_id,
            field_name=field_name,
            status=status,
            confidence_score=confidence_score,
            source=source,
            details=details,
        )
        db.add(ev)
    return ev


def generate_search_plan(niche: str, location: str | None) -> list[str]:
    clean_niche = (niche or "Business").strip()
    queries = [clean_niche]

    if not clean_niche.lower().endswith("s"):
        queries.append(f"{clean_niche}s")

    clean_lower = clean_niche.lower()
    if "clinic" in clean_lower:
        base = clean_lower.replace("clinics", "").replace("clinic", "").strip()
        queries.extend([f"{base} practice", f"family {base}", f"cosmetic {base}"])
    elif "dental" in clean_lower or "dentist" in clean_lower:
        queries.extend(["Dentists", "Dental Practice", "Family Dentist", "Cosmetic Dentist"])
    else:
        queries.extend([f"best {clean_niche}", f"top {clean_niche}", f"local {clean_niche}"])

    seen = set()
    result = []
    for q in queries:
        q_norm = q.lower().strip()
        if q_norm and q_norm not in seen:
            seen.add(q_norm)
            result.append(q)
    return result


def get_connectors() -> dict[str, Any]:
    from backend.app.sources.data_axle import DataAxleConnector
    from backend.app.sources.foursquare import FoursquareConnector
    from backend.app.sources.google_maps import GoogleMapsConnector, GooglePlacesConnector
    from backend.app.sources.google_search import GoogleSearchConnector
    from backend.app.sources.linkedin import LinkedInConnector
    from backend.app.sources.meta import MetaConnector
    from backend.app.sources.yelp import YelpConnector
    from backend.app.sources.osm_overpass import OSMOverpassConnector

    return {
        "google_maps": GoogleMapsConnector(),
        "google_places": GooglePlacesConnector(),
        "foursquare": FoursquareConnector(),
        "data_axle": DataAxleConnector(),
        "yelp": YelpConnector(),
        "google_search": GoogleSearchConnector(),
        "linkedin": LinkedInConnector(),
        "meta": MetaConnector(),
        "osm_overpass": OSMOverpassConnector(),
    }


def track_metric(job_id_str: str, metric_name: str, amount: int = 1) -> None:
    from backend.app.worker_concurrency import _global_limiter
    r = _global_limiter._redis_client
    if r:
        try:
            r.hincrby(f"job_metrics:{job_id_str}", metric_name, amount)
        except Exception:
            pass


def get_job_metrics(job_id_str: str) -> dict[str, Any]:
    from backend.app.worker_concurrency import _global_limiter
    r = _global_limiter._redis_client
    metrics = {
        "queries_executed": 0,
        "requests_executed": 0,
        "results_received": 0,
        "unique_businesses": 0,
        "duplicates": 0,
        "cross_source_matches": 0,
        "new_canonical_leads": 0,
        "enrichment_requests": 0,
        "validation_attempts": 0,
        "validation_passes": 0,
        "incomplete_leads": 0,
        "qualified_leads": 0,
        "source_failures": 0,
        "429s": 0,
        "timeouts": 0,
        "retries": 0,
        "crawl_budget_consumed": 0,
        "average_latency": 0.0,
    }
    if r:
        try:
            stored = r.hgetall(f"job_metrics:{job_id_str}")
            if stored:
                for k, v in stored.items():
                    if k in metrics:
                        if k == "average_latency":
                            metrics[k] = float(v)
                        else:
                            metrics[k] = int(v)
                
                # Calculate rates
                rec = metrics["results_received"]
                uniq = metrics["unique_businesses"]
                val_att = metrics["validation_attempts"]
                val_pass = metrics["validation_passes"]
                qual = metrics["qualified_leads"]
                matches = metrics["cross_source_matches"]
                
                metrics["unique_rate"] = round(uniq / rec, 2) if rec > 0 else 0.0
                metrics["cross_source_match_rate"] = round(matches / uniq, 2) if uniq > 0 else 0.0
                metrics["validation_rate"] = round(val_pass / val_att, 2) if val_att > 0 else 0.0
                metrics["qualification_rate"] = round(qual / uniq, 2) if uniq > 0 else 0.0
        except Exception:
            pass
    return metrics


def acquire_lead_lock(r, name: str, phone: str | None, website: str | None) -> str | None:
    if not r:
        return None
    from backend.app.ingestion.identity import normalize_business_name, normalize_phone, normalize_domain
    norm_name = normalize_business_name(name)
    norm_phone = normalize_phone(phone)
    norm_domain = normalize_domain(website)
    sig = f"{norm_name}:{norm_phone or norm_domain}"
    lock_key = f"lock:lead_ingestion:{sig}"
    import time
    for _ in range(50):
        if r.set(lock_key, "locked", ex=10, nx=True):
            return lock_key
        time.sleep(0.1)
    return None


def release_lead_lock(r, lock_key: str | None) -> None:
    if r and lock_key:
        try:
            r.delete(lock_key)
        except Exception:
            pass


def execute_single_query_plan(db, job, plan) -> None:
    import json
    import time
    from sqlalchemy import select
    from backend.app.models import Lead, ScrapeJobExecutionLog, SourceRecord
    from backend.app.websockets import publish_job_progress
    from backend.app.sources.geo_utils import SubdivisionManager
    from backend.app.ingestion.lifecycle import LifecycleResolver, LifecycleState
    from backend.app.enrichment.enrichment_engine import DeepFeatureEnrichmentEngine
    from backend.app.services.classification_agent import MultiLabelClassificationAgent
    from backend.app.models_services import ServiceOpportunity
    from backend.app.ingestion.ingestion import RawLead

    connectors = get_connectors()
    src_name = plan["source"]
    query_term = plan["query"]
    query_reason = plan["reason"]
    location = plan["location"]

    connector = connectors.get(src_name)
    if not connector:
        return

    if hasattr(connector, "supports_category") and not connector.supports_category(query_term):
        logger.info(
            f"[QueryPlan] Traceability: original_query='{plan.get('niche', job.niche)}' expanded_query='{query_term}' "
            f"connector='{src_name}' category_supported=False execution_status=SKIPPED result_count=0"
        )
        return

    from backend.app.worker_concurrency import _global_limiter
    r = _global_limiter._redis_client
    job_id_str = str(job.id)
    track_metric(job_id_str, "queries_executed")

    cells = []
    if src_name in ("google_maps", "google_places", "yelp"):
        target = job.target_lead_count or 10
        if target <= 5:
            subdivisions = 1
        elif target <= 20:
            subdivisions = 4
        else:
            subdivisions = 9
        cells = SubdivisionManager.subdivide_location(location, subdivisions=subdivisions)
        track_metric(job_id_str, "geographic_subdivision_count", subdivisions)

    if not cells:
        cells = [{"bbox": None, "center_lat": None, "center_lon": None, "radius_meters": None, "location_str": location}]
    else:
        for cell in cells:
            cell["location_str"] = f"{cell['center_lat']},{cell['center_lon']}"

    resolver = LifecycleResolver()
    enrichment_engine = DeepFeatureEnrichmentEngine()
    seen_ids = set()

    for cell in cells:
        if job.leads_scraped >= job.target_lead_count:
            break

        loc_param = cell["location_str"]
        pagination_state = {
            "page": 1,
            "next_page_token": None,
            "results_returned": 0,
            "unique_results": 0,
            "duplicate_results": 0,
            "has_more": True,
            "seen_cursors": set()
        }
        if cell.get("radius_meters"):
            pagination_state["radius_meters"] = cell["radius_meters"]

        max_pages_per_query = 5
        empty_pages_count = 0

        while (
            pagination_state.get("page", 1) <= max_pages_per_query
            and job.leads_scraped < job.target_lead_count
            and empty_pages_count < 2
            and pagination_state.get("has_more", True)
        ):
            db.refresh(job)
            if job.status in ("STOPPED_SAVED", "CANCELLED"):
                return

            page_num = pagination_state["page"]
            reqs_executed = 0
            if r:
                try:
                    reqs_executed = int(r.hget(f"job_metrics:{job_id_str}", "requests_executed") or 0)
                except Exception:
                    pass
            crawl_budget = max(100, (job.target_lead_count or 10) * 10)
            if reqs_executed >= crawl_budget:
                logger.warning(f"Crawl budget limit of {crawl_budget} requests reached. Aborting.")
                pagination_state["has_more"] = False
                break

            cursor = pagination_state.get("next_page_token")
            if cursor:
                if cursor in pagination_state["seen_cursors"]:
                    logger.warning(f"[Pagination] Duplicate cursor detected: {cursor}. Aborting.")
                    break
                pagination_state["seen_cursors"].add(cursor)

            records = []
            try:
                track_metric(job_id_str, "requests_executed")
                track_metric(job_id_str, "crawl_budget_consumed")
                start_time = time.time()

                import inspect
                sig = inspect.signature(connector.search_leads)
                if "pagination_state" in sig.parameters:
                    records = connector.search_leads(
                        query=query_term,
                        location=loc_param,
                        limit=50,
                        page=page_num,
                        pagination_state=pagination_state
                    )
                else:
                    records = connector.search_leads(
                        query=query_term,
                        location=loc_param,
                        limit=50,
                        page=page_num
                    )
                    pagination_state["results_returned"] = pagination_state.get("results_returned", 0) + len(records)
                    if len(records) == 0:
                        pagination_state["has_more"] = False
                        
                latency_ms = (time.time() - start_time) * 1000
                track_metric(job_id_str, "latency_sum", int(latency_ms))
                track_metric(job_id_str, "latency_count", 1)
                
                if hasattr(connector, "record_success"):
                    connector.record_success()
            except Exception as src_err:
                err_str = str(src_err).lower()
                classification = "UNAVAILABLE_PROVIDER"
                
                if "timeout" in err_str:
                    classification = "TIMEOUT"
                    track_metric(job_id_str, "timeouts")
                elif "429" in err_str or "rate limit" in err_str:
                    classification = "RATE_LIMITED"
                    track_metric(job_id_str, "429s")
                elif "401" in err_str or "403" in err_str or "auth" in err_str or "key" in err_str:
                    classification = "AUTH_FAILURE"
                elif "500" in err_str or "504" in err_str or "server error" in err_str:
                    classification = "SERVER_ERROR"
                elif "json" in err_str or "decode" in err_str:
                    classification = "MALFORMED_RESPONSE"
                elif "empty" in err_str:
                    classification = "EMPTY_RESPONSE"
                    
                logger.error(f"[Failure] Provider failure '{classification}' for {src_name}: {src_err}")
                track_metric(job_id_str, "source_failures")
                if r:
                    r.sadd(f"job_failed_sources:{job_id_str}", src_name)
                if hasattr(connector, "record_failure"):
                    connector.record_failure()
                    
                exec_log = ScrapeJobExecutionLog(
                    job_id=job.id,
                    source=src_name,
                    query=f"{query_term} ({query_reason})",
                    page=page_num,
                    records_received=0,
                    records_valid=0,
                    records_rejected=0,
                    new_count=0,
                    updated_count=0,
                    duplicate_count=0,
                    failed_count=1,
                    error_reason=f"[{classification}] {src_err}",
                )
                db.add(exec_log)
                db.commit()

                # Automated Resilient Cascade: If primary provider failed, try osm_overpass fallback
                if src_name != "osm_overpass":
                    try:
                        logger.info(f"[Fallback] Source '{src_name}' failed ({classification}). Automatically cascading to 'osm_overpass' for query '{query_term}' in '{loc_param}'")
                        osm_conn = connectors.get("osm_overpass")
                        if osm_conn:
                            records = osm_conn.search_leads(
                                query=query_term,
                                location=loc_param,
                                limit=job.target_lead_count or 50,
                                page=page_num,
                                pagination_state=pagination_state,
                            )
                            if records:
                                logger.info(f"[Fallback] 'osm_overpass' successfully recovered {len(records)} candidate leads!")
                                if r:
                                    r.sadd(f"job_success_sources:{job_id_str}", "osm_overpass")
                    except Exception as fb_err:
                        logger.warning(f"[Fallback] Fallback discovery via 'osm_overpass' failed: {fb_err}")
                        records = []

                if not records:
                    return

            records_received = len(records)
            track_metric(job_id_str, "results_received", records_received)
            job.fetched_count = getattr(job, 'fetched_count', 0) + records_received
            
            records_valid = 0
            records_rejected = 0
            page_new = 0
            page_updated = 0
            page_duplicate = 0
            page_failed = 0

            if not records:
                empty_pages_count += 1
            else:
                empty_pages_count = 0

            # Candidate signal scoring for intelligent prioritization
            def _candidate_signal_score(r_cand) -> int:
                s = 0
                if r_cand.website and str(r_cand.website).strip():
                    s += 40
                if r_cand.phone and str(r_cand.phone).strip():
                    s += 35
                if r_cand.email and str(r_cand.email).strip():
                    s += 30
                if r_cand.address and str(r_cand.address).strip():
                    s += 15
                return s

            # Sort records so strongest candidate signals are evaluated and enriched first
            prioritized_records = sorted(records, key=_candidate_signal_score, reverse=True)

            for rec in prioritized_records:
                if job.leads_scraped >= job.target_lead_count:
                    break

                db.refresh(job)
                if job.status in ("STOPPED_SAVED", "CANCELLED"):
                    return

                job.discovered_count += 1

                rec_key = rec.get_idempotency_key()
                if rec_key in seen_ids:
                    job.duplicate_count += 1
                    page_duplicate += 1
                    track_metric(job_id_str, "duplicates")
                    pagination_state["duplicate_results"] = pagination_state.get("duplicate_results", 0) + 1
                    continue
                seen_ids.add(rec_key)

                from backend.app.orchestration.discovery_orchestrator import is_viable_candidate

                if not is_viable_candidate(rec):
                    records_rejected += 1
                    job.failed_count += 1
                    page_failed += 1
                    continue

                raw_lead = RawLead(
                    source_name=rec.source,
                    source_record_id=rec.source_id,
                    business_name=rec.business_name,
                    industry=rec.category or job.niche or "General",
                    address=rec.address,
                    city=job.state or job.region,
                    country=job.country or "United States",
                    website=rec.website,
                    phone=rec.phone,
                    raw_payload=rec.raw_data or {},
                )

                lock_key = acquire_lead_lock(r, rec.business_name, rec.phone, rec.website)
                try:
                    canonical_lead, obs, l_state = resolver.process_observation(db, raw_lead)
                finally:
                    release_lead_lock(r, lock_key)

                if l_state == LifecycleState.DUPLICATE:
                    job.duplicate_count += 1
                    page_duplicate += 1
                    track_metric(job_id_str, "duplicates")
                    pagination_state["duplicate_results"] = pagination_state.get("duplicate_results", 0) + 1
                    continue

                track_metric(job_id_str, "unique_businesses")
                if l_state == LifecycleState.NEW:
                    job.new_count += 1
                    page_new += 1
                    track_metric(job_id_str, "new_canonical_leads")
                    pagination_state["unique_results"] = pagination_state.get("unique_results", 0) + 1
                elif l_state == LifecycleState.UPDATED:
                    job.updated_count += 1
                    page_updated += 1
                    track_metric(job_id_str, "cross_source_matches")
                    pagination_state["unique_results"] = pagination_state.get("unique_results", 0) + 1

                # ── Candidate Discovery & Targeted Enrichment ──
                effective_website = rec.website
                effective_phone = rec.phone
                effective_email = rec.email
                discovered_socials = {}
                discovered_whatsapp = []
                enr_res = None

                job_enrichments = getattr(job, "enrichments", None)
                is_enrichment_enabled = (
                    bool(job_enrichments)
                    if job_enrichments is not None
                    else bool(job.service)
                )

                if is_enrichment_enabled:
                    # 0. Zero-Budget Official Website Discovery & Verification (if candidate lacks website)
                    if not effective_website:
                        try:
                            from backend.app.enrichment.website_discovery import (
                                ZeroBudgetDiscoveryEngine,
                                VerificationDecision,
                            )

                            disc_engine = ZeroBudgetDiscoveryEngine()
                            raw_tags = rec.raw_data.get("tags") if isinstance(rec.raw_data, dict) else {}
                            verif_res = disc_engine.discover_and_verify_official_website(
                                business_name=rec.business_name,
                                phone=rec.phone,
                                email=rec.email,
                                address=rec.address,
                                city=rec.city,
                                raw_data_tags=raw_tags,
                            )

                            if verif_res.decision == VerificationDecision.ACCEPT and verif_res.verified_url:
                                effective_website = verif_res.verified_url
                                if canonical_lead:
                                    canonical_lead.canonical_domain = verif_res.verified_url
                                    canonical_lead.website_state = "VERIFIED"
                                logger.info(
                                    f"[Website Discovery] Successfully verified official website for '{rec.business_name}': {verif_res.verified_url}"
                                )
                        except Exception as disc_err:
                            logger.warning(
                                f"[Website Discovery] Zero-budget discovery warning for candidate '{rec.business_name}': {disc_err}"
                            )

                    # 1. Production Website Intelligence & Deep Contact Enrichment
                    if effective_website:
                        try:
                            from backend.app.enrichment.website_enricher import ProductionWebsiteEnricher

                            enricher = ProductionWebsiteEnricher()
                            enr_res = enricher.enrich_website(
                                target_url=effective_website,
                                provider_phone=rec.phone,
                                provider_email=rec.email,
                                provider_address=rec.address,
                            )

                            if enr_res and enr_res.contacts:
                                if enr_res.contacts.phones and not effective_phone:
                                    effective_phone = enr_res.contacts.phones[0].get("phone")
                                if enr_res.contacts.emails and not effective_email:
                                    effective_email = enr_res.contacts.emails[0].get("email")
                                discovered_whatsapp = enr_res.contacts.whatsapp_links or []
                            if enr_res and enr_res.social_profiles:
                                discovered_socials = enr_res.social_profiles
                        except Exception as enrich_err:
                            logger.warning(
                                f"[Enrichment] Website enrichment warning for '{rec.business_name}': {enrich_err}"
                            )

                # ── Deterministic Production Quality Gate ──
                from backend.app.intelligence.quality_gate import (
                    QualityGateEngine,
                    QualityGateDecision,
                )

                extra_ph = [p.get("phone") for p in (enr_res.contacts.phones if enr_res and enr_res.contacts else []) if p.get("phone")]
                extra_em = [e.get("email") for e in (enr_res.contacts.emails if enr_res and enr_res.contacts else []) if e.get("email")]
                extra_wa = discovered_whatsapp

                gate_res = QualityGateEngine.evaluate_candidate(
                    business_name=rec.business_name,
                    phone=effective_phone,
                    email=effective_email,
                    website=effective_website,
                    whatsapp=None,
                    social_profiles=discovered_socials,
                    website_verification_status="ACCEPT" if effective_website else None,
                    category=rec.category or job.niche,
                    target_niche=job.niche,
                    address=rec.address,
                    city=job.state or job.region,
                    target_location=location,
                    extra_phones=extra_ph,
                    extra_emails=extra_em,
                    extra_whatsapp_links=extra_wa,
                )

                if gate_res.decision == QualityGateDecision.REJECT:
                    records_rejected += 1
                    job.failed_count += 1
                    page_failed += 1
                    rej_reason_str = gate_res.rejection_reason.value if gate_res.rejection_reason else "UNQUALIFIED_CANDIDATE"
                    logger.info(
                        f"[QualityGate] Candidate '{rec.business_name}' REJECTED: {rej_reason_str} "
                        f"({'; '.join(gate_res.rejection_details)})"
                    )
                    track_metric(job_id_str, f"rejected_{rej_reason_str}")
                    continue  # DO NOT PERSIST AS PRODUCTION LEAD; CONTINUE DISCOVERY

                # ── Candidate Passed Quality Gate -> Promote to Production Lead ──
                records_valid += 1
                job.valid_count += 1

                final_phone = gate_res.verified_contacts.get("phone") or effective_phone
                final_email = gate_res.verified_contacts.get("email") or effective_email
                final_website = gate_res.verified_contacts.get("website") or effective_website

                existing_src = db.scalar(
                    select(SourceRecord).where(
                        SourceRecord.source == rec.source,
                        SourceRecord.source_id == rec.source_id,
                    )
                )
                if existing_src:
                    lead = db.get(Lead, existing_src.lead_id)
                    if lead:
                        if final_phone and not lead.phone:
                            lead.phone = final_phone
                        if final_email and not lead.email:
                            lead.email = final_email
                        if final_website and not lead.website:
                            lead.website = final_website
                else:
                    lead = Lead(
                        workspace_id=job.workspace_id,
                        job_id=job.id,
                        business_name=rec.business_name,
                        website=final_website,
                        phone=final_phone,
                        email=final_email,
                        notes=f"Source: {rec.source} | Accepted: {', '.join(gate_res.acceptance_reasons)}",
                        raw_status="PERSISTED",
                        verification_status="VERIFIED",
                        genuineness_status="VERIFIED",
                        genuineness_score=gate_res.identity_confidence,
                    )
                    db.add(lead)
                    db.flush()

                    src_rec = SourceRecord(
                        workspace_id=job.workspace_id,
                        lead_id=lead.id,
                        source=rec.source,
                        source_id=rec.source_id,
                        raw_data=rec.raw_data,
                    )
                    db.add(src_rec)
                    db.flush()

                # Record Evidence and Intelligence
                if lead and is_enrichment_enabled:
                    try:
                        # Record Website Evidence
                        if final_website:
                            _upsert_evidence_record(
                                db=db,
                                workspace_id=job.workspace_id,
                                lead_id=lead.id,
                                canonical_lead_id=str(canonical_lead.id) if canonical_lead else None,
                                field_name="website",
                                status="VERIFIED",
                                confidence_score=int(gate_res.identity_confidence * 100),
                                source="QUALITY_GATE_VERIFIED",
                                details={"verified_url": final_website, "reasons": gate_res.acceptance_reasons},
                            )

                        # Record Contacts Evidence
                        if enr_res and enr_res.contacts:
                            _upsert_evidence_record(
                                db=db,
                                workspace_id=job.workspace_id,
                                lead_id=lead.id,
                                canonical_lead_id=str(canonical_lead.id) if canonical_lead else None,
                                field_name="contacts",
                                status="VERIFIED",
                                confidence_score=gate_res.contactability_score,
                                source="WEBSITE_ENRICHMENT",
                                details={
                                    "emails": enr_res.contacts.emails,
                                    "phones": enr_res.contacts.phones,
                                    "whatsapp_links": enr_res.contacts.whatsapp_links,
                                    "addresses": enr_res.contacts.addresses,
                                },
                            )

                        # Record SEO Evidence
                        if enr_res and enr_res.seo:
                            _upsert_evidence_record(
                                db=db,
                                workspace_id=job.workspace_id,
                                lead_id=lead.id,
                                canonical_lead_id=str(canonical_lead.id) if canonical_lead else None,
                                field_name="seo",
                                status="VERIFIED",
                                confidence_score=enr_res.seo.seo_score,
                                source="WEBSITE_ENRICHMENT",
                                details={
                                    "title": enr_res.seo.title,
                                    "meta_description": enr_res.seo.meta_description,
                                    "canonical_url": enr_res.seo.canonical_url,
                                    "h1_tags": enr_res.seo.h1_tags,
                                    "h2_tags": enr_res.seo.h2_tags,
                                    "seo_issues": enr_res.seo.seo_issues,
                                },
                            )

                        # Record Technologies
                        if enr_res and enr_res.technologies:
                            _upsert_evidence_record(
                                db=db,
                                workspace_id=job.workspace_id,
                                lead_id=lead.id,
                                canonical_lead_id=str(canonical_lead.id) if canonical_lead else None,
                                field_name="technologies",
                                status="VERIFIED",
                                confidence_score=90,
                                source="WEBSITE_ENRICHMENT",
                                details={"detected_technologies": enr_res.technologies},
                            )

                        # Record Social Profiles
                        if discovered_socials:
                            _upsert_evidence_record(
                                db=db,
                                workspace_id=job.workspace_id,
                                lead_id=lead.id,
                                canonical_lead_id=str(canonical_lead.id) if canonical_lead else None,
                                field_name="social_profiles",
                                status="VERIFIED",
                                confidence_score=90,
                                source="WEBSITE_ENRICHMENT",
                                details={"profiles": discovered_socials},
                            )

                        # Optional Service Classification
                        if canonical_lead:
                            try:
                                import json
                                from backend.app.services.classification_agent import MultiLabelClassificationAgent
                                from backend.app.models_services import ServiceOpportunity

                                lead_payload = {
                                    "canonical_lead_id": canonical_lead.id,
                                    "business_name": canonical_lead.business_name,
                                    "website": canonical_lead.canonical_domain,
                                    "phone": canonical_lead.canonical_phone,
                                    "email": canonical_lead.canonical_email,
                                    "country": canonical_lead.country or job.country or "United States",
                                    "region_state": canonical_lead.state or job.state or job.region,
                                    "city": canonical_lead.city,
                                    "niche": job.niche or canonical_lead.industry or "General",
                                    "business_type": canonical_lead.business_maturity or "SMALL_BUSINESS",
                                    "website_state": "active" if canonical_lead.canonical_domain else "no_website",
                                    "ssl_valid": "Y" if canonical_lead.canonical_domain else "N",
                                    "facebook_ads_detected": "N",
                                }

                                classified_lead = MultiLabelClassificationAgent.classify_lead(lead_payload)
                                s_map = classified_lead.get("service_classifications", {})

                                for s_name, s_info in s_map.items():
                                    stype_upper = s_name.upper()
                                    eligible_str = "Y" if s_info.get("eligible") else "N"
                                    score_val = float(s_info.get("score", 0.0))
                                    reasons_json = json.dumps(s_info.get("reasons", []))

                                    existing_so = db.scalar(
                                        select(ServiceOpportunity).where(
                                            ServiceOpportunity.canonical_lead_id == canonical_lead.id,
                                            ServiceOpportunity.service_type == stype_upper,
                                        )
                                    )
                                    if existing_so:
                                        existing_so.eligible = eligible_str
                                        existing_so.score = score_val
                                        existing_so.reasons = reasons_json
                                    else:
                                        new_so = ServiceOpportunity(
                                            canonical_lead_id=canonical_lead.id,
                                            service_type=stype_upper,
                                            eligible=eligible_str,
                                            score=score_val,
                                            confidence=s_info.get("confidence", 0.85),
                                            reasons=reasons_json,
                                        )
                                        db.add(new_so)
                            except Exception as class_err:
                                logger.warning(f"[Classification] Service classification warning: {class_err}")

                        # Optional Genuineness and Learning Agent
                        try:
                            from backend.app.intelligence import GenuinenessAgent, LearningAgent

                            decision = GenuinenessAgent().evaluate_lead_genuineness(db, lead)
                            learning_agent = LearningAgent()
                            learning_agent.record_feature_snapshot(
                                db,
                                job.workspace_id,
                                lead.id,
                                {
                                    "source": rec.source,
                                    "niche": job.niche,
                                    "location": location,
                                    "website_exists": bool(final_website),
                                    "phone_exists": bool(final_phone),
                                },
                            )
                            learning_agent.record_prediction(
                                db,
                                job.workspace_id,
                                lead.id,
                                model_name="CatBoostLightGBMEnsemble",
                                model_version="v2.0_phase3_ensemble",
                                prediction=decision.overall_score,
                                confidence=decision.business_confidence,
                                decision=decision.decision,
                            )
                        except Exception as ml_err:
                            logger.warning(f"[Enrichment] Genuineness / Learning agent warning on {lead.id}: {ml_err}")

                        # Evaluate Lead Intelligence
                        from backend.app.intelligence.lead_intelligence import LeadIntelligenceEngine

                        contacts_ev = enr_res.contacts.__dict__ if enr_res and enr_res.contacts else {}
                        seo_ev = enr_res.seo.__dict__ if enr_res and enr_res.seo else {}
                        soc_ev = {"profiles": discovered_socials}
                        tech_ev = enr_res.technologies if enr_res else []
                        conf_ev = enr_res.conflicts if enr_res else {}
                        health_ev = enr_res.health.__dict__ if enr_res and enr_res.health else {}

                        intel_report = LeadIntelligenceEngine.evaluate_lead(
                            business_name=rec.business_name,
                            website=final_website,
                            phone=final_phone,
                            email=final_email,
                            category=rec.category or job.niche,
                            genuineness_score=gate_res.identity_confidence,
                            website_health=health_ev,
                            contacts_evidence=contacts_ev,
                            seo_evidence=seo_ev,
                            social_evidence=soc_ev,
                            technologies_evidence=tech_ev,
                            conflicts_evidence=conf_ev,
                        )

                        _upsert_evidence_record(
                            db=db,
                            workspace_id=job.workspace_id,
                            lead_id=lead.id,
                            canonical_lead_id=str(canonical_lead.id) if canonical_lead else None,
                            field_name="lead_intelligence",
                            status=intel_report.opportunity_category.value,
                            confidence_score=intel_report.overall_opportunity_score,
                            source="LEAD_INTELLIGENCE_ENGINE",
                            details={
                                "overall_opportunity_score": intel_report.overall_opportunity_score,
                                "opportunity_category": intel_report.opportunity_category.value,
                                "confidence_score": intel_report.confidence_score,
                                "contactability_score": intel_report.contactability_score,
                                "website_opportunity_score": intel_report.website_opportunity_score,
                                "seo_opportunity_score": intel_report.seo_opportunity_score,
                                "digital_presence_gap_score": intel_report.digital_presence_gap_score,
                                "top_reasons": intel_report.top_reasons,
                                "has_conflict": intel_report.has_conflict,
                            },
                        )
                    except Exception as intel_err:
                        logger.warning(
                            f"[Intelligence] Scoring warning for lead {lead.id}: {intel_err}"
                        )

                job.leads_scraped += 1
                job.progress_percent = min(
                    100.0, round((job.leads_scraped / job.target_lead_count) * 100, 1)
                )
                db.commit()

                prog_data = {
                    "event_type": "RAW_LEAD_CREATED",
                    "job_id": str(job.id),
                    "lead_id": str(canonical_lead.id),
                    "source": rec.source,
                    "status": job.status,
                    "leads_scraped": job.leads_scraped,
                    "target_lead_count": job.target_lead_count,
                    "progress_percent": job.progress_percent,
                    "discovered": job.discovered_count,
                    "valid": job.valid_count,
                    "new": job.new_count,
                    "updated": job.updated_count,
                    "duplicates": job.duplicate_count,
                    "failed": job.failed_count,
                }
                prog_data.update(get_job_metrics(job_id_str))
                publish_job_progress(str(job.id), prog_data)
            if r:
                r.sadd(f"job_success_sources:{job_id_str}", src_name)

            exec_log = ScrapeJobExecutionLog(
                job_id=job.id,
                source=src_name,
                query=f"{query_term} ({query_reason})",
                page=page_num,
                records_received=records_received,
                records_valid=records_valid,
                records_rejected=records_rejected,
                new_count=page_new,
                updated_count=page_updated,
                duplicate_count=page_duplicate,
                failed_count=page_failed,
            )
            db.add(exec_log)
            db.commit()

            pagination_state["page"] += 1


def finalize_job_status(db, job, job_id_str: str) -> None:
    from backend.app.websockets import publish_job_progress
    from backend.app.worker_concurrency import _global_limiter
    r = _global_limiter._redis_client

    failed_sources = []
    successful_sources = []
    if r:
        try:
            raw_failed = r.smembers(f"job_failed_sources:{job_id_str}") or set()
            raw_success = r.smembers(f"job_success_sources:{job_id_str}") or set()
            failed_sources = [s.decode() if isinstance(s, bytes) else s for s in raw_failed]
            successful_sources = [s.decode() if isinstance(s, bytes) else s for s in raw_success]
        except Exception:
            pass

    # Redis-absent / Execution log fallback
    if not failed_sources and not successful_sources:
        if job.failed_count > 0:
            failed_sources = ["inferred"]
        if (job.new_count + job.updated_count) > 0:
            successful_sources = ["inferred"]

        try:
            from backend.app.models import ScrapeJobExecutionLog
            exec_failures = db.query(ScrapeJobExecutionLog).filter(
                ScrapeJobExecutionLog.job_id == job.id,
                ScrapeJobExecutionLog.failed_count > 0,
            ).all()
            if exec_failures:
                failed_sources = [ef.source for ef in exec_failures]
        except Exception:
            pass

    # Database invariant check: verify and sync leads_scraped against actual persisted records
    db.refresh(job)
    try:
        from backend.app.models import Lead
        persisted_count = db.query(Lead).filter(Lead.job_id == job.id).count()
        job.leads_scraped = max(job.leads_scraped, persisted_count)
    except Exception as e:
        logger.warning(f"Failed to check persisted leads count for job {job.id}: {e}")

    target = job.target_lead_count or 1
    scraped = job.leads_scraped
    has_provider_failures = len(failed_sources) > 0

    if job.status in ("STOPPED_SAVED", "CANCELLED"):
        completion_reason = "CANCELLED" if job.status == "CANCELLED" else "STOPPED_SAVED"
    elif scraped >= target:
        job.status = "COMPLETED"
        completion_reason = "TARGET_REACHED"
    elif scraped == 0 and target > 0:
        job.status = "FAILED"
        if has_provider_failures and not successful_sources:
            completion_reason = "ALL_SOURCES_FAILED"
            job.error_message = "All provider sources failed."
        else:
            completion_reason = "DISCOVERY_EXHAUSTED"
            job.error_message = "Discovery exhausted. No valid leads found."
    else:  # 0 < scraped < target
        job.status = "PARTIAL"
        if has_provider_failures:
            completion_reason = "PARTIAL_SOURCE_FAILURE"
        else:
            completion_reason = "DISCOVERY_EXHAUSTED"

    job.completion_reason = completion_reason
    job.progress_percent = min(
        100.0, round((scraped / target) * 100, 1) if target > 0 else 0.0
    )
    if job.status not in ("STOPPED_SAVED", "CANCELLED"):
        db.commit()

    prog_data = {
        "event_type": f"JOB_{job.status}",
        "job_id": str(job.id),
        "status": job.status,
        "completion_reason": completion_reason,
        "error_message": job.error_message,
        "leads_scraped": scraped,
        "target_lead_count": target,
        "progress_percent": job.progress_percent,
        "discovered": job.discovered_count,
        "valid": job.valid_count,
        "new": job.new_count,
        "updated": job.updated_count,
        "duplicates": job.duplicate_count,
        "failed": job.failed_count,
        "fetched_count": getattr(job, 'fetched_count', 0),
    }
    prog_data.update(get_job_metrics(job_id_str))
    publish_job_progress(str(job.id), prog_data)



@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def scrape_source_query_task(self, job_id_str: str, plan: dict) -> None:
    """Independent concurrent discovery task for a single source + query plan."""
    import uuid
    from sqlalchemy import select
    from backend.app.database import SessionLocal
    from backend.app.models import ScrapeJob
    
    job_id = uuid.UUID(job_id_str)
    with SessionLocal() as db:
        job = db.scalar(select(ScrapeJob).where(ScrapeJob.id == job_id))
        if not job or job.status in ("COMPLETED", "PARTIAL", "CANCELLED", "STOPPED_SAVED"):
            return
            
        from backend.app.worker_concurrency import _global_limiter
        r = _global_limiter._redis_client
        source_name = plan["source"]
        
        # Concurrency limit per source
        source_concurrency_limit = 2
        if r:
            try:
                current_active = r.incr(f"active_src_tasks:{source_name}")
                if current_active > source_concurrency_limit:
                    r.decr(f"active_src_tasks:{source_name}")
                    self.retry(countdown=5)
                    return
            except Exception:
                pass
                
        try:
            execute_single_query_plan(db, job, plan)
        finally:
            if r:
                try:
                    r.decr(f"active_src_tasks:{source_name}")
                except Exception:
                    pass
                try:
                    remaining = r.decr(f"job_active_tasks:{job_id_str}")
                    if remaining <= 0:
                        finalize_job_status(db, job, job_id_str)
                except Exception as e:
                    logger.warning(f"Error decrementing active tasks: {e}")


def execute_scrape_job(self, job_id_str: str) -> None:
    """Asynchronous scrape job execution task initiating parallel source query tasks."""
    import uuid
    from sqlalchemy import select
    from backend.app.database import SessionLocal
    from backend.app.models import ScrapeJob
    from backend.app.websockets import publish_job_progress
    from backend.app.worker_concurrency import (
        ConcurrencyCapExceededError,
        workspace_concurrency_guard,
    )

    job_id = uuid.UUID(job_id_str)
    with SessionLocal() as db:
        job = db.scalar(select(ScrapeJob).where(ScrapeJob.id == job_id))
        if not job or job.status in ("COMPLETED", "PARTIAL", "CANCELLED", "STOPPED_SAVED"):
            return

        try:
            with workspace_concurrency_guard(str(job.workspace_id)):
                job.status = "RUNNING"
                db.commit()
                publish_job_progress(
                    str(job.id),
                    {
                        "event_type": "JOB_STARTED",
                        "job_id": str(job.id),
                        "status": job.status,
                        "leads_scraped": job.leads_scraped,
                        "target_lead_count": job.target_lead_count,
                        "progress_percent": job.progress_percent,
                    },
                )

                from backend.app.orchestration.discovery_orchestrator import DiscoveryOrchestrator
                connectors = get_connectors()
                orchestrator = DiscoveryOrchestrator(
                    db=db,
                    job=job,
                    connectors=connectors,
                    max_request_budget=60,
                )
                orchestrator.run_discovery()

        except ConcurrencyCapExceededError as cap_err:
            db.rollback()
            job.status = "FAILED"
            job.error_message = str(cap_err)
            db.commit()
            publish_job_progress(
                str(job.id),
                {
                    "event_type": "JOB_FAILED",
                    "job_id": str(job.id),
                    "status": job.status,
                    "leads_scraped": job.leads_scraped,
                    "target_lead_count": job.target_lead_count,
                    "progress_percent": job.progress_percent,
                    "discovered": job.discovered_count,
                    "valid": job.valid_count,
                    "new": job.new_count,
                    "updated": job.updated_count,
                    "duplicates": job.duplicate_count,
                    "failed": job.failed_count,
                    "error_message": job.error_message,
                },
            )
            if self and hasattr(self, "request") and self.request and self.request.retries < self.max_retries:
                raise self.retry(exc=cap_err, countdown=10) from cap_err
        except Exception as e:
            db.rollback()
            import logging
            logging.error(f"Unhandled exception in execute_scrape_job: {e}", exc_info=True)
            job.status = "FAILED"
            job.error_message = f"Internal orchestrator error: {str(e)}"
            db.commit()
            publish_job_progress(
                str(job.id),
                {
                    "event_type": "JOB_FAILED",
                    "job_id": str(job.id),
                    "status": job.status,
                    "leads_scraped": job.leads_scraped,
                    "target_lead_count": job.target_lead_count,
                    "progress_percent": job.progress_percent,
                    "error_message": job.error_message,
                },
            )
            raise e
        except Exception as error:
            db.rollback()
            job.status = "FAILED"
            job.error_message = str(error)
            db.commit()
            publish_job_progress(
                str(job.id),
                {
                    "event_type": "JOB_FAILED",
                    "job_id": str(job.id),
                    "status": job.status,
                    "leads_scraped": job.leads_scraped,
                    "target_lead_count": job.target_lead_count,
                    "progress_percent": job.progress_percent,
                    "discovered": job.discovered_count,
                    "valid": job.valid_count,
                    "new": job.new_count,
                    "updated": job.updated_count,
                    "duplicates": job.duplicate_count,
                    "failed": job.failed_count,
                    "error_message": job.error_message,
                },
            )
            if self and hasattr(self, "request") and self.request and self.request.retries < self.max_retries:
                raise self.retry(exc=error, countdown=5 * (2**self.request.retries)) from error


@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)
def process_scrape_job_task(self, job_id_str: str) -> None:
    """Asynchronous scrape job execution task wrapper."""
    execute_scrape_job(self, job_id_str)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)
def enrich_lead_task(self, lead_id_str: str) -> None:
    """Asynchronous background task for verifying lead details with field-aware Progressive Enrichment."""
    import uuid

    from sqlalchemy import select

    from backend.app.database import SessionLocal
    from backend.app.enrichment import (
        ConfidenceScorer,
        EmailVerifier,
        PhoneValidator,
        WebsiteValidator,
    )
    from backend.app.models import EvidenceRecord, Lead, SourceRecord
    from backend.app.models_phase2 import LeadObservation

    lead_id = uuid.UUID(lead_id_str)
    with SessionLocal() as db:
        lead = db.scalar(select(Lead).where(Lead.id == lead_id, Lead.deleted_at.is_(None)))
        if not lead:
            return

        # Find matching canonical_lead_id
        canonical_lead_id = None
        source_rec = db.scalar(select(SourceRecord).where(SourceRecord.lead_id == lead.id))
        if source_rec:
            obs = db.scalar(
                select(LeadObservation).where(
                    LeadObservation.source_name == source_rec.source,
                    LeadObservation.source_record_id == source_rec.source_id,
                )
            )
            if obs:
                canonical_lead_id = obs.canonical_lead_id

        # Field-Aware Selection: check if email/phone/website are already populated with high confidence (>= 80)
        highly_verified_fields = set()
        if canonical_lead_id:
            existing_evidence = db.scalars(
                select(EvidenceRecord).where(
                    EvidenceRecord.canonical_lead_id == canonical_lead_id,
                    EvidenceRecord.status == "VERIFIED",
                    EvidenceRecord.confidence_score >= 80,
                )
            ).all()
            highly_verified_fields = {ev.field_name for ev in existing_evidence}

        # Get lead observations for canonical lead to compute dynamic source confidence
        observations = []
        if canonical_lead_id:
            observations = list(db.scalars(
                select(LeadObservation).where(LeadObservation.canonical_lead_id == canonical_lead_id)
            ).all())

        from backend.app.intelligence.source_confidence import SourceConfidenceSystem

        web_result = None
        if lead.website and "website" not in highly_verified_fields:
            validator = WebsiteValidator()
            web_result = validator.validate(lead.website, lead.business_name)
            conf_val = SourceConfidenceSystem.calculate_field_confidence(
                db, "website", lead.website, observations,
                validation_passed=web_result.is_valid,
                validation_score=ConfidenceScorer.compute_website_confidence(web_result)
            )
            ev_web = EvidenceRecord(
                workspace_id=lead.workspace_id,
                lead_id=lead.id,
                canonical_lead_id=canonical_lead_id,
                field_name="website",
                status="VERIFIED" if web_result.is_valid else "FAILED",
                confidence_score=conf_val,
                source="website_validator",
                details=web_result.model_dump(),
            )
            db.add(ev_web)

        email_result = None
        if lead.email and "email" not in highly_verified_fields:
            verifier = EmailVerifier()
            email_result = verifier.verify(lead.email, lead.business_name, lead.website)
            conf_val = SourceConfidenceSystem.calculate_field_confidence(
                db, "email", lead.email, observations,
                validation_passed=email_result.is_valid,
                validation_score=ConfidenceScorer.compute_email_confidence(email_result)
            )
            ev_email = EvidenceRecord(
                workspace_id=lead.workspace_id,
                lead_id=lead.id,
                canonical_lead_id=canonical_lead_id,
                field_name="email",
                status="VERIFIED" if email_result.is_valid else "FAILED",
                confidence_score=conf_val,
                source="email_verifier",
                details=email_result.model_dump(),
            )
            db.add(ev_email)

        phone_result = None
        if lead.phone and "phone" not in highly_verified_fields:
            p_validator = PhoneValidator()
            phone_result = p_validator.validate(lead.phone)
            if phone_result.is_valid and phone_result.e164_format:
                lead.phone = phone_result.e164_format
            conf_val = SourceConfidenceSystem.calculate_field_confidence(
                db, "phone", lead.phone, observations,
                validation_passed=phone_result.is_valid,
                validation_score=ConfidenceScorer.compute_phone_confidence(phone_result)
            )
            ev_phone = EvidenceRecord(
                workspace_id=lead.workspace_id,
                lead_id=lead.id,
                canonical_lead_id=canonical_lead_id,
                field_name="phone",
                status="VERIFIED" if phone_result.is_valid else "FAILED",
                confidence_score=conf_val,
                source="phone_validator",
                details=phone_result.model_dump(),
            )
            db.add(ev_phone)

        db.commit()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)
def qualify_lead_task(self, lead_id_str: str) -> None:
    """Asynchronous background task to qualify and score a lead record for agency services."""
    import uuid

    from sqlalchemy import select

    from backend.app.database import SessionLocal
    from backend.app.intelligence import DeterministicRuleEngine
    from backend.app.models import Lead

    lead_id = uuid.UUID(lead_id_str)
    with SessionLocal() as db:
        lead = db.scalar(select(Lead).where(Lead.id == lead_id, Lead.deleted_at.is_(None)))
        if not lead:
            return

        engine = DeterministicRuleEngine()
        engine.qualify_lead(db, lead)

        from backend.app.intelligence import CompletenessChecker
        checker = CompletenessChecker()
        if checker.check_completeness(lead, db):
            lead.verification_status = "QUALIFIED"
        else:
            lead.verification_status = "INCOMPLETE"
        db.commit()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)
def dispatch_campaign_task(self, campaign_id_str: str) -> None:
    """Asynchronous background task to send cold emails to workspace leads."""
    import uuid
    from datetime import UTC, datetime

    from sqlalchemy import select

    from backend.app.database import SessionLocal
    from backend.app.metrics import MetricsRegistry
    from backend.app.models import EmailDispatch, Lead, OutreachCampaign
    from backend.app.outreach import EmailDispatcher

    campaign_id = uuid.UUID(campaign_id_str)
    with SessionLocal() as db:
        campaign = db.scalar(select(OutreachCampaign).where(OutreachCampaign.id == campaign_id))
        if not campaign:
            return

        campaign.status = "RUNNING"
        db.commit()

        leads = list(
            db.scalars(
                select(Lead).where(
                    Lead.workspace_id == campaign.workspace_id, Lead.deleted_at.is_(None)
                )
            )
        )

        dispatcher = EmailDispatcher(provider="mock")
        for lead in leads:
            res = dispatcher.send_email(db, campaign, lead)
            disp_record = EmailDispatch(
                workspace_id=campaign.workspace_id,
                campaign_id=campaign.id,
                lead_id=lead.id,
                recipient_email=res.recipient_email,
                status=res.status,
                sent_at=datetime.now(UTC) if res.success else None,
                error_message=res.error_message,
            )
            db.add(disp_record)
            MetricsRegistry.increment_counter("email_dispatches_total")

        campaign.status = "COMPLETED"
        db.commit()
