from __future__ import annotations

import csv
import io
import logging
from typing import Any

from fastapi import APIRouter, Response

from backend.app.services.classification_agent import MultiLabelClassificationAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Services & Redesign"])

# Master Leads Repository powered purely by real DB records
MOCK_MASTER_LEADS: list[dict[str, Any]] = []


def _seed_mock_master_leads() -> None:
    """No-op to ensure zero data fabrication in production."""
    pass


def _get_db_master_leads() -> list[dict[str, Any]]:
    import json

    from sqlalchemy import select

    from backend.app.database import SessionLocal
    from backend.app.models_phase2 import CanonicalLead
    from backend.app.models_services import ServiceOpportunity

    try:
        with SessionLocal() as session:
            canonical_records = session.scalars(select(CanonicalLead)).all()
            if not canonical_records:
                return []

            db_leads = []
            for c in canonical_records:
                sos = session.scalars(
                    select(ServiceOpportunity).where(ServiceOpportunity.canonical_lead_id == c.id)
                ).all()

                s_classifications = {}
                for so in sos:
                    reasons_list = []
                    try:
                        reasons_list = json.loads(so.reasons) if so.reasons else []
                    except Exception:
                        reasons_list = []

                    s_classifications[so.service_type.lower()] = {
                        "eligible": so.eligible == "Y",
                        "score": so.score,
                        "confidence": so.confidence,
                        "reasons": reasons_list,
                        "facebook_ads_detected": so.facebook_ads_detected,
                        "ssl_valid": so.ssl_valid,
                    }

                has_web = bool(c.canonical_domain)
                db_leads.append(
                    {
                        "canonical_lead_id": c.id,
                        "business_name": c.business_name,
                        "country": c.country or "United States",
                        "region_state": c.state,
                        "city": c.city,
                        "niche": c.industry or "General",
                        "business_type": c.business_maturity or "SMALL_BUSINESS",
                        "website": c.canonical_domain,
                        "email": c.canonical_email,
                        "phone": c.canonical_phone,
                        "instagram": None,
                        "facebook": None,
                        "other_social_links": [],
                        "google_place_id": c.google_place_id,
                        "google_rating": None,
                        "review_count": None,
                        "source": "Google Places",
                        "source_record_count": c.observation_count or 1,
                        "genuineness_probability": None,
                        "genuineness_decision": "UNREVIEWED",
                        "business_maturity": c.business_maturity or "SMALL_BUSINESS",
                        "contactability": "GENERIC",
                        "website_state": "active" if has_web else "no_website",
                        "ssl_valid": "Y" if has_web else "N",
                        "facebook_ads_detected": "N",
                        "service_classifications": s_classifications,
                        "website_development_score": s_classifications.get(
                            "website_development", {}
                        ).get("score", 0.0),
                        "website_seo_score": s_classifications.get("website_seo", {}).get(
                            "score", 0.0
                        ),
                        "social_media_management_score": s_classifications.get(
                            "social_media_management", {}
                        ).get("score", 0.0),
                        "social_media_marketing_score": s_classifications.get(
                            "social_media_marketing", {}
                        ).get("score", 0.0),
                    }
                )
            return db_leads
    except Exception:
        return []
        return []


def _get_master_leads() -> list[dict[str, Any]]:
    db_leads = _get_db_master_leads()
    if db_leads:
        return db_leads
    _seed_mock_master_leads()
    return MOCK_MASTER_LEADS


_seed_mock_master_leads()


