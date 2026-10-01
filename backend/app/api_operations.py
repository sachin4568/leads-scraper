from __future__ import annotations

import logging
import urllib.parse
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from backend.app.api import current_workspace_id
from backend.app.database import get_db
from backend.app.models import Deal, EvidenceRecord, Lead, LeadAction, ScrapeJob, SourceRecord
from backend.app.models_phase2 import CanonicalLead
from backend.app.models_services import ServiceOpportunity
from backend.app.schemas import (
    BulkWorkflowStatusUpdateRequest,
    ChannelMetrics,
    CrmPipelineDashboardResponse,
    CrmStageMetrics,
    DealCreate,
    DealRead,
    DealUpdate,
    ExecutionLink,
    LeadActionCreate,
    LeadActionRead,
    LeadTimelineResponse,
    OperationsLeadDetail,
    OperationsLeadListResponse,
    OperationsLeadRead,
    OutreachAnalyticsResponse,
    OutreachDashboardResponse,
    PipelineFunnelStage,
    PriorityQueueInfo,
    RecommendedChannelInfo,
    RevenueBreakdownItem,
    ServiceMetrics,
    TimelineEvent,
    WorkflowStatusUpdateRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/operations", tags=["operations"])

DEFAULT_STAGE_PROBABILITIES = {
    "NEW": 0.10,
    "CONTACTED": 0.20,
    "INTERESTED": 0.30,
    "QUALIFIED": 0.40,
    "PROPOSAL": 0.60,
    "NEGOTIATION": 0.80,
    "WON": 1.00,
    "LOST": 0.00,
}


def clean_phone_number(phone: str | None) -> str:
    if not phone:
        return ""
    return "".join(c for c in phone if c.isdigit() or c == "+")


def serialize_deal(deal: Deal, business_name: str | None = None) -> DealRead:
    weighted = round(float(deal.deal_value) * float(deal.probability), 2)
    return DealRead(
        id=deal.id,
        workspace_id=deal.workspace_id,
        lead_id=deal.lead_id,
        business_name=business_name,
        title=deal.title,
        service_type=deal.service_type,
        deal_value=deal.deal_value,
        currency=deal.currency,
        stage=deal.stage,
        probability=deal.probability,
        weighted_value=weighted,
        expected_close_date=deal.expected_close_date,
        owner=deal.owner,
        win_loss_reason=deal.win_loss_reason,
        notes=deal.notes,
        created_at=deal.created_at,
        updated_at=deal.updated_at,
        closed_at=deal.closed_at,
    )


def build_execution_links(
    business_name: str,
    phone: str | None,
    email: str | None,
    website: str | None,
    contacts_details: dict[str, Any],
    social_details: dict[str, Any],
) -> list[ExecutionLink]:
    """Generates direct, zero-friction click-to-execute links for sales operators."""
    links: list[ExecutionLink] = []

    # 1. Phone Call link
    if phone:
        cleaned_phone = clean_phone_number(phone)
        links.append(
            ExecutionLink(
                channel="PHONE",
                label=f"Call {phone}",
                url=f"tel:{cleaned_phone}",
                is_direct=True,
            )
        )

    # 2. WhatsApp Direct link
    wh_links = contacts_details.get("whatsapp_links", [])
    if wh_links:
        links.append(
            ExecutionLink(
                channel="WHATSAPP",
                label="Chat on WhatsApp",
                url=wh_links[0],
                is_direct=True,
            )
        )
    elif phone:
        digits = "".join(filter(str.isdigit, phone))
        encoded_msg = urllib.parse.quote(
            f"Hi {business_name}, I noticed an opportunity to modernize your web presence and improve customer engagement. Would you be open to a quick chat?"
        )
        links.append(
            ExecutionLink(
                channel="WHATSAPP",
                label=f"WhatsApp {phone}",
                url=f"https://wa.me/{digits}?text={encoded_msg}",
                is_direct=True,
            )
        )

    # 3. Mailto Email link with pre-filled subject and body
    if email:
        subject = urllib.parse.quote(f"Digital presence optimization for {business_name}")
        body = urllib.parse.quote(
            f"Hi {business_name} Team,\n\nI was reviewing your business profile and noticed a few areas where modernizing your web presence could significantly increase incoming inquiries.\n\nWould you have 10 minutes this week for a brief consultation?\n\nBest regards,\nOutreach Team"
        )
        links.append(
            ExecutionLink(
                channel="EMAIL",
                label=f"Email {email}",
                url=f"mailto:{email}?subject={subject}&body={body}",
                is_direct=True,
            )
        )

    # 4. Social Profile Direct Links
    profiles = social_details.get("profiles", {})
    for network, url in profiles.items():
        links.append(
            ExecutionLink(
                channel="SOCIAL_DM",
                label=f"Open {network.capitalize()}",
                url=url,
                is_direct=True,
            )
        )

    # 5. Website Contact Page / Homepage link
    if website:
        links.append(
            ExecutionLink(
                channel="CONTACT_PAGE",
                label="Open Official Website",
                url=website,
                is_direct=False,
            )
        )

    return links


def build_unified_timeline(
    lead: Lead,
    evidences: list[EvidenceRecord],
    actions: list[LeadAction],
    deals: list[Deal] | None = None,
) -> list[TimelineEvent]:
    """Constructs a unified, end-to-end chronological timeline from ingestion through outreach, deals, and conversion."""
    events: list[TimelineEvent] = []

    # 1. Discovery Event
    events.append(
        TimelineEvent(
            id=f"disc-{lead.id}",
            event_type="DISCOVERY",
            title="Lead Discovered via OSM",
            description=f"Identified {lead.business_name} under category '{getattr(lead, 'niche', None) or 'Business'}'.",
            timestamp=lead.created_at,
            source="OSM_OVERPASS",
            metadata={"phone": lead.phone, "email": lead.email, "niche": getattr(lead, "niche", None)},
        )
    )

    # 2. Evidence-derived lifecycle events
    for ev in evidences:
        if ev.field_name == "website" and ev.details:
            events.append(
                TimelineEvent(
                    id=f"web-{ev.id}",
                    event_type="WEBSITE_VERIFICATION",
                    title="Official Website Verified",
                    description=f"Discovered and verified official domain: {ev.details.get('verified_url', lead.website)} (Confidence: {ev.confidence_score}%)",
                    timestamp=ev.created_at,
                    source=ev.source,
                    metadata=ev.details,
                )
            )
        elif ev.field_name == "contacts" and ev.details:
            events.append(
                TimelineEvent(
                    id=f"enr-{ev.id}",
                    event_type="ENRICHMENT",
                    title="Deep Enrichment Completed",
                    description="Extracted contact channels, addresses, and digital endpoints.",
                    timestamp=ev.created_at,
                    source="WEBSITE_ENRICHMENT",
                    metadata=ev.details,
                )
            )
        elif ev.field_name == "lead_intelligence" and ev.details:
            events.append(
                TimelineEvent(
                    id=f"intel-{ev.id}",
                    event_type="OPPORTUNITY_SCORING",
                    title="Opportunity Intelligence Scored",
                    description=f"Assigned opportunity score of {ev.details.get('overall_opportunity_score', 0)}/100 ({ev.details.get('opportunity_category', 'MEDIUM')}).",
                    timestamp=ev.created_at,
                    source="LEAD_INTELLIGENCE_ENGINE",
                    metadata=ev.details,
                )
            )

    # 3. Outreach Actions & Response Events
    for act in actions:
        ev_type = "OUTREACH_ATTEMPT"
        if act.outcome == "MEETING_BOOKED":
            ev_type = "MEETING"
        elif act.outcome in ["RESPONDED", "INTERESTED", "NOT_INTERESTED"]:
            ev_type = "RESPONSE_RECEIVED"
        elif act.outcome == "CONVERTED":
            ev_type = "CONVERSION"
        elif act.outcome in ["LOST", "WRONG_NUMBER", "BOUNCED"]:
            ev_type = "LOST"
        elif act.outcome == "QUALIFIED":
            ev_type = "QUALIFICATION"
        elif act.follow_up_date:
            ev_type = "FOLLOW_UP"

        events.append(
            TimelineEvent(
                id=str(act.id),
                event_type=ev_type,
                title=f"{act.channel} • {act.outcome.replace('_', ' ')}",
                description=act.notes or f"Outreach outcome recorded as {act.outcome}.",
                channel=act.channel,
                outcome=act.outcome,
                timestamp=act.created_at,
                source="OPERATOR_OUTREACH",
                metadata={"follow_up_date": act.follow_up_date.isoformat() if act.follow_up_date else None},
            )
        )

    # 4. Deals & CRM Events
    if deals:
        for d in deals:
            events.append(
                TimelineEvent(
                    id=f"deal-create-{d.id}",
                    event_type="QUALIFICATION",
                    title=f"Opportunity Created: {d.title}",
                    description=f"Service: {d.service_type} • Deal Value: ₹{d.deal_value:,.2f} ({d.stage})",
                    timestamp=d.created_at,
                    source="CRM_PIPELINE",
                    metadata={"deal_id": str(d.id), "deal_value": d.deal_value, "stage": d.stage},
                )
            )
            if d.stage == "WON":
                events.append(
                    TimelineEvent(
                        id=f"deal-won-{d.id}",
                        event_type="CONVERSION",
                        title=f"🎉 Deal Won: {d.title}",
                        description=f"Closed revenue of ₹{d.deal_value:,.2f} for {d.service_type}.",
                        timestamp=d.closed_at or d.updated_at,
                        source="CRM_PIPELINE",
                        metadata={"deal_id": str(d.id), "deal_value": d.deal_value},
                    )
                )
            elif d.stage == "LOST":
                events.append(
                    TimelineEvent(
                        id=f"deal-lost-{d.id}",
                        event_type="LOST",
                        title=f"Deal Lost: {d.title}",
                        description=f"Reason: {d.win_loss_reason or 'Lost opportunity'}",
                        timestamp=d.closed_at or d.updated_at,
                        source="CRM_PIPELINE",
                        metadata={"deal_id": str(d.id), "win_loss_reason": d.win_loss_reason},
                    )
                )

    # Sort descending by timestamp (latest first)
    events.sort(key=lambda x: x.timestamp, reverse=True)
    return events


def derive_recommended_channel(
    phone: str | None,
    email: str | None,
    contacts_details: dict[str, Any],
    social_details: dict[str, Any],
) -> RecommendedChannelInfo:
    """Deterministically derives the most effective outreach channel based on available contactability."""
    wh_links = contacts_details.get("whatsapp_links", [])
    if wh_links:
        return RecommendedChannelInfo(
            channel="WHATSAPP",
            value=wh_links[0],
            label="WhatsApp Direct",
        )
    
    if email:
        return RecommendedChannelInfo(
            channel="EMAIL",
            value=email,
            label="Email Outreach",
        )
    
    if phone:
        return RecommendedChannelInfo(
            channel="PHONE",
            value=phone,
            label="Phone Call",
        )
    
    profiles = social_details.get("profiles", {})
    if profiles:
        first_network, first_url = next(iter(profiles.items()))
        return RecommendedChannelInfo(
            channel="SOCIAL_DM",
            value=first_url,
            label=f"{first_network.capitalize()} DM",
        )
    
    return RecommendedChannelInfo(
        channel="NONE",
        value=None,
        label="No Direct Channel",
    )


def derive_priority_queue(
    opp_score: int,
    rec_channel: RecommendedChannelInfo,
    workflow_status: str,
    has_conflict: bool,
    follow_up_date: datetime | None,
) -> PriorityQueueInfo:
    """Combines opportunity score, contactability, conflict state, and follow-ups into an actionable priority queue."""
    now_utc = datetime.now(UTC)

    if workflow_status in ["CONVERTED", "DISMISSED", "LOST"]:
        return PriorityQueueInfo(
            queue="ARCHIVED",
            badge="⚪ Converted / Dismissed",
            urgency=0,
        )

    if follow_up_date is not None:
        f_date = follow_up_date if follow_up_date.tzinfo else follow_up_date.replace(tzinfo=UTC)
        if f_date <= now_utc:
            return PriorityQueueInfo(
                queue="FOLLOW_UP_OVERDUE",
                badge="🚨 Overdue Follow-up",
                urgency=95,
            )
        return PriorityQueueInfo(
            queue="FOLLOW_UP_SCHEDULED",
            badge="🟠 Follow Up Pending",
            urgency=75,
        )

    if rec_channel.channel == "NONE":
        return PriorityQueueInfo(
            queue="NO_CONTACT_CHANNEL",
            badge="⚪ No Contact Channel",
            urgency=10,
        )

    if opp_score >= 65 and workflow_status in ["NEW", "REVIEWED"]:
        if has_conflict:
            return PriorityQueueInfo(
                queue="REVIEW",
                badge="🟡 Review Conflict First",
                urgency=70,
            )
        return PriorityQueueInfo(
            queue="CONTACT_NOW",
            badge="🔴 Contact Now",
            urgency=90,
        )

    if workflow_status == "NEW":
        return PriorityQueueInfo(
            queue="REVIEW",
            badge="🟡 Review Required",
            urgency=50,
        )

    return PriorityQueueInfo(
        queue="STANDARD",
        badge="Standard Priority",
        urgency=30,
    )


@router.get("/leads", response_model=OperationsLeadListResponse)
def list_operations_leads(
    opportunity_category: str | None = Query(default=None, description="Comma-separated: VERY_HIGH,HIGH,MEDIUM,LOW,MINIMAL"),
    website_status: str | None = Query(default=None, description="has_website, no_website, verified_website, unverified_website, unreachable"),
    has_phone: bool | None = None,
    has_email: bool | None = None,
    has_whatsapp: bool | None = None,
    has_social: bool | None = None,
    service: str | None = Query(default=None, description="WEBSITE_DEVELOPMENT, SEO, SMMA"),
    workflow_status: str | None = Query(default=None, description="NEW, REVIEWED, CONTACTED, QUALIFIED, CONVERTED, DISMISSED, LOST"),
    priority_queue: str | None = Query(default=None, description="CONTACT_NOW, FOLLOW_UP_OVERDUE, FOLLOW_UP_SCHEDULED, REVIEW, NO_CONTACT_CHANNEL, ARCHIVED"),
    search: str | None = None,
    sort_by: str = Query(default="opportunity_score_desc", description="opportunity_score_desc, opportunity_score_asc, genuineness_score_desc, contactability_desc, created_at_desc, updated_at_desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
) -> OperationsLeadListResponse:
    """Server-side paginated, filterable, and sortable operations queue with 0 N+1 queries."""
    
    # 1. Base Query on Leads
    stmt = select(Lead).where(
        Lead.workspace_id == workspace_id,
        Lead.deleted_at.is_(None),
    )

    # 2. Basic SQL Filters
    if workflow_status:
        stmt = stmt.where(Lead.workflow_status == workflow_status.upper().strip())

    if has_phone is True:
        stmt = stmt.where(Lead.phone.is_not(None), Lead.phone != "")
    elif has_phone is False:
        stmt = stmt.where(or_(Lead.phone.is_(None), Lead.phone == ""))

    if has_email is True:
        stmt = stmt.where(Lead.email.is_not(None), Lead.email != "")
    elif has_email is False:
        stmt = stmt.where(or_(Lead.email.is_(None), Lead.email == ""))

    if website_status == "has_website":
        stmt = stmt.where(Lead.website.is_not(None), Lead.website != "")
    elif website_status == "no_website":
        stmt = stmt.where(or_(Lead.website.is_(None), Lead.website == ""))

    if search and search.strip():
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Lead.business_name.ilike(term),
                Lead.phone.ilike(term),
                Lead.email.ilike(term),
                Lead.website.ilike(term),
            )
        )

    # 3. Determine if secondary in-memory filtering is active
    has_secondary_filters = bool(
        opportunity_category
        or service
        or priority_queue
        or (has_whatsapp is not None)
        or (has_social is not None)
        or (website_status in ("verified_website", "unverified_website"))
    )

    can_use_sql_pagination = not has_secondary_filters and sort_by in (
        "genuineness_score_desc",
        "created_at_desc",
        "created_at_asc",
        "updated_at_desc",
    )

    if can_use_sql_pagination:
        # SQL-level Fast Path for High Scale
        if sort_by == "created_at_asc":
            stmt = stmt.order_by(asc(Lead.created_at))
        elif sort_by == "created_at_desc":
            stmt = stmt.order_by(desc(Lead.created_at))
        elif sort_by == "genuineness_score_desc":
            stmt = stmt.order_by(desc(Lead.genuineness_score), desc(Lead.created_at))
        elif sort_by == "updated_at_desc":
            stmt = stmt.order_by(desc(Lead.updated_at))
        else:
            stmt = stmt.order_by(desc(Lead.created_at))

        total_count = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        if total_count == 0:
            return OperationsLeadListResponse(total=0, page=page, page_size=page_size, results=[])

        all_matching_leads = db.scalars(
            stmt.limit(page_size).offset((page - 1) * page_size)
        ).all()
        is_already_paginated = True
    else:
        all_matching_leads = db.scalars(stmt).all()
        if not all_matching_leads:
            return OperationsLeadListResponse(total=0, page=page, page_size=page_size, results=[])
        is_already_paginated = False
        total_count = len(all_matching_leads)

    lead_ids = [l.id for l in all_matching_leads]

    # 4. Batch Load Evidence & Actions in ONE Single Batch Query each (0 N+1)
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
        ).order_by(desc(LeadAction.created_at), desc(LeadAction.id))
    ).all()
    actions_by_lead: dict[uuid.UUID, list[LeadAction]] = {}
    for act in actions_raw:
        if act.lead_id not in actions_by_lead:
            actions_by_lead[act.lead_id] = []
        actions_by_lead[act.lead_id].append(act)

    # 5. Transform and Apply Secondary In-Memory Intelligence Filters
    enriched_items: list[dict[str, Any]] = []
    opp_cat_set = set(opportunity_category.upper().split(",")) if opportunity_category else None

    for lead in all_matching_leads:
        ev_map = evidence_by_lead.get(lead.id, {})
        intel_ev = ev_map.get("lead_intelligence")
        intel_details = (intel_ev.details or {}) if intel_ev else {}
        
        contacts_ev = ev_map.get("contacts")
        contacts_details = (contacts_ev.details or {}) if contacts_ev else {}

        social_ev = ev_map.get("social_profiles")
        social_details = (social_ev.details or {}) if social_ev else {}

        conflicts_ev = ev_map.get("conflicts")
        conflicts_details = (conflicts_ev.details or {}) if conflicts_ev else {}

        web_ev = ev_map.get("website")

        # Determine website status
        if not lead.website:
            w_status = "NO_WEBSITE"
        elif web_ev and web_ev.source == "ZERO_BUDGET_VERIFIED":
            w_status = "VERIFIED_WEBSITE"
        elif web_ev and web_ev.status == "REJECT":
            w_status = "UNVERIFIED_WEBSITE"
        else:
            w_status = "HAS_WEBSITE"

        wh_links = contacts_details.get("whatsapp_links", [])
        soc_profiles = social_details.get("profiles", {})
        lead_has_wh = bool(wh_links)
        lead_has_soc = bool(soc_profiles)

        opp_score = int(intel_details.get("overall_opportunity_score", int(lead.genuineness_score * 100)))
        opp_cat = str(intel_details.get("opportunity_category", intel_ev.status if intel_ev else "MEDIUM"))
        top_reasons = list(intel_details.get("top_reasons", []))

        # Check secondary filter criteria
        if opp_cat_set and opp_cat not in opp_cat_set:
            continue

        if website_status == "verified_website" and w_status != "VERIFIED_WEBSITE":
            continue
        elif website_status == "unverified_website" and w_status != "UNVERIFIED_WEBSITE":
            continue

        if has_whatsapp is True and not lead_has_wh:
            continue
        elif has_whatsapp is False and lead_has_wh:
            continue

        if has_social is True and not lead_has_soc:
            continue
        elif has_social is False and lead_has_soc:
            continue

        # Recommended service inference
        rec_service = None
        rec_score = None
        if not lead.website or w_status == "NO_WEBSITE":
            rec_service = "WEBSITE_DEVELOPMENT"
            rec_score = 95.0
        elif opp_score >= 65:
            rec_service = "SEO"
            rec_score = float(intel_details.get("seo_opportunity_score", 75.0))
        elif lead_has_wh or lead_has_soc:
            rec_service = "SMMA"
            rec_score = float(intel_details.get("digital_presence_gap_score", 60.0))

        if service and rec_service != service.upper().strip():
            continue

        rec_channel = derive_recommended_channel(
            phone=lead.phone,
            email=lead.email,
            contacts_details=contacts_details,
            social_details=social_details,
        )

        p_queue = derive_priority_queue(
            opp_score=opp_score,
            rec_channel=rec_channel,
            workflow_status=lead.workflow_status or "NEW",
            has_conflict=bool(conflicts_details),
            follow_up_date=lead.follow_up_date,
        )

        if priority_queue and p_queue.queue != priority_queue.upper().strip():
            continue

        exec_links = build_execution_links(
            business_name=lead.business_name,
            phone=lead.phone,
            email=lead.email,
            website=lead.website,
            contacts_details=contacts_details,
            social_details=social_details,
        )

        lead_acts = actions_by_lead.get(lead.id, [])
        latest_act = LeadActionRead.model_validate(lead_acts[0]) if lead_acts else None

        item = {
            "id": lead.id,
            "business_name": lead.business_name,
            "category": getattr(lead, "niche", None) or "Business",
            "location": None,
            "phone": lead.phone,
            "email": lead.email,
            "website": lead.website,
            "website_status": w_status,
            "opportunity_score": opp_score,
            "opportunity_category": opp_cat,
            "genuineness_score": lead.genuineness_score,
            "recommended_service": rec_service,
            "recommended_service_score": rec_score,
            "workflow_status": lead.workflow_status or "NEW",
            "top_reasons": top_reasons,
            "has_conflict": bool(conflicts_details),
            "has_whatsapp": lead_has_wh,
            "has_social": lead_has_soc,
            "recommended_channel": rec_channel,
            "priority_queue": p_queue,
            "execution_links": exec_links,
            "follow_up_date": lead.follow_up_date,
            "actions_count": len(lead_acts),
            "latest_action": latest_act,
            "last_enriched_at": intel_ev.created_at if intel_ev else lead.updated_at,
            "created_at": lead.created_at,
            "_contactability_score": int(intel_details.get("contactability_score", 0)),
        }
        enriched_items.append(item)

    if is_already_paginated:
        paginated_results = [OperationsLeadRead(**item) for item in enriched_items]
        total = total_count
    else:
        # 6. Deterministic Sorting
        if sort_by == "opportunity_score_desc":
            enriched_items.sort(key=lambda x: x["opportunity_score"], reverse=True)
        elif sort_by == "opportunity_score_asc":
            enriched_items.sort(key=lambda x: x["opportunity_score"])
        elif sort_by == "genuineness_score_desc":
            enriched_items.sort(key=lambda x: x["genuineness_score"], reverse=True)
        elif sort_by == "contactability_desc":
            enriched_items.sort(key=lambda x: x["_contactability_score"], reverse=True)
        elif sort_by == "created_at_desc":
            enriched_items.sort(key=lambda x: x["created_at"], reverse=True)
        elif sort_by == "updated_at_desc":
            enriched_items.sort(key=lambda x: x["last_enriched_at"] or x["created_at"], reverse=True)
        else:
            enriched_items.sort(key=lambda x: x["opportunity_score"], reverse=True)

        # 7. Pagination
        total = len(enriched_items)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_results = [OperationsLeadRead(**item) for item in enriched_items[start_idx:end_idx]]

    return OperationsLeadListResponse(
        total=total,
        page=page,
        page_size=page_size,
        results=paginated_results,
    )


