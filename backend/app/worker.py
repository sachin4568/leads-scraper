from __future__ import annotations

import logging

from celery import Celery

from backend.app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


def get_broker_url() -> str:
    url = settings.redis_url.get_secret_value()
    try:
        import redis

        r = redis.Redis.from_url(url, socket_timeout=0.5, socket_connect_timeout=0.5)
        r.ping()
        return url
    except Exception:
        logger.warning(
            "Redis connection refused on %s. Falling back to in-memory Celery broker (memory://).",
            url,
        )
        return "memory://"


celery_app = Celery("lead_intelligence", broker=get_broker_url())
celery_app.conf.update(task_acks_late=True, task_reject_on_worker_lost=True)


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
            if reqs_executed >= 100:
                logger.warning(f"Crawl budget limit of 100 requests reached. Aborting.")
                pagination_state["has_more"] = False
                break

            cursor = pagination_state.get("next_page_token")
            if cursor:
                if cursor in pagination_state["seen_cursors"]:
                    logger.warning(f"[Pagination] Duplicate cursor detected: {cursor}. Aborting.")
                    break
                pagination_state["seen_cursors"].add(cursor)

            records = []
            retry_count = 0
            max_retries = 3
            
            while retry_count <= max_retries:
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
                    break
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
                    elif "500" in err_str or "server error" in err_str:
                        classification = "SERVER_ERROR"
                    elif "json" in err_str or "decode" in err_str:
                        classification = "MALFORMED_RESPONSE"
                    elif "empty" in err_str:
                        classification = "EMPTY_RESPONSE"
                        
                    is_transient = classification in ("TIMEOUT", "SERVER_ERROR", "RATE_LIMITED", "UNAVAILABLE_PROVIDER")
                    if is_transient and retry_count < max_retries:
                        retry_count += 1
                        track_metric(job_id_str, "retries")
                        time.sleep(2 ** retry_count)
                        continue
                    else:
                        logger.error(f"[Failure] Permanent failure '{classification}' for {src_name}: {src_err}")
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
                        return

            records_received = len(records)
            track_metric(job_id_str, "results_received", records_received)
            
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

            for rec in records:
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

                if (
                    not rec.business_name
                    or not str(rec.business_name).strip()
                    or rec.business_name.lower() == "unknown business"
                ):
                    records_rejected += 1
                    job.failed_count += 1
                    page_failed += 1
                    continue

                records_valid += 1
                job.valid_count += 1

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

                existing_src = db.scalar(
                    select(SourceRecord).where(
                        SourceRecord.source == rec.source,
                        SourceRecord.source_id == rec.source_id,
                    )
                )
                if not existing_src:
                    lead = Lead(
                        workspace_id=job.workspace_id,
                        job_id=job.id,
                        business_name=rec.business_name,
                        website=rec.website,
                        phone=rec.phone,
                        notes=f"Source: {rec.source}",
                        raw_status="PERSISTED",
                        verification_status="VERIFIED"
                        if (rec.website or rec.phone)
                        else "UNVERIFIED",
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
                            "website_exists": bool(rec.website),
                            "phone_exists": bool(rec.phone),
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

                try:
                    track_metric(job_id_str, "enrichment_requests")
                    enrichment_engine.enrich_lead(canonical_lead.id, raw_lead)
                except Exception as enrich_err:
                    logger.warning(
                        f"Auto enrichment warning on canonical lead {canonical_lead.id}: {enrich_err}"
                    )

                try:
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
                        "website_state": "active"
                        if canonical_lead.canonical_domain
                        else "no_website",
                        "ssl_valid": "Y" if canonical_lead.canonical_domain else "N",
                        "facebook_ads_detected": "N",
                    }

                    classified_lead = MultiLabelClassificationAgent.classify_lead(
                        lead_payload
                    )
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
                    logger.error(
                        f"Service classification error on {canonical_lead.id}: {class_err}"
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
            failed_sources = list(r.smembers(f"job_failed_sources:{job_id_str}") or [])
            successful_sources = list(r.smembers(f"job_success_sources:{job_id_str}") or [])
        except Exception:
            pass

    db.refresh(job)
    if job.status not in ("STOPPED_SAVED", "CANCELLED"):
        if len(failed_sources) > 0 and len(successful_sources) > 0:
            job.status = "PARTIAL_SUCCESS"
        elif len(failed_sources) > 0 and len(successful_sources) == 0:
            job.status = "FAILED"
        else:
            if job.leads_scraped >= job.target_lead_count:
                job.status = "COMPLETED"
            else:
                job.status = "PARTIAL"

        job.progress_percent = min(
            100.0, round((job.leads_scraped / job.target_lead_count) * 100, 1)
        )
        db.commit()

    prog_data = {
        "event_type": f"JOB_{job.status}",
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

                target_sources = job.sources or ["google_maps"]
                location = job.state or job.region or job.country

                from backend.app.intelligence.query_expansion import QueryExpansionEngine
                from backend.app.intelligence.adaptive_discovery import AdaptiveDiscoveryEngine

                search_plan_base = QueryExpansionEngine().expand_query(job.niche, location)

                # Build Cartesian query plans
                query_plans = []
                for src in target_sources:
                    for item in search_plan_base:
                        q_term = item["query"]
                        q_reason = item.get("reason", "unknown")
                        
                        reason_lower = q_reason.lower()
                        if "exact" in reason_lower:
                            priority = 1
                        elif "plural" in reason_lower or "singular" in reason_lower:
                            priority = 2
                        elif "synonym" in reason_lower or "service" in reason_lower or "subcategory" in reason_lower:
                            priority = 3
                        else:
                            priority = 4
                            
                        hist_score = AdaptiveDiscoveryEngine.get_query_score(db, q_term)
                        query_plans.append({
                            "query": q_term,
                            "reason": q_reason,
                            "source": src,
                            "niche": job.niche,
                            "location": location,
                            "priority": priority,
                            "historical_score": hist_score
                        })
                        
                # Prioritize plans
                sorted_plans = sorted(
                    query_plans,
                    key=lambda x: (x["historical_score"], -x["priority"]),
                    reverse=True
                )

                from backend.app.worker_concurrency import _global_limiter
                r = _global_limiter._redis_client
                import os
                is_test = os.getenv("APP_ENV") == "test"

                if r and not is_test:
                    try:
                        # Clear old metrics
                        r.delete(f"job_metrics:{job_id_str}")
                        r.delete(f"job_failed_sources:{job_id_str}")
                        r.delete(f"job_success_sources:{job_id_str}")
                        
                        r.set(f"job_active_tasks:{job_id_str}", len(sorted_plans))
                        for plan in sorted_plans:
                            scrape_source_query_task.delay(job_id_str, plan)
                    except Exception as e:
                        logger.warning(f"Failed to queue Celery tasks: {e}. Executing inline.")
                        r = None

                if not r:
                    logger.info("Executing plans sequentially inline.")
                    for plan in sorted_plans:
                        execute_single_query_plan(db, job, plan)
                    finalize_job_status(db, job, job_id_str)

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