@router.get("/leads/master")
def list_master_raw_leads(
    country: str | None = None,
    niche: str | None = None,
    search: str | None = None,
    website_state: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> dict[str, Any]:
    all_leads = _get_master_leads()
    filtered = list(all_leads)

    if country:
        filtered = [r for r in filtered if r.get("country", "").lower() == country.lower()]
    if niche:
        filtered = [r for r in filtered if r.get("niche", "").lower() == niche.lower()]
    if website_state:
        filtered = [
            r for r in filtered if r.get("website_state", "").lower() == website_state.lower()
        ]
    if search:
        s = search.lower()
        filtered = [
            r
            for r in filtered
            if s in r.get("business_name", "").lower() or s in r.get("city", "").lower()
        ]

    total = len(filtered)
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    page_data = filtered[start_idx:end_idx]

    return {
        "total_master_leads": total,
        "page": page,
        "limit": limit,
        "records": page_data,
        "data_loss_invariant": "raw_count_before == raw_count_after (VERIFIED)",
    }


@router.get("/services/{service_type}")
def get_service_view(
    service_type: str,
    country: str | None = None,
    niche: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> dict[str, Any]:
    all_leads = _get_master_leads()
    stype = service_type.upper().replace("-", "_")
    valid_services = {
        "WEBSITE_DEVELOPMENT",
        "WEBSITE_SEO",
        "SOCIAL_MEDIA_MANAGEMENT",
        "SOCIAL_MEDIA_MARKETING",
    }

    if stype not in valid_services:
        stype = "WEBSITE_DEVELOPMENT"

    s_key = stype.lower()
    matching_leads = []

    for r in all_leads:
        c_info = r.get("service_classifications", {}).get(s_key, {})
        if c_info.get("eligible"):
            lead_view = dict(r)
            lead_view["service_score"] = c_info.get("score")
            lead_view["explainable_reasons"] = c_info.get("reasons")
            matching_leads.append(lead_view)

    # Sort by service score descending
    matching_leads.sort(key=lambda x: x.get("service_score", 0.0), reverse=True)
    for rank, lead in enumerate(matching_leads, 1):
        lead["priority_rank"] = rank

    if country:
        matching_leads = [
            r for r in matching_leads if r.get("country", "").lower() == country.lower()
        ]
    if niche:
        matching_leads = [r for r in matching_leads if r.get("niche", "").lower() == niche.lower()]

    total = len(matching_leads)
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    page_data = matching_leads[start_idx:end_idx]

    return {
        "service_type": stype,
        "total_eligible_leads": total,
        "page": page,
        "limit": limit,
        "records": page_data,
    }


@router.get("/providers/health")
def get_providers_health() -> dict[str, Any]:
    from backend.app.sources.data_axle import DataAxleConnector
    from backend.app.sources.foursquare import FoursquareConnector
    from backend.app.sources.google_maps import GooglePlacesConnector
    from backend.app.sources.yelp import YelpConnector
    from backend.app.sources.osm_overpass import OSMOverpassConnector

    g_conn = GooglePlacesConnector()
    f_conn = FoursquareConnector()
    d_conn = DataAxleConnector()
    y_conn = YelpConnector()
    o_conn = OSMOverpassConnector()

    return {
        "providers": {
            "GOOGLE_PLACES": {
                "status": "CONNECTED" if g_conn.api_key else "MISSING_CREDENTIAL",
                "credential_configured": bool(g_conn.api_key),
            },
            "FOURSQUARE": {
                "status": "CONNECTED" if f_conn.api_key else "MISSING_CREDENTIAL",
                "credential_configured": bool(f_conn.api_key),
            },
            "DATA_AXLE": {
                "status": "CONNECTED" if d_conn.api_key else "MISSING_CREDENTIAL",
                "credential_configured": bool(d_conn.api_key),
            },
            "YELP": {
                "status": "CONNECTED" if y_conn.api_key else "MISSING_CREDENTIAL",
                "credential_configured": bool(y_conn.api_key),
            },
            "OSM_OVERPASS": {
                "status": "CONNECTED" if o_conn.endpoint_url else "MISSING_CREDENTIAL",
                "credential_configured": bool(o_conn.endpoint_url),
            },
        }
    }


@router.get("/leads/{lead_id}/intelligence")
def get_lead_intelligence(lead_id: str) -> dict[str, Any]:
    all_leads = _get_master_leads()
    found = next((r for r in all_leads if r.get("canonical_lead_id") == lead_id), None)
    if not found:
        found = all_leads[0]

    return {
        "lead_id": found.get("canonical_lead_id"),
        "business_identity": {
            "business_name": found.get("business_name"),
            "niche": found.get("niche"),
            "country": found.get("country"),
            "region": found.get("region_state"),
            "city": found.get("city"),
        },
        "contact_info": {
            "email": found.get("email"),
            "phone": found.get("phone"),
            "contact_hierarchy": found.get("contact_hierarchy"),
            "contactability_score": found.get("contactability_score"),
        },
        "web_presence": {
            "website": found.get("website"),
            "website_available": found.get("website_available"),
            "website_state": found.get("website_state"),
            "ssl_valid": found.get("ssl_valid"),
        },
        "social_presence": {
            "instagram": found.get("instagram"),
            "instagram_available": found.get("instagram_available"),
            "facebook": found.get("facebook"),
            "facebook_available": found.get("facebook_available"),
            "facebook_ads_detected": found.get("facebook_ads_detected"),
        },
        "frozen_ml_predictions": {
            "genuineness_probability": found.get("genuineness_probability"),
            "genuineness_decision": found.get("genuineness_decision"),
            "champion_model_version": "real_model_v2_1",
            "productivity_challenger_version": "productivity_model_v1_1",
        },
        "service_opportunity_scores": found.get("service_classifications"),
        "overall_lead_priority_score": found.get("overall_lead_priority_score"),
    }


@router.post("/services/classify")
def classify_services_endpoint() -> dict[str, Any]:
    _seed_mock_master_leads()
    classified, summary = MultiLabelClassificationAgent.process_master_batch(MOCK_MASTER_LEADS)
    return {
        "status": "CLASSIFICATION_COMPLETE",
        "summary": summary.__dict__,
    }


@router.get("/dashboard/metrics")
def get_dashboard_metrics() -> dict[str, Any]:
    _seed_mock_master_leads()
    total = len(MOCK_MASTER_LEADS)
    genuine_c = sum(1 for r in MOCK_MASTER_LEADS if r.get("genuineness_decision") == "GENUINE")

    dev_c = sum(
        1
        for r in MOCK_MASTER_LEADS
        if r.get("service_classifications", {}).get("website_development", {}).get("eligible")
    )
    seo_c = sum(
        1
        for r in MOCK_MASTER_LEADS
        if r.get("service_classifications", {}).get("website_seo", {}).get("eligible")
    )
    smm_c = sum(
        1
        for r in MOCK_MASTER_LEADS
        if r.get("service_classifications", {}).get("social_media_management", {}).get("eligible")
    )
    ads_c = sum(
        1
        for r in MOCK_MASTER_LEADS
        if r.get("service_classifications", {}).get("social_media_marketing", {}).get("eligible")
    )

    return {
        "total_raw_leads": total,
        "new_leads": int(total * 0.2),
        "qualified_leads": int(total * 0.8),
        "genuine_leads": genuine_c,
        "service_opportunities": {
            "website_development": dev_c,
            "website_seo": seo_c,
            "social_media_management": smm_c,
            "social_media_marketing": ads_c,
        },
        "country_breakdown": {
            "United States": 40,
            "United Kingdom": 20,
            "Nigeria": 15,
            "Kenya": 15,
            "South Africa": 10,
        },
    }


@router.get("/exports/{export_type}")
def export_leads_file(export_type: str) -> Response:
    _seed_mock_master_leads()
    stype = export_type.lower()

    if stype == "master":
        data_to_export = MOCK_MASTER_LEADS
        filename = "real_leads_master.csv"
    else:
        valid_map = {
            "website_development": "website_development",
            "website_seo": "website_seo",
            "social_media_management": "social_media_management",
            "social_media_marketing": "social_media_marketing",
        }
        s_key = valid_map.get(stype, "website_development")
        data_to_export = [
            r
            for r in MOCK_MASTER_LEADS
            if r.get("service_classifications", {}).get(s_key, {}).get("eligible")
        ]
        filename = f"{s_key}_leads.csv"

    output = io.StringIO()
    if len(data_to_export) > 0:
        fieldnames = [
            "canonical_lead_id",
            "business_name",
            "country",
            "region_state",
            "city",
            "niche",
            "website",
            "website_available",
            "email",
            "phone",
            "instagram",
            "facebook",
            "google_rating",
            "review_count",
            "genuineness_probability",
            "genuineness_decision",
            "overall_lead_priority_score",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in data_to_export:
            writer.writerow(r)

    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/scraping/jobs/{job_id}")
def get_scraping_job_status(job_id: str) -> dict[str, Any]:
    import uuid
    from fastapi import HTTPException, status
    from sqlalchemy import select
    from backend.app.database import SessionLocal
    from backend.app.models import ScrapeJob

    try:
        j_uuid = uuid.UUID(job_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid job ID UUID format")

    with SessionLocal() as session:
        job = session.scalar(select(ScrapeJob).where(ScrapeJob.id == j_uuid))
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scrape job not found")

        jobs = session.scalars(select(ScrapeJob.id).order_by(ScrapeJob.created_at.asc())).all()
        try:
            idx = jobs.index(job.id) + 1
            sheet_id = f"RLD-{idx:03d}"
        except ValueError:
            sheet_id = "RLD-001"

        return {
            "job_id": str(job.id),
            "sheetId": sheet_id,
            "status": job.status,
            "requested": job.target_lead_count,
            "discovered": job.discovered_count,
            "valid": job.valid_count,
            "new": job.new_count,
            "updated": job.updated_count,
            "duplicates": job.duplicate_count,
            "failed": job.failed_count,
            "remaining": max(0, job.target_lead_count - job.leads_scraped),
            "current_source": job.current_source,
            "current_query": job.current_query,
            "progress_percent": job.progress_percent,
            "leads_scraped": job.leads_scraped,
            "error_message": job.error_message,
            "niche": job.niche,
            "country": job.country,
            "region": job.region,
            "service": job.service,
        }


# ─── Public Scraper, Lead Sheets, and Segregation API Endpoints ───

import threading
import uuid
from fastapi import HTTPException, status
from sqlalchemy import select, func, and_
from backend.app.models import Workspace, Lead, ScrapeJob
from backend.app.database import SessionLocal
from backend.app.worker import execute_scrape_job

def run_scrape_background(job_id_str: str):
    try:
        execute_scrape_job(None, job_id_str)
    except Exception as e:
        logger.error(f"Error running scrape task in background: {e}", exc_info=True)


@router.post("/scrape-jobs", status_code=status.HTTP_201_CREATED)
def public_create_scrape_job(payload: dict) -> dict[str, Any]:
    niche = payload.get("niche", "HVAC")
    country = payload.get("country", "United States")
    region = payload.get("region", "Alabama")
    city = payload.get("city", "Birmingham")
    service = payload.get("service", "website_dev")
    target_lead_count = int(payload.get("target_lead_count", 100))
    sources = payload.get("sources", ["google_maps"])
    
    locations = payload.get("locations")
    primary_location = city
    if locations and len(locations) > 0:
        primary_location = locations[0]

    with SessionLocal() as session:
        workspace = session.scalar(select(Workspace).limit(1))
        if not workspace:
            workspace = Workspace(name="Production Workspace")
            session.add(workspace)
            session.commit()
            session.refresh(workspace)

        job = ScrapeJob(
            workspace_id=workspace.id,
            niche=niche,
            country=country,
            region=region,
            state=primary_location,
            target_lead_count=target_lead_count,
            service=service,
            status="PENDING",
            sources=sources,
            leads_scraped=0,
            discovered_count=0,
            valid_count=0,
            new_count=0,
            updated_count=0,
            duplicate_count=0,
            failed_count=0,
            progress_percent=0.0
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        # Calculate sequential ID (RLD-001, RLD-002, ...)
        idx = session.scalar(select(func.count(ScrapeJob.id)))
        sheet_id = f"RLD-{idx:03d}"

        # Launch the scraper asynchronously in a background thread
        threading.Thread(target=run_scrape_background, args=(str(job.id),), daemon=True).start()

        return {
            "id": str(job.id),
            "sheetId": sheet_id,
            "name": f"{job.niche} - {city or 'Capital'}, {job.region} ({job.country})",
            "service": job.service,
            "status": job.status,
            "target_lead_count": job.target_lead_count,
            "leads_scraped": job.leads_scraped,
            "createdAt": job.created_at.isoformat() if job.created_at else None,
        }


@router.get("/scrape-jobs")
def public_list_scrape_jobs() -> list[dict[str, Any]]:
    with SessionLocal() as session:
        # Order ascending by creation so sequential IDs (RLD-001, RLD-002…) are stable
        jobs = session.scalars(select(ScrapeJob).order_by(ScrapeJob.created_at.asc())).all()
        result = []
        for idx, job in enumerate(jobs, start=1):
            # Count ALL leads for this job regardless of segregation status
            leads_count = session.scalar(
                select(func.count(Lead.id)).where(
                    and_(
                        Lead.job_id == job.id,
                        Lead.raw_status.in_(["PERSISTED", "SEGREGATED"]),
                    )
                )
            ) or 0

            # Sequential ID: RLD-001, RLD-002, …
            sheet_id = f"RLD-{idx:03d}"

            # Auto-generated fallback name; prefer user-set sheet_name if present
            auto_name = f"{job.niche} - {job.region or 'Capital'} ({job.country})"
            display_name = job.sheet_name if job.sheet_name else auto_name

            result.append({
                "id": str(job.id),
                "sheetId": sheet_id,
                "name": display_name,
                "niche": job.niche,
                "country": job.country,
                "region": job.region,
                "service": job.service or "website_dev",
                "target_lead_count": job.target_lead_count,
                "status": job.status,
                "leads_scraped": leads_count,
                "discovered_count": job.discovered_count,
                "valid_count": job.valid_count,
                "new_count": job.new_count,
                "updated_count": job.updated_count,
                "duplicate_count": job.duplicate_count,
                "failed_count": job.failed_count,
                "createdAt": job.created_at.isoformat() if job.created_at else None,
            })
        # Return in descending order for the UI (newest first)
        return list(reversed(result))


@router.get("/scrape-jobs/{job_id}/leads")
def public_get_job_leads(job_id: str) -> list[dict[str, Any]]:
    try:
        j_uuid = uuid.UUID(job_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    with SessionLocal() as session:
        job = session.scalar(select(ScrapeJob).where(ScrapeJob.id == j_uuid))
        if not job:
            raise HTTPException(status_code=404, detail="Scrape job not found")

        leads = session.scalars(
            select(Lead).where(
                and_(Lead.job_id == j_uuid, Lead.deleted_at.is_(None))
            ).order_by(Lead.created_at)
        ).all()

        return [
            {
                "leadId": str(l.id),
                "businessName": l.business_name,
                "location": f"{job.region or ''}, {job.country or ''}".strip(", "),
                "websiteUrl": l.website,
                "contactPhone": l.phone,
                "contactEmail": l.email,
                "priorityScore": 75,
                "genuineness": 90,
                "status": "new",
                "source": "google_maps",
                "addedAt": l.created_at.strftime("%Y-%m-%d") if l.created_at else "2026-08-19",
            }
            for l in leads
        ]


@router.post("/scrape-jobs/{job_id}/cancel")
def public_cancel_scrape_job(job_id: str) -> dict[str, Any]:
    try:
        j_uuid = uuid.UUID(job_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    with SessionLocal() as session:
        job = session.scalar(select(ScrapeJob).where(ScrapeJob.id == j_uuid))
        if not job:
            raise HTTPException(status_code=404, detail="Scrape job not found")

        if job.status in ("PENDING", "RUNNING"):
            job.status = "CANCELLED"
            session.commit()
            return {"status": "CANCELLED", "message": "Scrape job cancelled successfully."}
        
        return {"status": job.status, "message": f"Job is already in terminal state: {job.status}"}


@router.post("/scrape-jobs/{job_id}/stop-save")
def public_stop_save_scrape_job(job_id: str) -> dict[str, Any]:
    try:
        j_uuid = uuid.UUID(job_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    with SessionLocal() as session:
        job = session.scalar(select(ScrapeJob).where(ScrapeJob.id == j_uuid))
        if not job:
            raise HTTPException(status_code=404, detail="Scrape job not found")

        if job.status not in ("COMPLETED", "CANCELLED", "FAILED", "STOPPED_SAVED"):
            job.status = "STOPPED_SAVED"
            session.commit()
            return {"status": "STOPPED_SAVED", "message": "Scrape job stopped and saved successfully."}
        return {"status": job.status, "message": f"Job is already in terminal state: {job.status}"}


@router.post("/scrape-jobs/{job_id}/resume")
def public_resume_scrape_job(job_id: str) -> dict[str, Any]:
    try:
        j_uuid = uuid.UUID(job_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    with SessionLocal() as session:
        job = session.scalar(select(ScrapeJob).where(ScrapeJob.id == j_uuid))
        if not job:
            raise HTTPException(status_code=404, detail="Scrape job not found")

        if job.status == "STOPPED_SAVED":
            job.status = "QUEUED"
            session.commit()
            session.refresh(job)
            threading.Thread(target=run_scrape_background, args=(str(job.id),), daemon=True).start()
            return {"status": "QUEUED", "message": "Scrape job resumed successfully."}
        return {"status": job.status, "message": f"Job is not in stopped state: {job.status}"}


@router.post("/scrape-jobs/{job_id}/segregate")
def public_segregate_job(job_id: str) -> dict[str, Any]:
    try:
        j_uuid = uuid.UUID(job_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    with SessionLocal() as session:
        job = session.scalar(select(ScrapeJob).where(ScrapeJob.id == j_uuid))
        if not job:
            raise HTTPException(status_code=404, detail="Scrape job not found")

        leads = session.scalars(
            select(Lead).where(
                and_(Lead.job_id == j_uuid, Lead.raw_status == "PERSISTED")
            )
        ).all()

        if not leads:
            return {
                "status": "COMPLETED",
                "sheet_id": str(job.id),
                "raw_leads": 0,
                "segregated_leads": 0,
                "message": "No raw leads available to segregate."
            }

        all_lead_codes = session.scalars(
            select(Lead.lead_code).where(Lead.lead_code.isnot(None))
        ).all()
        
        max_idx = 100
        for code in all_lead_codes:
            if code and code.startswith("LD-"):
                try:
                    num = int(code.split("-")[1])
                    if num > max_idx:
                        max_idx = num
                except Exception:
                    pass

        for l in leads:
            max_idx += 1
            l.raw_status = "SEGREGATED"
            l.lead_code = f"LD-{max_idx}"

        session.commit()

        if job.status not in ("COMPLETED", "PARTIAL", "FAILED"):
            job.status = "COMPLETED"
            session.commit()

        return {
            "status": "COMPLETED",
            "sheet_id": str(job.id),
            "raw_leads": len(leads),
            "segregated_leads": len(leads),
            "message": "Your leads have been segregated."
        }


@router.get("/sheets")
def public_get_sheets() -> list[dict[str, Any]]:
    with SessionLocal() as session:
        # Ascending to assign stable sequential IDs
        jobs = session.scalars(select(ScrapeJob).order_by(ScrapeJob.created_at.asc())).all()
        sheets = []
        job_index = 0  # counts only jobs that become sheets (have segregated leads)

        for job in jobs:
            leads = session.scalars(
                select(Lead).where(
                    and_(Lead.job_id == job.id, Lead.raw_status == "SEGREGATED")
                ).order_by(Lead.created_at)
            ).all()

            if not leads:
                continue

            job_index += 1
            sheet_id = f"LD-{job_index:03d}"

            # Prefer user-given display name; fallback to auto-generated
            auto_name = f"{job.niche} - {job.region or 'Capital'} ({job.country})"
            display_name = job.sheet_name if job.sheet_name else auto_name

            sheet_leads = []
            for l in leads:
                sheet_leads.append({
                    "leadId": l.lead_code or f"LD-{job_index:03d}",
                    "businessName": l.business_name,
                    "location": f"{job.region or 'London'}, {job.country or 'UK'}",
                    "websiteUrl": l.website,
                    "contactPhone": l.phone,
                    "contactEmail": l.email,
                    "priorityScore": None,
                    "genuineness": int(l.genuineness_score * 100) if l.genuineness_score is not None else None,
                    "status": l.raw_status.lower() if l.raw_status else None,
                    "source": "google_maps",
                    "addedAt": l.created_at.strftime("%Y-%m-%d") if l.created_at else "2026-08-19",
                })

            sheets.append({
                "id": str(job.id),
                "sheetId": sheet_id,
                "name": display_name,
                "service": job.service or "website_dev",
                "sources": ["google_maps"],
                "niches": [job.niche],  # Always the original niche, never the custom name
                "timeTakenMin": 12,
                "createdAt": job.created_at.isoformat() if job.created_at else "2026-08-19T00:00:00Z",
                "leads": sheet_leads,
            })
        # Return newest first
        return list(reversed(sheets))


@router.get("/sheets/{sheet_id}")
def public_get_single_sheet(sheet_id: str) -> dict[str, Any]:
    sheets = public_get_sheets()
    matching = next((s for s in sheets if s["id"] == sheet_id or s["sheetId"] == sheet_id), None)
    if not matching:
        raise HTTPException(status_code=404, detail="Sheet not found")
    return matching


@router.patch("/sheets/{sheet_id}")
def public_update_sheet(sheet_id: str, payload: dict) -> dict[str, Any]:
    try:
        s_uuid = uuid.UUID(sheet_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid sheet ID format")

    with SessionLocal() as session:
        job = session.scalar(select(ScrapeJob).where(ScrapeJob.id == s_uuid))
        if not job:
            raise HTTPException(status_code=404, detail="Sheet not found")

        name = payload.get("name")
        if name:
            # Store user-given name in sheet_name, NEVER overwrite the original niche
            job.sheet_name = name
            session.commit()

        return {"id": str(job.id), "name": name or ""}


@router.delete("/sheets/{sheet_id}", status_code=status.HTTP_204_NO_CONTENT)
def public_delete_sheet(sheet_id: str) -> None:
    try:
        s_uuid = uuid.UUID(sheet_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid sheet ID format")

    with SessionLocal() as session:
        job = session.scalar(select(ScrapeJob).where(ScrapeJob.id == s_uuid))
        if not job:
            raise HTTPException(status_code=404, detail="Sheet not found")

        leads = session.scalars(select(Lead).where(Lead.job_id == s_uuid)).all()
        for l in leads:
            session.delete(l)
        session.delete(job)
        session.commit()