@router.get("/leads/{lead_id}", response_model=OperationsLeadDetail)
def get_operations_lead_detail(
    lead_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
) -> OperationsLeadDetail:
    """Returns complete intelligence, action history, unified timeline, deals, SEO, technologies, contacts, and conflicts."""
    lead = db.scalar(
        select(Lead).where(
            Lead.id == lead_id,
            Lead.workspace_id == workspace_id,
            Lead.deleted_at.is_(None),
        )
    )
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    evidences = db.scalars(
        select(EvidenceRecord).where(
            EvidenceRecord.lead_id == lead.id,
            EvidenceRecord.workspace_id == workspace_id,
        ).order_by(desc(EvidenceRecord.created_at))
    ).all()

    actions = db.scalars(
        select(LeadAction).where(
            LeadAction.lead_id == lead.id,
            LeadAction.workspace_id == workspace_id,
        ).order_by(desc(LeadAction.created_at), desc(LeadAction.id))
    ).all()

    deals = db.scalars(
        select(Deal).where(
            Deal.lead_id == lead.id,
            Deal.workspace_id == workspace_id,
        ).order_by(desc(Deal.created_at), desc(Deal.id))
    ).all()

    ev_map: dict[str, EvidenceRecord] = {ev.field_name: ev for ev in evidences}
    intel_ev = ev_map.get("lead_intelligence")
    intel_details = (intel_ev.details or {}) if intel_ev else {}
    
    contacts_ev = ev_map.get("contacts")
    contacts_details = (contacts_ev.details or {}) if contacts_ev else {}

    seo_ev = ev_map.get("seo")
    seo_details = (seo_ev.details or {}) if seo_ev else {}

    social_ev = ev_map.get("social_profiles")
    social_details = (social_ev.details or {}) if social_ev else {}

    tech_ev = ev_map.get("technologies")
    tech_details = (tech_ev.details or {}) if tech_ev else {}

    conflicts_ev = ev_map.get("conflicts")
    conflicts_details = (conflicts_ev.details or {}) if conflicts_ev else {}

    web_ev = ev_map.get("website")

    if not lead.website:
        w_status = "NO_WEBSITE"
    elif web_ev and web_ev.source == "ZERO_BUDGET_VERIFIED":
        w_status = "VERIFIED_WEBSITE"
    elif web_ev and web_ev.status == "REJECT":
        w_status = "UNVERIFIED_WEBSITE"
    else:
        w_status = "HAS_WEBSITE"

    wh_links = contacts_details.get("whatsapp_links", [])
    soc_profiles = social_details.get("profiles", {})

    opp_score = int(intel_details.get("overall_opportunity_score", int(lead.genuineness_score * 100)))
    opp_cat = str(intel_details.get("opportunity_category", intel_ev.status if intel_ev else "MEDIUM"))
    top_reasons = list(intel_details.get("top_reasons", []))

    evidence_list = []
    for ev in evidences:
        evidence_list.append({
            "id": str(ev.id),
            "field_name": ev.field_name,
            "status": ev.status,
            "confidence_score": ev.confidence_score,
            "source": ev.source,
            "details": ev.details or {},
            "created_at": ev.created_at.isoformat() if ev.created_at else None,
        })

    rec_service = None
    rec_score = None
    if not lead.website or w_status == "NO_WEBSITE":
        rec_service = "WEBSITE_DEVELOPMENT"
        rec_score = 95.0
    elif opp_score >= 65:
        rec_service = "SEO"
        rec_score = float(intel_details.get("seo_opportunity_score", 75.0))
    elif wh_links or soc_profiles:
        rec_service = "SMMA"
        rec_score = float(intel_details.get("digital_presence_gap_score", 60.0))

    rec_channel = derive_recommended_channel(
        phone=lead.phone,
        email=lead.email,
        contacts_details=contacts_details,
        social_details=social_details,
    )

    p_queue = derive_priority_queue(
        opp_score=opp_score,
        rec_channel=rec_channel,
        workflow_status=lead.workflow_status or "NEW",
        has_conflict=bool(conflicts_details),
        follow_up_date=lead.follow_up_date,
    )

    exec_links = build_execution_links(
        business_name=lead.business_name,
        phone=lead.phone,
        email=lead.email,
        website=lead.website,
        contacts_details=contacts_details,
        social_details=social_details,
    )

    action_history = [LeadActionRead.model_validate(a) for a in actions]
    timeline_events = build_unified_timeline(lead=lead, evidences=evidences, actions=actions, deals=deals)
    deals_list = [serialize_deal(d, business_name=lead.business_name) for d in deals]

    return OperationsLeadDetail(
        id=lead.id,
        business_name=lead.business_name,
        category=getattr(lead, "niche", None) or "Business",
        location=None,
        phone=lead.phone,
        email=lead.email,
        website=lead.website,
        website_status=w_status,
        opportunity_score=opp_score,
        opportunity_category=opp_cat,
        genuineness_score=lead.genuineness_score,
        recommended_service=rec_service,
        recommended_service_score=rec_score,
        workflow_status=lead.workflow_status or "NEW",
        top_reasons=top_reasons,
        has_conflict=bool(conflicts_details),
        has_whatsapp=bool(wh_links),
        has_social=bool(soc_profiles),
        recommended_channel=rec_channel,
        priority_queue=p_queue,
        execution_links=exec_links,
        follow_up_date=lead.follow_up_date,
        actions_count=len(actions),
        latest_action=action_history[0] if action_history else None,
        last_enriched_at=intel_ev.created_at if intel_ev else lead.updated_at,
        created_at=lead.created_at,
        contactability={
            "phone": lead.phone,
            "email": lead.email,
            "whatsapp_links": wh_links,
            "website_phones": contacts_details.get("phones", []),
            "website_emails": contacts_details.get("emails", []),
            "addresses": contacts_details.get("addresses", []),
            "contactability_score": intel_details.get("contactability_score", 0),
        },
        website_health={
            "is_reachable": not bool(seo_details.get("seo_issues", [])) if lead.website else False,
            "is_https": lead.website.startswith("https") if lead.website else False,
            "verified_url": web_ev.details.get("verified_url") if web_ev and web_ev.details else lead.website,
        },
        seo=seo_details,
        social=social_details,
        technologies=tech_details.get("detected_technologies", []),
        service_opportunities={
            "website_development": {"eligible": not bool(lead.website), "score": intel_details.get("website_opportunity_score", 0)},
            "seo": {"eligible": bool(lead.website) and opp_score >= 50, "score": intel_details.get("seo_opportunity_score", 0)},
            "smma": {"eligible": bool(soc_profiles) or bool(wh_links), "score": intel_details.get("digital_presence_gap_score", 0)},
        },
        evidence_records=evidence_list,
        conflicts=conflicts_details,
        action_history=action_history,
        timeline=timeline_events,
        deals=deals_list,
    )


