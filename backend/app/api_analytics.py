from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from backend.app.api import current_workspace_id
from backend.app.database import get_db
from backend.app.models import Deal, EvidenceRecord, Lead, LeadAction
from backend.app.schemas import (
    AnalyticsOverviewResponse,
    ChannelMetrics,
    ExecutiveKpiSummary,
    PipelineFunnelStage,
    QualityTierPerformance,
    ServicePerformanceAnalytics,
    SourcePerformance,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["analytics"])


def parse_timeframe_bounds(
    timeframe: str,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> tuple[datetime | None, datetime | None]:
    """Calculates UTC datetime boundaries for standardized reporting windows."""
    now_utc = datetime.now(UTC)
    tf = timeframe.lower().strip()

    if tf == "today":
        start = datetime(now_utc.year, now_utc.month, now_utc.day, 0, 0, 0, tzinfo=UTC)
        return start, now_utc
    elif tf == "7d":
        return now_utc - timedelta(days=7), now_utc
    elif tf == "30d":
        return now_utc - timedelta(days=30), now_utc
    elif tf == "90d":
        return now_utc - timedelta(days=90), now_utc
    elif tf == "this_year":
        start = datetime(now_utc.year, 1, 1, 0, 0, 0, tzinfo=UTC)
        return start, now_utc
    elif tf == "custom" and start_date:
        s_date = start_date if start_date.tzinfo else start_date.replace(tzinfo=UTC)
        e_date = (end_date if end_date.tzinfo else end_date.replace(tzinfo=UTC)) if end_date else now_utc
        return s_date, e_date
    else:  # all_time or default
        return None, None


def compute_business_analytics(
    workspace_id: uuid.UUID,
    db: Session,
    start_dt: datetime | None,
    end_dt: datetime | None,
    timeframe: str,
) -> AnalyticsOverviewResponse:
    """Executes single-batch aggregate analytics across discovery, intelligence, outreach, and CRM revenue."""
    
    # 1. Base Leads Query filtered by workspace and timeframe
    leads_stmt = select(Lead).where(
        Lead.workspace_id == workspace_id,
        Lead.deleted_at.is_(None),
    )
    if start_dt:
        leads_stmt = leads_stmt.where(Lead.created_at >= start_dt)
    if end_dt:
        leads_stmt = leads_stmt.where(Lead.created_at <= end_dt)

    leads = db.scalars(leads_stmt).all()
    lead_ids = [l.id for l in leads]

    if not leads:
        empty_kpis = ExecutiveKpiSummary(
            total_leads=0,
            contactable_leads=0,
            contacted_leads=0,
            responded_leads=0,
            qualified_leads=0,
            won_leads=0,
            lost_leads=0,
            total_pipeline_value=0.0,
            weighted_pipeline_value=0.0,
            won_revenue=0.0,
            lost_value=0.0,
            overall_conversion_rate=0.0,
            overall_response_rate=0.0,
            win_rate=0.0,
            avg_deal_size=0.0,
        )
        return AnalyticsOverviewResponse(
            timeframe=timeframe,
            start_date=start_dt,
            end_date=end_dt,
            kpis=empty_kpis,
            funnel=[],
            quality_performance=[],
            source_performance=[],
            service_performance=[],
            channel_effectiveness=[],
        )

    # 2. Batch load Evidence, Actions, and Deals for matching leads (0 N+1)
    evidences_raw = db.scalars(
        select(EvidenceRecord).where(
            EvidenceRecord.lead_id.in_(lead_ids),
            EvidenceRecord.workspace_id == workspace_id,
        )
    ).all()
    evidence_by_lead: dict[uuid.UUID, dict[str, EvidenceRecord]] = {}
    for ev in evidences_raw:
        if ev.lead_id not in evidence_by_lead:
            evidence_by_lead[ev.lead_id] = {}
        evidence_by_lead[ev.lead_id][ev.field_name] = ev

    actions_raw = db.scalars(
        select(LeadAction).where(
            LeadAction.lead_id.in_(lead_ids),
            LeadAction.workspace_id == workspace_id,
        ).order_by(desc(LeadAction.created_at))
    ).all()
    actions_by_lead: dict[uuid.UUID, list[LeadAction]] = {}
    for act in actions_raw:
        if act.lead_id not in actions_by_lead:
            actions_by_lead[act.lead_id] = []
        actions_by_lead[act.lead_id].append(act)

    deals_raw = db.scalars(
        select(Deal).where(
            Deal.workspace_id == workspace_id,
            Deal.lead_id.in_(lead_ids),
        )
    ).all()
    deals_by_lead: dict[uuid.UUID, list[Deal]] = {}
    for d in deals_raw:
        if d.lead_id not in deals_by_lead:
            deals_by_lead[d.lead_id] = []
        deals_by_lead[d.lead_id].append(d)

    # 3. Initialize Data Aggregators
    total_leads = len(leads)
    contactable_leads = 0
    contacted_leads = 0
    responded_leads = 0
    interested_leads = 0
    meeting_booked_leads = 0
    qualified_leads = 0
    won_leads = 0
    lost_leads = 0

    total_pipeline_value = 0.0
    weighted_pipeline_value = 0.0
    won_revenue = 0.0
    lost_value = 0.0
    total_deals_count = 0
    won_deals_count = 0
    lost_deals_count = 0

    quality_tiers: dict[str, dict[str, Any]] = {
        "VERY_HIGH": {"leads": 0, "contactable": 0, "contacted": 0, "qualified": 0, "won": 0, "won_rev": 0.0, "total_deals": 0, "deal_val_sum": 0.0},
        "HIGH": {"leads": 0, "contactable": 0, "contacted": 0, "qualified": 0, "won": 0, "won_rev": 0.0, "total_deals": 0, "deal_val_sum": 0.0},
        "MEDIUM": {"leads": 0, "contactable": 0, "contacted": 0, "qualified": 0, "won": 0, "won_rev": 0.0, "total_deals": 0, "deal_val_sum": 0.0},
        "LOW": {"leads": 0, "contactable": 0, "contacted": 0, "qualified": 0, "won": 0, "won_rev": 0.0, "total_deals": 0, "deal_val_sum": 0.0},
        "MINIMAL": {"leads": 0, "contactable": 0, "contacted": 0, "qualified": 0, "won": 0, "won_rev": 0.0, "total_deals": 0, "deal_val_sum": 0.0},
    }

    sources_map: dict[str, dict[str, Any]] = {
        "OSM_DISCOVERY": {"leads": 0, "contactable": 0, "responded": 0, "qualified": 0, "won": 0, "won_rev": 0.0, "pipe_val": 0.0, "deals_count": 0},
        "ZERO_BUDGET_VERIFIED": {"leads": 0, "contactable": 0, "responded": 0, "qualified": 0, "won": 0, "won_rev": 0.0, "pipe_val": 0.0, "deals_count": 0},
        "DIRECT_INTAKE": {"leads": 0, "contactable": 0, "responded": 0, "qualified": 0, "won": 0, "won_rev": 0.0, "pipe_val": 0.0, "deals_count": 0},
    }

    services_map: dict[str, dict[str, Any]] = {
        "WEBSITE_DEVELOPMENT": {"leads_pitched": 0, "opportunities": 0, "pipeline_val": 0.0, "won_rev": 0.0, "won_deals": 0, "closed_deals": 0, "deal_val_sum": 0.0},
        "SEO": {"leads_pitched": 0, "opportunities": 0, "pipeline_val": 0.0, "won_rev": 0.0, "won_deals": 0, "closed_deals": 0, "deal_val_sum": 0.0},
        "SMMA": {"leads_pitched": 0, "opportunities": 0, "pipeline_val": 0.0, "won_rev": 0.0, "won_deals": 0, "closed_deals": 0, "deal_val_sum": 0.0},
        "PAID_ADS": {"leads_pitched": 0, "opportunities": 0, "pipeline_val": 0.0, "won_rev": 0.0, "won_deals": 0, "closed_deals": 0, "deal_val_sum": 0.0},
        "CUSTOM": {"leads_pitched": 0, "opportunities": 0, "pipeline_val": 0.0, "won_rev": 0.0, "won_deals": 0, "closed_deals": 0, "deal_val_sum": 0.0},
    }

    channel_map: dict[str, dict[str, int]] = {
        "WHATSAPP": {"attempts": 0, "responses": 0, "interested": 0, "meetings_booked": 0, "conversions": 0},
        "PHONE": {"attempts": 0, "responses": 0, "interested": 0, "meetings_booked": 0, "conversions": 0},
        "EMAIL": {"attempts": 0, "responses": 0, "interested": 0, "meetings_booked": 0, "conversions": 0},
        "SOCIAL_DM": {"attempts": 0, "responses": 0, "interested": 0, "meetings_booked": 0, "conversions": 0},
        "CONTACT_PAGE": {"attempts": 0, "responses": 0, "interested": 0, "meetings_booked": 0, "conversions": 0},
    }

    response_outcomes = {"RESPONDED", "INTERESTED", "NOT_INTERESTED", "MEETING_BOOKED", "QUALIFIED", "CONVERTED", "LOST"}
    interest_outcomes = {"INTERESTED", "MEETING_BOOKED", "QUALIFIED", "CONVERTED"}

    # 4. Process Lead Level Metrics
    for lead in leads:
        ev_map = evidence_by_lead.get(lead.id, {})
        contacts_ev = ev_map.get("contacts")
        contacts_details = (contacts_ev.details or {}) if contacts_ev else {}
        social_ev = ev_map.get("social_profiles")
        social_details = (social_ev.details or {}) if social_ev else {}
        intel_ev = ev_map.get("lead_intelligence")
        intel_details = (intel_ev.details or {}) if intel_ev else {}
        web_ev = ev_map.get("website")

        # Opportunity Quality Tier
        q_tier = str(intel_details.get("opportunity_category", intel_ev.status if intel_ev else "MEDIUM")).upper()
        if q_tier not in quality_tiers:
            q_tier = "MEDIUM"
        quality_tiers[q_tier]["leads"] += 1

        # Acquisition Source attribution
        source_key = "OSM_DISCOVERY"
        if web_ev and web_ev.source == "ZERO_BUDGET_VERIFIED":
            source_key = "ZERO_BUDGET_VERIFIED"
        elif not lead.phone and not lead.email and not lead.website:
            source_key = "DIRECT_INTAKE"
        sources_map[source_key]["leads"] += 1

        # Contactability
        has_direct_contact = bool(
            lead.phone or lead.email or contacts_details.get("whatsapp_links") or social_details.get("profiles")
        )
        if has_direct_contact:
            contactable_leads += 1
            quality_tiers[q_tier]["contactable"] += 1
            sources_map[source_key]["contactable"] += 1

        # Outreach Activity
        lead_acts = actions_by_lead.get(lead.id, [])
        lead_deals = deals_by_lead.get(lead.id, [])

        is_contacted = bool(lead_acts or lead.workflow_status in ["CONTACTED", "QUALIFIED", "CONVERTED", "LOST"])
        if is_contacted:
            contacted_leads += 1
            quality_tiers[q_tier]["contacted"] += 1

        outcomes = {a.outcome for a in lead_acts}
        has_response = bool(outcomes.intersection(response_outcomes))
        has_interest = bool(outcomes.intersection(interest_outcomes))
        has_meeting = "MEETING_BOOKED" in outcomes or lead.workflow_status in ["QUALIFIED", "CONVERTED"]

        if has_response:
            responded_leads += 1
            sources_map[source_key]["responded"] += 1
        if has_interest:
            interested_leads += 1
        if has_meeting:
            meeting_booked_leads += 1

        # Pitched Service Inference
        opp_score = int(intel_details.get("overall_opportunity_score", int(lead.genuineness_score * 100)))
        pitched_service = "WEBSITE_DEVELOPMENT"
        if lead.website:
            if opp_score >= 65:
                pitched_service = "SEO"
            else:
                pitched_service = "SMMA"
        services_map[pitched_service]["leads_pitched"] += 1

        # Lead Workflow & Conversion Status
        is_qualified = lead.workflow_status in ["QUALIFIED", "CONVERTED"] or bool(lead_deals)
        is_won = lead.workflow_status == "CONVERTED" or any(d.stage == "WON" for d in lead_deals)
        is_lost = lead.workflow_status in ["LOST", "DISMISSED"] and not is_won

        if is_qualified:
            qualified_leads += 1
            quality_tiers[q_tier]["qualified"] += 1
            sources_map[source_key]["qualified"] += 1

        if is_won:
            won_leads += 1
            quality_tiers[q_tier]["won"] += 1
            sources_map[source_key]["won"] += 1
        elif is_lost:
            lost_leads += 1

        # Channel Action Aggregations
        for a in lead_acts:
            ch = a.channel.upper()
            if ch in channel_map:
                channel_map[ch]["attempts"] += 1
                if a.outcome in response_outcomes:
                    channel_map[ch]["responses"] += 1
                if a.outcome in interest_outcomes:
                    channel_map[ch]["interested"] += 1
                if a.outcome in ["MEETING_BOOKED", "CONVERTED"]:
                    channel_map[ch]["meetings_booked"] += 1
                if a.outcome == "CONVERTED":
                    channel_map[ch]["conversions"] += 1

        # CRM Deals & Revenue Aggregation for Lead
        for d in lead_deals:
            total_deals_count += 1
            val = float(d.deal_value)
            weighted = round(val * float(d.probability), 2)
            svc_key = d.service_type if d.service_type in services_map else "CUSTOM"

            services_map[svc_key]["opportunities"] += 1
            services_map[svc_key]["deal_val_sum"] += val
            quality_tiers[q_tier]["total_deals"] += 1
            quality_tiers[q_tier]["deal_val_sum"] += val
            sources_map[source_key]["deals_count"] += 1

            if d.stage == "WON":
                won_revenue += val
                won_deals_count += 1
                services_map[svc_key]["won_rev"] += val
                services_map[svc_key]["won_deals"] += 1
                services_map[svc_key]["closed_deals"] += 1
                quality_tiers[q_tier]["won_rev"] += val
                sources_map[source_key]["won_rev"] += val
            elif d.stage == "LOST":
                lost_value += val
                lost_deals_count += 1
                services_map[svc_key]["closed_deals"] += 1
            else:
                total_pipeline_value += val
                weighted_pipeline_value += weighted
                services_map[svc_key]["pipeline_val"] += val
                sources_map[source_key]["pipe_val"] += val

    # 5. Calculate KPI Metrics & Ratios
    overall_conv_rate = round((won_leads / max(1, total_leads)) * 100.0, 1)
    overall_resp_rate = round((responded_leads / max(1, contacted_leads)) * 100.0, 1) if contacted_leads > 0 else 0.0
    total_closed_deals = won_deals_count + lost_deals_count
    win_rate = round((won_deals_count / max(1, total_closed_deals)) * 100.0, 1) if total_closed_deals > 0 else 0.0
    avg_deal_size = round((won_revenue + total_pipeline_value) / max(1, total_deals_count), 2) if total_deals_count > 0 else 0.0

    kpis = ExecutiveKpiSummary(
        total_leads=total_leads,
        contactable_leads=contactable_leads,
        contacted_leads=contacted_leads,
        responded_leads=responded_leads,
        qualified_leads=qualified_leads,
        won_leads=won_leads,
        lost_leads=lost_leads,
        total_pipeline_value=round(total_pipeline_value, 2),
        weighted_pipeline_value=round(weighted_pipeline_value, 2),
        won_revenue=round(won_revenue, 2),
        lost_value=round(lost_value, 2),
        overall_conversion_rate=overall_conv_rate,
        overall_response_rate=overall_resp_rate,
        win_rate=win_rate,
        avg_deal_size=avg_deal_size,
    )

    # 6. Complete Pipeline Funnel
    funnel_raw = [
        ("Leads Discovered", total_leads),
        ("Contactable", contactable_leads),
        ("Contacted", contacted_leads),
        ("Responded", responded_leads),
        ("Interested", interested_leads),
        ("Qualified", qualified_leads),
        ("Won", won_leads),
    ]
    funnel: list[PipelineFunnelStage] = []
    prev_cnt = total_leads
    for stage_name, count in funnel_raw:
        rate_prev = round((count / max(1, prev_cnt)) * 100.0, 1)
        rate_tot = round((count / max(1, total_leads)) * 100.0, 1)
        funnel.append(
            PipelineFunnelStage(
                stage=stage_name,
                count=count,
                conversion_rate_from_previous=rate_prev,
                conversion_rate_from_total=rate_tot,
            )
        )
        prev_cnt = count

    # 7. Quality Tier Breakdown
    quality_performance: list[QualityTierPerformance] = []
    for tier_name, data in quality_tiers.items():
        t_leads = data["leads"]
        quality_performance.append(
            QualityTierPerformance(
                tier=tier_name,
                leads_count=t_leads,
                contactable_count=data["contactable"],
                contactable_pct=round((data["contactable"] / max(1, t_leads)) * 100.0, 1) if t_leads > 0 else 0.0,
                contacted_count=data["contacted"],
                contacted_pct=round((data["contacted"] / max(1, t_leads)) * 100.0, 1) if t_leads > 0 else 0.0,
                qualified_count=data["qualified"],
                qualified_pct=round((data["qualified"] / max(1, t_leads)) * 100.0, 1) if t_leads > 0 else 0.0,
                won_count=data["won"],
                won_pct=round((data["won"] / max(1, t_leads)) * 100.0, 1) if t_leads > 0 else 0.0,
                won_revenue=round(data["won_rev"], 2),
                avg_deal_size=round(data["deal_val_sum"] / max(1, data["total_deals"]), 2) if data["total_deals"] > 0 else 0.0,
            )
        )

    # 8. Acquisition Source Breakdown
    source_performance: list[SourcePerformance] = []
    for src_name, data in sources_map.items():
        s_leads = data["leads"]
        source_performance.append(
            SourcePerformance(
                source=src_name.replace("_", " "),
                leads_count=s_leads,
                contactable_pct=round((data["contactable"] / max(1, s_leads)) * 100.0, 1) if s_leads > 0 else 0.0,
                response_pct=round((data["responded"] / max(1, s_leads)) * 100.0, 1) if s_leads > 0 else 0.0,
                qualified_pct=round((data["qualified"] / max(1, s_leads)) * 100.0, 1) if s_leads > 0 else 0.0,
                won_pct=round((data["won"] / max(1, s_leads)) * 100.0, 1) if s_leads > 0 else 0.0,
                won_revenue=round(data["won_rev"], 2),
                pipeline_value=round(data["pipe_val"], 2),
                avg_deal_size=round((data["won_rev"] + data["pipe_val"]) / max(1, data["deals_count"]), 2) if data["deals_count"] > 0 else 0.0,
            )
        )

    # 9. Service Pitch Performance Breakdown
    service_performance: list[ServicePerformanceAnalytics] = []
    for svc_name, data in services_map.items():
        s_closed = data["closed_deals"]
        service_performance.append(
            ServicePerformanceAnalytics(
                service=svc_name.replace("_", " "),
                leads_pitched=data["leads_pitched"],
                opportunities_count=data["opportunities"],
                pipeline_value=round(data["pipeline_val"], 2),
                won_revenue=round(data["won_rev"], 2),
                win_rate=round((data["won_deals"] / max(1, s_closed)) * 100.0, 1) if s_closed > 0 else 0.0,
                avg_deal_size=round(data["deal_val_sum"] / max(1, data["opportunities"]), 2) if data["opportunities"] > 0 else 0.0,
            )
        )

    # 10. Channel Effectiveness Breakdown
    channel_effectiveness: list[ChannelMetrics] = []
    for ch_name, data in channel_map.items():
        att = data["attempts"]
        resp = data["responses"]
        intr = data["interested"]
        conv = data["conversions"]
        channel_effectiveness.append(
            ChannelMetrics(
                channel=ch_name,
                attempts=att,
                responses=resp,
                interested=intr,
                meetings_booked=data["meetings_booked"],
                conversions=conv,
                response_rate=round((resp / max(1, att)) * 100.0, 1) if att > 0 else 0.0,
                interest_rate=round((intr / max(1, resp)) * 100.0, 1) if resp > 0 else 0.0,
                conversion_rate=round((conv / max(1, att)) * 100.0, 1) if att > 0 else 0.0,
            )
        )

    return AnalyticsOverviewResponse(
        timeframe=timeframe,
        start_date=start_dt,
        end_date=end_dt,
        kpis=kpis,
        funnel=funnel,
        quality_performance=quality_performance,
        source_performance=source_performance,
        service_performance=service_performance,
        channel_effectiveness=channel_effectiveness,
    )


@router.get("/overview", response_model=AnalyticsOverviewResponse)
def get_analytics_overview(
    timeframe: str = Query(default="30d", description="today, 7d, 30d, 90d, this_year, all_time, custom"),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
) -> AnalyticsOverviewResponse:
    """Consolidated Executive Business Analytics endpoint answering: lead volume, contactability, conversion, quality, and revenue."""
    start_dt, end_dt = parse_timeframe_bounds(timeframe, start_date, end_date)
    return compute_business_analytics(
        workspace_id=workspace_id,
        db=db,
        start_dt=start_dt,
        end_dt=end_dt,
        timeframe=timeframe,
    )


@router.get("/funnel", response_model=list[PipelineFunnelStage])
def get_analytics_funnel(
    timeframe: str = Query(default="30d"),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
) -> list[PipelineFunnelStage]:
    """Returns the end-to-end sales conversion funnel with drop-offs."""
    start_dt, end_dt = parse_timeframe_bounds(timeframe, start_date, end_date)
    overview = compute_business_analytics(workspace_id, db, start_dt, end_dt, timeframe)
    return overview.funnel


@router.get("/revenue", response_model=ExecutiveKpiSummary)
def get_analytics_revenue(
    timeframe: str = Query(default="30d"),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
) -> ExecutiveKpiSummary:
    """Returns revenue KPIs: pipeline, weighted forecast, won revenue, win rate, avg deal size."""
    start_dt, end_dt = parse_timeframe_bounds(timeframe, start_date, end_date)
    overview = compute_business_analytics(workspace_id, db, start_dt, end_dt, timeframe)
    return overview.kpis


@router.get("/quality", response_model=list[QualityTierPerformance])
def get_analytics_quality_tiers(
    timeframe: str = Query(default="30d"),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
) -> list[QualityTierPerformance]:
    """Returns performance breakdown by Phase 9 Opportunity Intelligence Quality Tiers."""
    start_dt, end_dt = parse_timeframe_bounds(timeframe, start_date, end_date)
    overview = compute_business_analytics(workspace_id, db, start_dt, end_dt, timeframe)
    return overview.quality_performance


@router.get("/sources", response_model=list[SourcePerformance])
def get_analytics_sources(
    timeframe: str = Query(default="30d"),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
) -> list[SourcePerformance]:
    """Returns acquisition source commercial comparison."""
    start_dt, end_dt = parse_timeframe_bounds(timeframe, start_date, end_date)
    overview = compute_business_analytics(workspace_id, db, start_dt, end_dt, timeframe)
    return overview.source_performance


@router.get("/services", response_model=list[ServicePerformanceAnalytics])
def get_analytics_services(
    timeframe: str = Query(default="30d"),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
) -> list[ServicePerformanceAnalytics]:
    """Returns service performance and revenue matrix."""
    start_dt, end_dt = parse_timeframe_bounds(timeframe, start_date, end_date)
    overview = compute_business_analytics(workspace_id, db, start_dt, end_dt, timeframe)
    return overview.service_performance


@router.get("/channels", response_model=list[ChannelMetrics])
def get_analytics_channels(
    timeframe: str = Query(default="30d"),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
) -> list[ChannelMetrics]:
    """Returns communication channel performance breakdown."""
    start_dt, end_dt = parse_timeframe_bounds(timeframe, start_date, end_date)
    overview = compute_business_analytics(workspace_id, db, start_dt, end_dt, timeframe)
    return overview.channel_effectiveness
