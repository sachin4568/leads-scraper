from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.app.api import current_workspace_id
from backend.app.database import get_db
from backend.app.models import Deal, Lead, LeadAction, Proposal, ProposalVersion

router = APIRouter(tags=["Proposals & Quotations"])


# ─── Pydantic Schemas ────────────────────────────────────────────────────────

class ProposalVersionRead(BaseModel):
    id: uuid.UUID
    version_number: int
    base_price: float
    addons_total: float
    discount_amount: float
    quoted_amount: float
    scope_of_work: str | None = None
    deliverables: list[str] | None = None
    timeline: str | None = None
    change_summary: str | None = None
    created_at: datetime


class ProposalRead(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    deal_id: uuid.UUID
    lead_id: uuid.UUID
    client_name: str
    deal_title: str
    proposal_number: str
    title: str
    service_type: str
    status: str
    current_version: int
    base_price: float
    addons_total: float
    discount_amount: float
    quoted_amount: float
    currency: str
    scope_of_work: str | None = None
    deliverables: list[str] | None = None
    timeline: str | None = None
    terms_and_conditions: str | None = None
    expected_start_date: datetime | None = None
    expiry_date: datetime | None = None
    sent_at: datetime | None = None
    viewed_at: datetime | None = None
    accepted_at: datetime | None = None
    rejected_at: datetime | None = None
    rejection_reason: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    versions: list[ProposalVersionRead] = []


class ProposalCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    service_type: str = Field(default="WEBSITE_DEVELOPMENT")
    base_price: float = Field(..., ge=0.0)
    addons_total: float = Field(default=0.0, ge=0.0)
    discount_amount: float = Field(default=0.0, ge=0.0)
    currency: str = Field(default="INR")
    scope_of_work: str | None = None
    deliverables: list[str] | None = None
    timeline: str | None = None
    terms_and_conditions: str | None = None
    expected_start_date: datetime | None = None
    expiry_date: datetime | None = None
    notes: str | None = None


class ProposalVersionCreate(BaseModel):
    base_price: float = Field(..., ge=0.0)
    addons_total: float = Field(default=0.0, ge=0.0)
    discount_amount: float = Field(default=0.0, ge=0.0)
    scope_of_work: str | None = None
    deliverables: list[str] | None = None
    timeline: str | None = None
    change_summary: str | None = None


class ProposalStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(PROPOSAL_DRAFT|PROPOSAL_SENT|VIEWED|NEGOTIATION|ACCEPTED|REJECTED|EXPIRED)$")
    rejection_reason: str | None = None


class ProposalListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    proposals: list[ProposalRead]


class ProposalMetricsResponse(BaseModel):
    total_proposals: int
    draft_count: int
    sent_count: int
    viewed_count: int
    negotiation_count: int
    accepted_count: int
    rejected_count: int
    expired_count: int
    total_quoted_pipeline: float
    total_won_revenue: float
    proposal_to_win_rate: float
    avg_proposal_value: float
    avg_discount_amount: float
    avg_negotiation_reduction: float


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/operations/deals/{deal_id}/proposals", response_model=ProposalRead, status_code=status.HTTP_201_CREATED)
def create_deal_proposal(
    deal_id: uuid.UUID,
    payload: ProposalCreate,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
):
    """Creates a new proposal for a qualified deal, initializes version 1, and updates deal stage."""
    deal = db.scalar(
        select(Deal).where(Deal.id == deal_id, Deal.workspace_id == workspace_id)
    )
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")

    lead = db.scalar(
        select(Lead).where(Lead.id == deal.lead_id, Lead.workspace_id == workspace_id)
    )
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated Lead not found")

    quoted = round(payload.base_price + payload.addons_total - payload.discount_amount, 2)
    if quoted < 0:
        quoted = 0.0

    # Generate sequential proposal number
    prop_count = db.scalar(
        select(func.count()).select_from(Proposal).where(Proposal.workspace_id == workspace_id)
    ) or 0
    prop_number = f"PROP-{datetime.now(UTC).year}-{prop_count + 1:04d}"

    proposal = Proposal(
        workspace_id=workspace_id,
        deal_id=deal.id,
        lead_id=lead.id,
        proposal_number=prop_number,
        title=payload.title,
        service_type=payload.service_type or deal.service_type,
        status="PROPOSAL_DRAFT",
        current_version=1,
        base_price=payload.base_price,
        addons_total=payload.addons_total,
        discount_amount=payload.discount_amount,
        quoted_amount=quoted,
        currency=payload.currency,
        scope_of_work=payload.scope_of_work,
        deliverables=payload.deliverables,
        timeline=payload.timeline,
        terms_and_conditions=payload.terms_and_conditions,
        expected_start_date=payload.expected_start_date,
        expiry_date=payload.expiry_date,
        notes=payload.notes,
    )
    db.add(proposal)
    db.flush()

    # Create Version 1 record (append-only history)
    v1 = ProposalVersion(
        workspace_id=workspace_id,
        proposal_id=proposal.id,
        version_number=1,
        base_price=payload.base_price,
        addons_total=payload.addons_total,
        discount_amount=payload.discount_amount,
        quoted_amount=quoted,
        scope_of_work=payload.scope_of_work,
        deliverables=payload.deliverables,
        timeline=payload.timeline,
        change_summary="Initial proposal draft created",
    )
    db.add(v1)

    # Sync Deal stage to PROPOSAL if not already beyond
    if deal.stage in ["NEW", "CONTACTED", "INTERESTED", "QUALIFIED"]:
        deal.stage = "PROPOSAL"

    # Append to Lead Activity Timeline
    action = LeadAction(
        workspace_id=workspace_id,
        lead_id=lead.id,
        channel="EMAIL",
        outcome="FOLLOW_UP_SCHEDULED",
        notes=f"Proposal {prop_number} drafted for {deal.service_type}: ₹{quoted:,.2f} (v1)",
    )
    db.add(action)

    db.commit()
    db.refresh(proposal)

    return get_proposal_detail(proposal_id=proposal.id, workspace_id=workspace_id, db=db)


@router.get("/operations/proposals", response_model=ProposalListResponse)
def list_proposals(
    status_filter: str | None = Query(None, alias="status"),
    service_type: str | None = None,
    deal_id: uuid.UUID | None = None,
    lead_id: uuid.UUID | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
):
    """Lists proposals for the workspace with multi-field filtering and zero N+1 queries."""
    stmt = select(Proposal, Lead.business_name, Deal.title).join(
        Lead, Proposal.lead_id == Lead.id
    ).join(
        Deal, Proposal.deal_id == Deal.id
    ).where(
        Proposal.workspace_id == workspace_id
    )

    if status_filter:
        stmt = stmt.where(Proposal.status == status_filter)
    if service_type:
        stmt = stmt.where(Proposal.service_type == service_type)
    if deal_id:
        stmt = stmt.where(Proposal.deal_id == deal_id)
    if lead_id:
        stmt = stmt.where(Proposal.lead_id == lead_id)
    if search:
        search_pattern = f"%{search}%"
        stmt = stmt.where(
            (Proposal.proposal_number.ilike(search_pattern))
            | (Proposal.title.ilike(search_pattern))
            | (Lead.business_name.ilike(search_pattern))
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    results_raw = db.execute(
        stmt.order_by(desc(Proposal.created_at)).limit(page_size).offset((page - 1) * page_size)
    ).all()

    proposals_out = []
    for prop, bus_name, d_title in results_raw:
        proposals_out.append(
            ProposalRead(
                id=prop.id,
                workspace_id=prop.workspace_id,
                deal_id=prop.deal_id,
                lead_id=prop.lead_id,
                client_name=bus_name,
                deal_title=d_title,
                proposal_number=prop.proposal_number,
                title=prop.title,
                service_type=prop.service_type,
                status=prop.status,
                current_version=prop.current_version,
                base_price=prop.base_price,
                addons_total=prop.addons_total,
                discount_amount=prop.discount_amount,
                quoted_amount=prop.quoted_amount,
                currency=prop.currency,
                scope_of_work=prop.scope_of_work,
                deliverables=prop.deliverables,
                timeline=prop.timeline,
                terms_and_conditions=prop.terms_and_conditions,
                expected_start_date=prop.expected_start_date,
                expiry_date=prop.expiry_date,
                sent_at=prop.sent_at,
                viewed_at=prop.viewed_at,
                accepted_at=prop.accepted_at,
                rejected_at=prop.rejected_at,
                rejection_reason=prop.rejection_reason,
                notes=prop.notes,
                created_at=prop.created_at,
                updated_at=prop.updated_at,
                versions=[],
            )
        )

    return ProposalListResponse(total=total, page=page, page_size=page_size, proposals=proposals_out)


@router.get("/operations/proposals/metrics", response_model=ProposalMetricsResponse)
def get_proposal_metrics(
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
):
    """Calculates closing intelligence KPIs, won revenue, and negotiation discounts."""
    proposals = db.scalars(
        select(Proposal).where(Proposal.workspace_id == workspace_id)
    ).all()

    total_proposals = len(proposals)
    draft_count = 0
    sent_count = 0
    viewed_count = 0
    negotiation_count = 0
    accepted_count = 0
    rejected_count = 0
    expired_count = 0
    total_quoted_pipeline = 0.0
    total_won_revenue = 0.0
    total_discounts = 0.0

    for p in proposals:
        total_quoted_pipeline += p.quoted_amount
        total_discounts += p.discount_amount

        if p.status == "PROPOSAL_DRAFT":
            draft_count += 1
        elif p.status == "PROPOSAL_SENT":
            sent_count += 1
        elif p.status == "VIEWED":
            viewed_count += 1
        elif p.status == "NEGOTIATION":
            negotiation_count += 1
        elif p.status == "ACCEPTED":
            accepted_count += 1
            total_won_revenue += p.quoted_amount
        elif p.status == "REJECTED":
            rejected_count += 1
        elif p.status == "EXPIRED":
            expired_count += 1

    closed_proposals = accepted_count + rejected_count + expired_count
    proposal_to_win_rate = (
        round((accepted_count / closed_proposals) * 100.0, 2) if closed_proposals > 0 else 0.0
    )
    avg_proposal_val = (
        round(total_quoted_pipeline / total_proposals, 2) if total_proposals > 0 else 0.0
    )
    avg_discount = (
        round(total_discounts / total_proposals, 2) if total_proposals > 0 else 0.0
    )

    # Calculate average negotiation price reduction
    accepted_proposals = [p for p in proposals if p.status == "ACCEPTED" and p.current_version > 1]
    reduction_sum = 0.0
    for ap in accepted_proposals:
        v1 = db.scalar(
            select(ProposalVersion).where(
                ProposalVersion.proposal_id == ap.id,
                ProposalVersion.version_number == 1,
            )
        )
        if v1 and v1.quoted_amount > ap.quoted_amount:
            reduction_sum += (v1.quoted_amount - ap.quoted_amount)

    avg_reduction = (
        round(reduction_sum / len(accepted_proposals), 2) if accepted_proposals else 0.0
    )

    return ProposalMetricsResponse(
        total_proposals=total_proposals,
        draft_count=draft_count,
        sent_count=sent_count,
        viewed_count=viewed_count,
        negotiation_count=negotiation_count,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        expired_count=expired_count,
        total_quoted_pipeline=round(total_quoted_pipeline, 2),
        total_won_revenue=round(total_won_revenue, 2),
        proposal_to_win_rate=proposal_to_win_rate,
        avg_proposal_value=avg_proposal_val,
        avg_discount_amount=avg_discount,
        avg_negotiation_reduction=avg_reduction,
    )


@router.get("/operations/proposals/{proposal_id}", response_model=ProposalRead)
def get_proposal_detail(
    proposal_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
):
    """Retrieves full proposal details including complete version history."""
    row = db.execute(
        select(Proposal, Lead.business_name, Deal.title)
        .join(Lead, Proposal.lead_id == Lead.id)
        .join(Deal, Proposal.deal_id == Deal.id)
        .where(Proposal.id == proposal_id, Proposal.workspace_id == workspace_id)
    ).first()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")

    prop, bus_name, d_title = row

    versions = db.scalars(
        select(ProposalVersion)
        .where(ProposalVersion.proposal_id == prop.id, ProposalVersion.workspace_id == workspace_id)
        .order_by(ProposalVersion.version_number)
    ).all()

    return ProposalRead(
        id=prop.id,
        workspace_id=prop.workspace_id,
        deal_id=prop.deal_id,
        lead_id=prop.lead_id,
        client_name=bus_name,
        deal_title=d_title,
        proposal_number=prop.proposal_number,
        title=prop.title,
        service_type=prop.service_type,
        status=prop.status,
        current_version=prop.current_version,
        base_price=prop.base_price,
        addons_total=prop.addons_total,
        discount_amount=prop.discount_amount,
        quoted_amount=prop.quoted_amount,
        currency=prop.currency,
        scope_of_work=prop.scope_of_work,
        deliverables=prop.deliverables,
        timeline=prop.timeline,
        terms_and_conditions=prop.terms_and_conditions,
        expected_start_date=prop.expected_start_date,
        expiry_date=prop.expiry_date,
        sent_at=prop.sent_at,
        viewed_at=prop.viewed_at,
        accepted_at=prop.accepted_at,
        rejected_at=prop.rejected_at,
        rejection_reason=prop.rejection_reason,
        notes=prop.notes,
        created_at=prop.created_at,
        updated_at=prop.updated_at,
        versions=[
            ProposalVersionRead(
                id=v.id,
                version_number=v.version_number,
                base_price=v.base_price,
                addons_total=v.addons_total,
                discount_amount=v.discount_amount,
                quoted_amount=v.quoted_amount,
                scope_of_work=v.scope_of_work,
                deliverables=v.deliverables,
                timeline=v.timeline,
                change_summary=v.change_summary,
                created_at=v.created_at,
            )
            for v in versions
        ],
    )


@router.post("/operations/proposals/{proposal_id}/versions", response_model=ProposalRead)
def create_proposal_version(
    proposal_id: uuid.UUID,
    payload: ProposalVersionCreate,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
):
    """Creates a new proposal version with updated pricing/scope, preserving previous versions."""
    prop = db.scalar(
        select(Proposal).where(Proposal.id == proposal_id, Proposal.workspace_id == workspace_id)
    )
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")

    new_ver = prop.current_version + 1
    new_quote = round(payload.base_price + payload.addons_total - payload.discount_amount, 2)
    if new_quote < 0:
        new_quote = 0.0

    ver_record = ProposalVersion(
        workspace_id=workspace_id,
        proposal_id=prop.id,
        version_number=new_ver,
        base_price=payload.base_price,
        addons_total=payload.addons_total,
        discount_amount=payload.discount_amount,
        quoted_amount=new_quote,
        scope_of_work=payload.scope_of_work or prop.scope_of_work,
        deliverables=payload.deliverables or prop.deliverables,
        timeline=payload.timeline or prop.timeline,
        change_summary=payload.change_summary or f"Revised to v{new_ver}: ₹{new_quote:,.2f}",
    )
    db.add(ver_record)

    # Update Proposal current values
    prop.current_version = new_ver
    prop.base_price = payload.base_price
    prop.addons_total = payload.addons_total
    prop.discount_amount = payload.discount_amount
    prop.quoted_amount = new_quote
    if payload.scope_of_work:
        prop.scope_of_work = payload.scope_of_work
    if payload.deliverables:
        prop.deliverables = payload.deliverables
    if payload.timeline:
        prop.timeline = payload.timeline
    prop.updated_at = datetime.now(UTC)

    # Add timeline entry
    action = LeadAction(
        workspace_id=workspace_id,
        lead_id=prop.lead_id,
        channel="EMAIL",
        outcome="FOLLOW_UP_SCHEDULED",
        notes=f"Proposal {prop.proposal_number} updated to v{new_ver}: ₹{new_quote:,.2f} ({payload.change_summary or 'Pricing revision'})",
    )
    db.add(action)

    db.commit()
    db.refresh(prop)

    return get_proposal_detail(proposal_id=prop.id, workspace_id=workspace_id, db=db)


@router.patch("/operations/proposals/{proposal_id}/status", response_model=ProposalRead)
def update_proposal_status(
    proposal_id: uuid.UUID,
    payload: ProposalStatusUpdate,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
):
    """Transitions proposal lifecycle status and synchronizes CRM deal stage & won revenue."""
    prop = db.scalar(
        select(Proposal).where(Proposal.id == proposal_id, Proposal.workspace_id == workspace_id)
    )
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")

    deal = db.scalar(
        select(Deal).where(Deal.id == prop.deal_id, Deal.workspace_id == workspace_id)
    )
    now = datetime.now(UTC)
    old_status = prop.status
    prop.status = payload.status
    prop.updated_at = now

    if payload.status == "PROPOSAL_SENT" and not prop.sent_at:
        prop.sent_at = now
        if deal and deal.stage in ["NEW", "CONTACTED", "INTERESTED", "QUALIFIED"]:
            deal.stage = "PROPOSAL"
    elif payload.status == "VIEWED" and not prop.viewed_at:
        prop.viewed_at = now
    elif payload.status == "NEGOTIATION":
        if deal:
            deal.stage = "NEGOTIATION"
    elif payload.status == "ACCEPTED":
        prop.accepted_at = now
        if deal:
            deal.stage = "WON"
            deal.deal_value = prop.quoted_amount  # Sync final won revenue to deal
            deal.closed_at = now
            deal.probability = 1.0

        # Create Won milestone on lead timeline
        action = LeadAction(
            workspace_id=workspace_id,
            lead_id=prop.lead_id,
            channel="PHONE",
            outcome="CONVERTED",
            notes=f"🎉 Proposal {prop.proposal_number} ACCEPTED! Closed revenue: ₹{prop.quoted_amount:,.2f}",
        )
        db.add(action)

    elif payload.status == "REJECTED":
        prop.rejected_at = now
        prop.rejection_reason = payload.rejection_reason or "Client declined proposal"
        if deal:
            deal.stage = "LOST"
            deal.win_loss_reason = prop.rejection_reason
            deal.closed_at = now
            deal.probability = 0.0

        action = LeadAction(
            workspace_id=workspace_id,
            lead_id=prop.lead_id,
            channel="PHONE",
            outcome="NOT_INTERESTED",
            notes=f"Proposal {prop.proposal_number} REJECTED. Reason: {prop.rejection_reason}",
        )
        db.add(action)

    elif payload.status == "EXPIRED":
        if deal and deal.stage in ["PROPOSAL", "NEGOTIATION"]:
            deal.notes = f"{deal.notes or ''} [Proposal {prop.proposal_number} expired]".strip()

    db.commit()
    db.refresh(prop)

    return get_proposal_detail(proposal_id=prop.id, workspace_id=workspace_id, db=db)