@router.get("/leads/{lead_id}/timeline", response_model=LeadTimelineResponse)
def get_lead_activity_timeline(
    lead_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
) -> LeadTimelineResponse:
    """Returns a unified, end-to-end activity timeline for a single lead."""
    lead = db.scalar(
        select(Lead).where(
            Lead.id == lead_id,
            Lead.workspace_id == workspace_id,
            Lead.deleted_at.is_(None),
        )
    )
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    evidences = db.scalars(
        select(EvidenceRecord).where(
            EvidenceRecord.lead_id == lead.id,
            EvidenceRecord.workspace_id == workspace_id,
        ).order_by(desc(EvidenceRecord.created_at))
    ).all()

    actions = db.scalars(
        select(LeadAction).where(
            LeadAction.lead_id == lead.id,
            LeadAction.workspace_id == workspace_id,
        ).order_by(desc(LeadAction.created_at), desc(LeadAction.id))
    ).all()

    deals = db.scalars(
        select(Deal).where(
            Deal.lead_id == lead.id,
            Deal.workspace_id == workspace_id,
        ).order_by(desc(Deal.created_at), desc(Deal.id))
    ).all()

    timeline_events = build_unified_timeline(lead=lead, evidences=evidences, actions=actions, deals=deals)

    return LeadTimelineResponse(
        lead_id=lead.id,
        business_name=lead.business_name,
        current_workflow_status=lead.workflow_status or "NEW",
        events=timeline_events,
    )


@router.post("/leads/{lead_id}/actions", response_model=LeadActionRead, status_code=status.HTTP_201_CREATED)
def record_lead_action(
    lead_id: uuid.UUID,
    payload: LeadActionCreate,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
) -> LeadActionRead:
    """Records an outreach attempt/response in an append-only log without modifying source evidence."""
    lead = db.scalar(
        select(Lead).where(
            Lead.id == lead_id,
            Lead.workspace_id == workspace_id,
            Lead.deleted_at.is_(None),
        )
    )
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    action = LeadAction(
        workspace_id=workspace_id,
        lead_id=lead.id,
        channel=payload.channel,
        outcome=payload.outcome,
        notes=payload.notes,
        follow_up_date=payload.follow_up_date,
    )
    db.add(action)

    if payload.next_workflow_status:
        lead.workflow_status = payload.next_workflow_status
    elif payload.outcome in ["CONTACTED", "NO_RESPONSE", "FOLLOW_UP_SCHEDULED"]:
        if lead.workflow_status in ["NEW", "REVIEWED"]:
            lead.workflow_status = "CONTACTED"
    elif payload.outcome in ["RESPONDED", "INTERESTED"]:
        if lead.workflow_status in ["NEW", "REVIEWED", "CONTACTED"]:
            lead.workflow_status = "CONTACTED"
    elif payload.outcome in ["MEETING_BOOKED", "QUALIFIED"]:
        lead.workflow_status = "QUALIFIED"
    elif payload.outcome == "CONVERTED":
        lead.workflow_status = "CONVERTED"
    elif payload.outcome in ["NOT_INTERESTED", "LOST"]:
        lead.workflow_status = "LOST"
    elif payload.outcome in ["WRONG_NUMBER", "BOUNCED"]:
        lead.workflow_status = "DISMISSED"

    if payload.follow_up_date is not None:
        lead.follow_up_date = payload.follow_up_date
    elif payload.outcome in ["CONVERTED", "NOT_INTERESTED", "WRONG_NUMBER", "LOST"]:
        lead.follow_up_date = None

    db.commit()
    db.refresh(action)
    return LeadActionRead.model_validate(action)


@router.get("/leads/{lead_id}/actions", response_model=list[LeadActionRead])
def get_lead_actions(
    lead_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
) -> list[LeadActionRead]:
    """Retrieves chronological outreach history for a lead."""
    lead = db.scalar(
        select(Lead).where(
            Lead.id == lead_id,
            Lead.workspace_id == workspace_id,
            Lead.deleted_at.is_(None),
        )
    )
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    actions = db.scalars(
        select(LeadAction).where(
            LeadAction.lead_id == lead.id,
            LeadAction.workspace_id == workspace_id,
        ).order_by(desc(LeadAction.created_at), desc(LeadAction.id))
    ).all()
    return [LeadActionRead.model_validate(a) for a in actions]


# ─── CRM Deals & Opportunities Endpoints ─────────────────────────────────────

@router.post("/deals", response_model=DealRead, status_code=status.HTTP_201_CREATED)
def create_deal(
    payload: DealCreate,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
) -> DealRead:
    """Creates a new sales deal / opportunity from a qualified lead."""
    lead = db.scalar(
        select(Lead).where(
            Lead.id == payload.lead_id,
            Lead.workspace_id == workspace_id,
            Lead.deleted_at.is_(None),
        )
    )
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    prob = payload.probability if payload.probability is not None else DEFAULT_STAGE_PROBABILITIES.get(payload.stage, 0.4)
    closed_at = datetime.now(UTC) if payload.stage in ["WON", "LOST"] else None

    deal = Deal(
        workspace_id=workspace_id,
        lead_id=lead.id,
        title=payload.title,
        service_type=payload.service_type,
        deal_value=payload.deal_value,
        currency=payload.currency,
        stage=payload.stage,
        probability=prob,
        expected_close_date=payload.expected_close_date,
        owner=payload.owner,
        win_loss_reason=payload.win_loss_reason,
        notes=payload.notes,
        closed_at=closed_at,
    )
    db.add(deal)

    if payload.stage == "WON":
        lead.workflow_status = "CONVERTED"
    elif payload.stage == "LOST":
        lead.workflow_status = "LOST"
    elif lead.workflow_status in ["NEW", "REVIEWED", "CONTACTED"]:
        lead.workflow_status = "QUALIFIED"

    db.commit()
    db.refresh(deal)
    return serialize_deal(deal, business_name=lead.business_name)


@router.get("/deals", response_model=list[DealRead])
def list_deals(
    stage: str | None = None,
    service_type: str | None = None,
    lead_id: uuid.UUID | None = None,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
) -> list[DealRead]:
    """Lists all CRM sales deals with optional stage or service filters (0 N+1 queries)."""
    stmt = select(Deal, Lead.business_name).join(Lead, Deal.lead_id == Lead.id).where(
        Deal.workspace_id == workspace_id,
        Lead.deleted_at.is_(None),
    )
    if stage:
        stmt = stmt.where(Deal.stage == stage.upper().strip())
    if service_type:
        stmt = stmt.where(Deal.service_type == service_type.upper().strip())
    if lead_id:
        stmt = stmt.where(Deal.lead_id == lead_id)

    stmt = stmt.order_by(desc(Deal.created_at), desc(Deal.id))
    results = db.execute(stmt).all()

    return [serialize_deal(d, business_name=bname) for d, bname in results]


@router.get("/deals/{deal_id}", response_model=DealRead)
def get_deal(
    deal_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
) -> DealRead:
    """Retrieves a single deal by ID."""
    res = db.execute(
        select(Deal, Lead.business_name).join(Lead, Deal.lead_id == Lead.id).where(
            Deal.id == deal_id,
            Deal.workspace_id == workspace_id,
            Lead.deleted_at.is_(None),
        )
    ).first()
    if not res:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    deal, bname = res
    return serialize_deal(deal, business_name=bname)


@router.patch("/deals/{deal_id}", response_model=DealRead)
def update_deal(
    deal_id: uuid.UUID,
    payload: DealUpdate,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
) -> DealRead:
    """Updates deal stage, value, close date, or win/loss reason and synchronizes lead status."""
    deal = db.scalar(
        select(Deal).where(
            Deal.id == deal_id,
            Deal.workspace_id == workspace_id,
        )
    )
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")

    lead = db.scalar(
        select(Lead).where(
            Lead.id == deal.lead_id,
            Lead.workspace_id == workspace_id,
        )
    )

    if payload.title is not None:
        deal.title = payload.title
    if payload.service_type is not None:
        deal.service_type = payload.service_type
    if payload.deal_value is not None:
        deal.deal_value = payload.deal_value
    if payload.currency is not None:
        deal.currency = payload.currency
    if payload.expected_close_date is not None:
        deal.expected_close_date = payload.expected_close_date
    if payload.owner is not None:
        deal.owner = payload.owner
    if payload.win_loss_reason is not None:
        deal.win_loss_reason = payload.win_loss_reason
    if payload.notes is not None:
        deal.notes = payload.notes

    if payload.stage is not None:
        deal.stage = payload.stage
        if payload.probability is not None:
            deal.probability = payload.probability
        else:
            deal.probability = DEFAULT_STAGE_PROBABILITIES.get(payload.stage, deal.probability)

        if payload.stage in ["WON", "LOST"]:
            deal.closed_at = datetime.now(UTC)
            if lead:
                lead.workflow_status = "CONVERTED" if payload.stage == "WON" else "LOST"
        else:
            deal.closed_at = None
            if lead and lead.workflow_status in ["NEW", "REVIEWED", "CONTACTED"]:
                lead.workflow_status = "QUALIFIED"

    elif payload.probability is not None:
        deal.probability = payload.probability

    db.commit()
    db.refresh(deal)
    return serialize_deal(deal, business_name=lead.business_name if lead else None)


@router.get("/crm/pipeline", response_model=CrmPipelineDashboardResponse)
def get_crm_pipeline_dashboard(
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
) -> CrmPipelineDashboardResponse:
    """Calculates live CRM pipeline revenue, weighted pipeline, won revenue, stage distributions, and revenue by service/source."""
    deals_raw = db.execute(
        select(Deal, Lead.business_name).join(Lead, Deal.lead_id == Lead.id).where(
            Deal.workspace_id == workspace_id,
            Lead.deleted_at.is_(None),
        ).order_by(desc(Deal.created_at), desc(Deal.id))
    ).all()

    total_deals = len(deals_raw)
    total_pipeline_value = 0.0
    weighted_pipeline_value = 0.0
    won_revenue = 0.0
    lost_value = 0.0
    active_deals_count = 0
    won_deals_count = 0
    lost_deals_count = 0

    stages_map: dict[str, dict[str, Any]] = {
        "QUALIFIED": {"count": 0, "total_value": 0.0, "weighted_value": 0.0},
        "PROPOSAL": {"count": 0, "total_value": 0.0, "weighted_value": 0.0},
        "NEGOTIATION": {"count": 0, "total_value": 0.0, "weighted_value": 0.0},
        "WON": {"count": 0, "total_value": 0.0, "weighted_value": 0.0},
        "LOST": {"count": 0, "total_value": 0.0, "weighted_value": 0.0},
    }

    service_map: dict[str, dict[str, Any]] = {
        "WEBSITE_DEVELOPMENT": {"deals_count": 0, "won_revenue": 0.0, "pipeline_value": 0.0},
        "SEO": {"deals_count": 0, "won_revenue": 0.0, "pipeline_value": 0.0},
        "SMMA": {"deals_count": 0, "won_revenue": 0.0, "pipeline_value": 0.0},
        "PAID_ADS": {"deals_count": 0, "won_revenue": 0.0, "pipeline_value": 0.0},
        "CUSTOM": {"deals_count": 0, "won_revenue": 0.0, "pipeline_value": 0.0},
    }

    source_map: dict[str, dict[str, Any]] = {
        "OSM_DISCOVERY": {"deals_count": 0, "won_revenue": 0.0, "pipeline_value": 0.0},
        "ZERO_BUDGET_VERIFIED": {"deals_count": 0, "won_revenue": 0.0, "pipeline_value": 0.0},
    }

    serialized_deals: list[DealRead] = []

    for d, bname in deals_raw:
        val = float(d.deal_value)
        weighted = round(val * float(d.probability), 2)
        serialized_deals.append(serialize_deal(d, business_name=bname))

        svc = d.service_type if d.service_type in service_map else "CUSTOM"
        service_map[svc]["deals_count"] += 1

        source_key = "OSM_DISCOVERY"
        source_map[source_key]["deals_count"] += 1

        if d.stage == "WON":
            won_revenue += val
            won_deals_count += 1
            service_map[svc]["won_revenue"] += val
            source_map[source_key]["won_revenue"] += val
        elif d.stage == "LOST":
            lost_value += val
            lost_deals_count += 1
        else:
            total_pipeline_value += val
            weighted_pipeline_value += weighted
            active_deals_count += 1
            service_map[svc]["pipeline_value"] += val
            source_map[source_key]["pipeline_value"] += val

        if d.stage in stages_map:
            stages_map[d.stage]["count"] += 1
            stages_map[d.stage]["total_value"] += val
            stages_map[d.stage]["weighted_value"] += weighted

    total_closed = won_deals_count + lost_deals_count
    win_rate = round((won_deals_count / max(1, total_closed)) * 100.0, 1) if total_closed > 0 else 0.0
    avg_deal_size = round((won_revenue + total_pipeline_value) / max(1, total_deals), 2) if total_deals > 0 else 0.0

    stages_list = [
        CrmStageMetrics(
            stage=st_name,
            count=data["count"],
            total_value=round(data["total_value"], 2),
            weighted_value=round(data["weighted_value"], 2),
        )
        for st_name, data in stages_map.items()
    ]

    service_breakdown = [
        RevenueBreakdownItem(
            category=svc_name.replace("_", " "),
            deals_count=data["deals_count"],
            won_revenue=round(data["won_revenue"], 2),
            pipeline_value=round(data["pipeline_value"], 2),
        )
        for svc_name, data in service_map.items()
        if data["deals_count"] > 0 or svc_name in ["WEBSITE_DEVELOPMENT", "SEO", "SMMA"]
    ]

    source_breakdown = [
        RevenueBreakdownItem(
            category=src_name.replace("_", " "),
            deals_count=data["deals_count"],
            won_revenue=round(data["won_revenue"], 2),
            pipeline_value=round(data["pipeline_value"], 2),
        )
        for src_name, data in source_map.items()
        if data["deals_count"] > 0
    ]

    return CrmPipelineDashboardResponse(
        total_pipeline_value=round(total_pipeline_value, 2),
        weighted_pipeline_value=round(weighted_pipeline_value, 2),
        won_revenue=round(won_revenue, 2),
        lost_value=round(lost_value, 2),
        total_deals=total_deals,
        active_deals_count=active_deals_count,
        won_deals_count=won_deals_count,
        lost_deals_count=lost_deals_count,
        avg_deal_size=avg_deal_size,
        win_rate=win_rate,
        stages=stages_list,
        revenue_by_service=service_breakdown,
        revenue_by_source=source_breakdown,
        recent_deals=serialized_deals[:10],
    )


@router.patch("/leads/{lead_id}/workflow", response_model=OperationsLeadRead)
def update_lead_workflow_status(
    lead_id: uuid.UUID,
    payload: WorkflowStatusUpdateRequest,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
) -> OperationsLeadRead:
    """Updates the operational workflow status of a lead without mutating ground-truth discovery data."""
    lead = db.scalar(
        select(Lead).where(
            Lead.id == lead_id,
            Lead.workspace_id == workspace_id,
            Lead.deleted_at.is_(None),
        )
    )
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    lead.workflow_status = payload.workflow_status
    db.commit()
    db.refresh(lead)

    return OperationsLeadRead(
        id=lead.id,
        business_name=lead.business_name,
        category=getattr(lead, "niche", None) or "Business",
        location=None,
        phone=lead.phone,
        email=lead.email,
        website=lead.website,
        website_status="HAS_WEBSITE" if lead.website else "NO_WEBSITE",
        opportunity_score=int(lead.genuineness_score * 100),
        opportunity_category="MEDIUM",
        genuineness_score=lead.genuineness_score,
        recommended_service=None,
        recommended_service_score=None,
        workflow_status=lead.workflow_status,
        top_reasons=[],
        has_conflict=False,
        has_whatsapp=False,
        has_social=False,
        recommended_channel=RecommendedChannelInfo(),
        priority_queue=PriorityQueueInfo(),
        execution_links=[],
        follow_up_date=lead.follow_up_date,
        actions_count=0,
        latest_action=None,
        last_enriched_at=lead.updated_at,
        created_at=lead.created_at,
    )


@router.patch("/leads/bulk-workflow")
def bulk_update_lead_workflow_status(
    payload: BulkWorkflowStatusUpdateRequest,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Bulk updates workflow status for multiple leads safely, rejecting cross-workspace injections."""
    if payload.lead_ids:
        foreign_leads = db.scalars(
            select(Lead.id).where(
                Lead.id.in_(payload.lead_ids),
                Lead.workspace_id != workspace_id,
            )
        ).all()
        if foreign_leads:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-workspace operation forbidden: Unauthorized lead IDs provided",
            )

    leads = db.scalars(
        select(Lead).where(
            Lead.id.in_(payload.lead_ids),
            Lead.workspace_id == workspace_id,
            Lead.deleted_at.is_(None),
        )
    ).all()

    for l in leads:
        l.workflow_status = payload.workflow_status

    db.commit()
    return {
        "updated_count": len(leads),
        "workflow_status": payload.workflow_status,
        "status": "SUCCESS",
    }


@router.get("/outreach/dashboard", response_model=OutreachDashboardResponse)
def get_outreach_dashboard_metrics(
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
) -> OutreachDashboardResponse:
    """Returns workspace-wide outreach performance, queue distribution, and upcoming follow-ups."""
    leads = db.scalars(
        select(Lead).where(
            Lead.workspace_id == workspace_id,
            Lead.deleted_at.is_(None),
        )
    ).all()

    total_leads = len(leads)
    new_leads = sum(1 for l in leads if l.workflow_status == "NEW")
    contacted = sum(1 for l in leads if l.workflow_status == "CONTACTED")
    qualified = sum(1 for l in leads if l.workflow_status == "QUALIFIED")
    converted = sum(1 for l in leads if l.workflow_status == "CONVERTED")
    dismissed = sum(1 for l in leads if l.workflow_status in ["DISMISSED", "LOST"])

    now_utc = datetime.now(UTC)
    follow_up_required = sum(
        1 for l in leads if l.follow_up_date is not None and l.workflow_status in ["CONTACTED", "QUALIFIED", "REVIEWED"]
    )
    overdue_follow_ups_count = sum(
        1
        for l in leads
        if l.follow_up_date is not None
        and (l.follow_up_date if l.follow_up_date.tzinfo else l.follow_up_date.replace(tzinfo=UTC)) <= now_utc
        and l.workflow_status in ["CONTACTED", "QUALIFIED", "REVIEWED"]
    )

    ready_to_contact = sum(
        1 for l in leads if (l.phone or l.email) and l.workflow_status in ["NEW", "REVIEWED"]
    )

    channels_breakdown = {
        "whatsapp": 0,
        "email": sum(1 for l in leads if l.email),
        "phone": sum(1 for l in leads if l.phone),
        "social": 0,
        "none": sum(1 for l in leads if not l.phone and not l.email),
    }

    recent_actions_raw = db.scalars(
        select(LeadAction).where(LeadAction.workspace_id == workspace_id).order_by(desc(LeadAction.created_at), desc(LeadAction.id)).limit(10)
    ).all()

    return OutreachDashboardResponse(
        total_leads=total_leads,
        new_leads=new_leads,
        ready_to_contact=ready_to_contact,
        contacted=contacted,
        follow_up_required=follow_up_required,
        overdue_follow_ups_count=overdue_follow_ups_count,
        qualified=qualified,
        converted=converted,
        dismissed=dismissed,
        channels_breakdown=channels_breakdown,
        recent_actions=[LeadActionRead.model_validate(a) for a in recent_actions_raw],
    )


@router.get("/outreach/analytics", response_model=OutreachAnalyticsResponse)
def get_outreach_analytics(
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
) -> OutreachAnalyticsResponse:
    """Calculates full sales pipeline funnel, conversion drop-offs, channel effectiveness, and service metrics with 0 N+1 queries."""
    leads = db.scalars(
        select(Lead).where(
            Lead.workspace_id == workspace_id,
            Lead.deleted_at.is_(None),
        )
    ).all()

    if not leads:
        return OutreachAnalyticsResponse(
            total_leads=0,
            contactable_leads=0,
            contacted_leads=0,
            responded_leads=0,
            interested_leads=0,
            meeting_booked_leads=0,
            qualified_leads=0,
            converted_leads=0,
            lost_leads=0,
            overall_response_rate=0.0,
            overall_interest_rate=0.0,
            overall_conversion_rate=0.0,
            funnel=[],
            channel_effectiveness=[],
            service_effectiveness=[],
        )

    lead_ids = [l.id for l in leads]

    actions = db.scalars(
        select(LeadAction).where(LeadAction.lead_id.in_(lead_ids)).order_by(desc(LeadAction.created_at), desc(LeadAction.id))
    ).all()

    evidences = db.scalars(
        select(EvidenceRecord).where(EvidenceRecord.lead_id.in_(lead_ids))
    ).all()

    evidence_by_lead: dict[uuid.UUID, dict[str, EvidenceRecord]] = {}
    for ev in evidences:
        if ev.lead_id not in evidence_by_lead:
            evidence_by_lead[ev.lead_id] = {}
        evidence_by_lead[ev.lead_id][ev.field_name] = ev

    actions_by_lead: dict[uuid.UUID, list[LeadAction]] = {}
    for act in actions:
        if act.lead_id not in actions_by_lead:
            actions_by_lead[act.lead_id] = []
        actions_by_lead[act.lead_id].append(act)

    total_leads = len(leads)
    contactable_leads = 0
    contacted_leads = 0
    responded_leads = 0
    interested_leads = 0
    meeting_booked_leads = 0
    qualified_leads = 0
    converted_leads = 0
    lost_leads = 0

    service_agg: dict[str, dict[str, int]] = {
        "WEBSITE_DEVELOPMENT": {"leads_count": 0, "attempts": 0, "responses": 0, "interested": 0, "meetings_booked": 0, "conversions": 0},
        "SEO": {"leads_count": 0, "attempts": 0, "responses": 0, "interested": 0, "meetings_booked": 0, "conversions": 0},
        "SMMA": {"leads_count": 0, "attempts": 0, "responses": 0, "interested": 0, "meetings_booked": 0, "conversions": 0},
    }

    channel_agg: dict[str, dict[str, int]] = {
        "WHATSAPP": {"attempts": 0, "responses": 0, "interested": 0, "meetings_booked": 0, "conversions": 0},
        "PHONE": {"attempts": 0, "responses": 0, "interested": 0, "meetings_booked": 0, "conversions": 0},
        "EMAIL": {"attempts": 0, "responses": 0, "interested": 0, "meetings_booked": 0, "conversions": 0},
        "SOCIAL_DM": {"attempts": 0, "responses": 0, "interested": 0, "meetings_booked": 0, "conversions": 0},
        "CONTACT_PAGE": {"attempts": 0, "responses": 0, "interested": 0, "meetings_booked": 0, "conversions": 0},
    }

    response_outcomes = {"RESPONDED", "INTERESTED", "NOT_INTERESTED", "MEETING_BOOKED", "QUALIFIED", "CONVERTED", "LOST"}
    interest_outcomes = {"INTERESTED", "MEETING_BOOKED", "QUALIFIED", "CONVERTED"}

    for lead in leads:
        ev_map = evidence_by_lead.get(lead.id, {})
        contacts_ev = ev_map.get("contacts")
        contacts_details = (contacts_ev.details or {}) if contacts_ev else {}
        social_ev = ev_map.get("social_profiles")
        social_details = (social_ev.details or {}) if social_ev else {}
        intel_ev = ev_map.get("lead_intelligence")
        intel_details = (intel_ev.details or {}) if intel_ev else {}

        opp_score = int(intel_details.get("overall_opportunity_score", int(lead.genuineness_score * 100)))
        rec_svc = "WEBSITE_DEVELOPMENT"
        if lead.website:
            if opp_score >= 65:
                rec_svc = "SEO"
            else:
                rec_svc = "SMMA"

        service_agg[rec_svc]["leads_count"] += 1

        has_direct = bool(lead.phone or lead.email or contacts_details.get("whatsapp_links") or social_details.get("profiles"))
        if has_direct:
            contactable_leads += 1

        lead_acts = actions_by_lead.get(lead.id, [])
        if lead_acts or lead.workflow_status in ["CONTACTED", "QUALIFIED", "CONVERTED", "LOST"]:
            contacted_leads += 1

        lead_outcomes = {a.outcome for a in lead_acts}
        has_response = bool(lead_outcomes.intersection(response_outcomes))
        has_interest = bool(lead_outcomes.intersection(interest_outcomes))
        has_meeting = "MEETING_BOOKED" in lead_outcomes or lead.workflow_status in ["QUALIFIED", "CONVERTED"]

        if has_response:
            responded_leads += 1
        if has_interest:
            interested_leads += 1
        if has_meeting:
            meeting_booked_leads += 1
        if lead.workflow_status in ["QUALIFIED", "CONVERTED"]:
            qualified_leads += 1
        if lead.workflow_status == "CONVERTED":
            converted_leads += 1
        if lead.workflow_status in ["LOST", "DISMISSED"]:
            lost_leads += 1

        for a in lead_acts:
            ch = a.channel.upper()
            if ch in channel_agg:
                channel_agg[ch]["attempts"] += 1
                if a.outcome in response_outcomes:
                    channel_agg[ch]["responses"] += 1
                if a.outcome in interest_outcomes:
                    channel_agg[ch]["interested"] += 1
                if a.outcome in ["MEETING_BOOKED", "CONVERTED"]:
                    channel_agg[ch]["meetings_booked"] += 1
                if a.outcome == "CONVERTED":
                    channel_agg[ch]["conversions"] += 1

            service_agg[rec_svc]["attempts"] += 1
            if a.outcome in response_outcomes:
                service_agg[rec_svc]["responses"] += 1
            if a.outcome in interest_outcomes:
                service_agg[rec_svc]["interested"] += 1
            if a.outcome in ["MEETING_BOOKED", "CONVERTED"]:
                service_agg[rec_svc]["meetings_booked"] += 1
            if a.outcome == "CONVERTED":
                service_agg[rec_svc]["conversions"] += 1

    funnel_counts = [
        ("Leads Discovered", total_leads),
        ("Contactable", contactable_leads),
        ("Contacted", contacted_leads),
        ("Responded", responded_leads),
        ("Interested", interested_leads),
        ("Meeting Booked", meeting_booked_leads),
        ("Qualified", qualified_leads),
        ("Converted", converted_leads),
    ]

    funnel_stages: list[PipelineFunnelStage] = []
    prev_count = total_leads
    for stage_name, count in funnel_counts:
        rate_prev = round((count / max(1, prev_count)) * 100.0, 1)
        rate_tot = round((count / max(1, total_leads)) * 100.0, 1)
        funnel_stages.append(
            PipelineFunnelStage(
                stage=stage_name,
                count=count,
                conversion_rate_from_previous=rate_prev,
                conversion_rate_from_total=rate_tot,
            )
        )
        prev_count = count

    channel_metrics_list: list[ChannelMetrics] = []
    for ch_name, data in channel_agg.items():
        att = data["attempts"]
        resp = data["responses"]
        intr = data["interested"]
        conv = data["conversions"]
        channel_metrics_list.append(
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

    service_metrics_list: list[ServiceMetrics] = []
    for svc_name, data in service_agg.items():
        service_metrics_list.append(
            ServiceMetrics(
                service=svc_name,
                leads_count=data["leads_count"],
                attempts=data["attempts"],
                responses=data["responses"],
                interested=data["interested"],
                meetings_booked=data["meetings_booked"],
                conversions=data["conversions"],
            )
        )

    overall_resp_rate = round((responded_leads / max(1, contacted_leads)) * 100.0, 1) if contacted_leads > 0 else 0.0
    overall_intr_rate = round((interested_leads / max(1, responded_leads)) * 100.0, 1) if responded_leads > 0 else 0.0
    overall_conv_rate = round((converted_leads / max(1, total_leads)) * 100.0, 1) if total_leads > 0 else 0.0

    return OutreachAnalyticsResponse(
        total_leads=total_leads,
        contactable_leads=contactable_leads,
        contacted_leads=contacted_leads,
        responded_leads=responded_leads,
        interested_leads=interested_leads,
        meeting_booked_leads=meeting_booked_leads,
        qualified_leads=qualified_leads,
        converted_leads=converted_leads,
        lost_leads=lost_leads,
        overall_response_rate=overall_resp_rate,
        overall_interest_rate=overall_intr_rate,
        overall_conversion_rate=overall_conv_rate,
        funnel=funnel_stages,
        channel_effectiveness=channel_metrics_list,
        service_effectiveness=service_metrics_list,
    )
