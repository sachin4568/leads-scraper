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
from backend.app.models import Customer, Deal, DeliveryProject, Lead, LeadAction, ProjectDeliverable, Proposal

router = APIRouter(tags=["Customer Onboarding & Delivery Management"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class DeliverableRead(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    status: str
    due_date: datetime | None = None
    completed_at: datetime | None = None
    sort_order: int
    notes: str | None = None
    created_at: datetime


class DeliverableCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    due_date: datetime | None = None
    notes: str | None = None


class DeliverableStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(PENDING|IN_PROGRESS|COMPLETED|BLOCKED)$")


class DeliveryProjectRead(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    customer_id: uuid.UUID
    deal_id: uuid.UUID | None = None
    proposal_id: uuid.UUID | None = None
    customer_name: str
    project_name: str
    service_type: str
    contract_value: float
    currency: str
    status: str
    progress_percent: float
    start_date: datetime | None = None
    target_completion_date: datetime | None = None
    actual_completion_date: datetime | None = None
    owner: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    deliverables: list[DeliverableRead] = []


class DeliveryProjectStatusUpdate(BaseModel):
    status: str = Field(
        ...,
        pattern="^(ONBOARDING|REQUIREMENTS|IN_PROGRESS|REVIEW|CLIENT_APPROVAL|COMPLETED|ON_HOLD|CANCELLED)$",
    )


class DeliveryProjectListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    projects: list[DeliveryProjectRead]


class CustomerRead(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    lead_id: uuid.UUID | None = None
    company_name: str
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    website: str | None = None
    status: str
    lifetime_value: float
    currency: str
    notes: str | None = None
    onboarded_at: datetime
    created_at: datetime
    updated_at: datetime
    projects_count: int = 0


class CustomerListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    customers: list[CustomerRead]


class DeliveryMetricsResponse(BaseModel):
    total_customers: int
    active_customers: int
    total_projects: int
    active_projects: int
    completed_projects: int
    in_delivery_revenue: float
    realized_completed_revenue: float
    avg_project_progress: float
    on_time_delivery_rate: float


# ─── Helper Functions ────────────────────────────────────────────────────────

def recalculate_project_progress(db: Session, project: DeliveryProject) -> float:
    """Calculates progress percent dynamically based on completed deliverables."""
    total_deliverables = db.scalar(
        select(func.count()).select_from(ProjectDeliverable).where(ProjectDeliverable.project_id == project.id)
    ) or 0

    if total_deliverables == 0:
        return 0.0

    completed = db.scalar(
        select(func.count()).select_from(ProjectDeliverable).where(
            ProjectDeliverable.project_id == project.id,
            ProjectDeliverable.status == "COMPLETED",
        )
    ) or 0

    progress = round((completed / total_deliverables) * 100.0, 1)
    project.progress_percent = progress
    db.commit()
    db.refresh(project)
    return progress


def seed_standard_deliverables(db: Session, project: DeliveryProject, service_type: str) -> None:
    """Seeds initial deliverables based on the contracted service."""
    now = datetime.now(UTC)
    template_items = [
        "Client Onboarding & Assets Handoff",
        "Technical Requirements Specification",
        "Design Wireframes & Architecture",
        "Core Development & Integration",
        "QA & Cross-Device Verification",
        "Client Review & Final Approval",
    ]
    if service_type == "SEO":
        template_items = [
            "Technical SEO Audit & Keyword Mapping",
            "On-Page Optimization & Meta Structuring",
            "Schema Markup & Local GMB Linking",
            "Performance Speed Optimization",
            "Analytics & Search Console Reporting",
        ]
    elif service_type == "SMMA":
        template_items = [
            "Content Strategy & Brand Guidelines",
            "Creative Ad Assets & Copywriting",
            "Campaign Setup & Pixel Tracking",
            "Audience Targeting & Launch",
            "Weekly Analytics & ROAS Review",
        ]

    for idx, title in enumerate(template_items, 1):
        deliv = ProjectDeliverable(
            workspace_id=project.workspace_id,
            project_id=project.id,
            title=title,
            status="PENDING",
            sort_order=idx,
            created_at=now,
        )
        db.add(deliv)
    db.commit()


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/operations/delivery/metrics", response_model=DeliveryMetricsResponse)
def get_delivery_metrics(
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
):
    """Calculates delivery management KPIs, active work, and realized revenue."""
    customers = db.scalars(
        select(Customer).where(Customer.workspace_id == workspace_id)
    ).all()
    projects = db.scalars(
        select(DeliveryProject).where(DeliveryProject.workspace_id == workspace_id)
    ).all()

    total_cust = len(customers)
    active_cust = sum(1 for c in customers if c.status in ["ACTIVE", "ONBOARDING"])

    total_proj = len(projects)
    active_proj = 0
    completed_proj = 0
    in_delivery_rev = 0.0
    realized_rev = 0.0
    progress_sum = 0.0

    for p in projects:
        progress_sum += p.progress_percent
        if p.status in ["ONBOARDING", "REQUIREMENTS", "IN_PROGRESS", "REVIEW", "CLIENT_APPROVAL"]:
            active_proj += 1
            in_delivery_rev += p.contract_value
        elif p.status == "COMPLETED":
            completed_proj += 1
            realized_rev += p.contract_value

    avg_prog = round(progress_sum / total_proj, 1) if total_proj > 0 else 0.0
    on_time_rate = round((completed_proj / total_proj) * 100.0, 1) if total_proj > 0 else 100.0

    return DeliveryMetricsResponse(
        total_customers=total_cust,
        active_customers=active_cust,
        total_projects=total_proj,
        active_projects=active_proj,
        completed_projects=completed_proj,
        in_delivery_revenue=round(in_delivery_rev, 2),
        realized_completed_revenue=round(realized_rev, 2),
        avg_project_progress=avg_prog,
        on_time_delivery_rate=on_time_rate,
    )


@router.post("/operations/deals/{deal_id}/convert-to-customer", response_model=DeliveryProjectRead, status_code=status.HTTP_201_CREATED)
def convert_deal_to_customer(
    deal_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
):
    """Converts a WON CRM deal into an active Customer record and creates a Delivery Project."""
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

    # Check if proposal exists for this deal
    accepted_prop = db.scalar(
        select(Proposal).where(
            Proposal.deal_id == deal.id,
            Proposal.workspace_id == workspace_id,
            Proposal.status == "ACCEPTED",
        )
    )

    contract_val = accepted_prop.quoted_amount if accepted_prop else deal.deal_value

    # Find or Create Customer
    customer = db.scalar(
        select(Customer).where(
            Customer.lead_id == lead.id,
            Customer.workspace_id == workspace_id,
        )
    )
    now = datetime.now(UTC)
    if not customer:
        customer = Customer(
            workspace_id=workspace_id,
            lead_id=lead.id,
            company_name=lead.business_name,
            contact_email=lead.email,
            contact_phone=lead.phone,
            website=lead.website,
            status="ONBOARDING",
            lifetime_value=contract_val,
            onboarded_at=now,
        )
        db.add(customer)
        db.flush()
    else:
        customer.lifetime_value += contract_val
        customer.status = "ACTIVE"
        customer.updated_at = now

    # Ensure Deal is marked WON
    deal.stage = "WON"
    deal.closed_at = deal.closed_at or now

    # Create Delivery Project
    project = DeliveryProject(
        workspace_id=workspace_id,
        customer_id=customer.id,
        deal_id=deal.id,
        proposal_id=accepted_prop.id if accepted_prop else None,
        project_name=f"{customer.company_name} — {deal.service_type.replace('_', ' ').title()}",
        service_type=deal.service_type,
        contract_value=contract_val,
        status="ONBOARDING",
        progress_percent=0.0,
        start_date=now,
    )
    db.add(project)
    db.flush()

    # Seed Standard Deliverables
    seed_standard_deliverables(db=db, project=project, service_type=deal.service_type)

    # Append Delivery Milestone to Lead Action Timeline
    action = LeadAction(
        workspace_id=workspace_id,
        lead_id=lead.id,
        channel="OTHER",
        outcome="CONVERTED",
        notes=f"🚀 Customer Onboarding Initiated: Project '{project.project_name}' created with ₹{contract_val:,.2f} contract value.",
    )
    db.add(action)

    db.commit()
    db.refresh(project)

    return get_project_detail(project_id=project.id, workspace_id=workspace_id, db=db)


@router.get("/operations/customers", response_model=CustomerListResponse)
def list_customers(
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
):
    """Lists customers for the workspace with search and status filters."""
    stmt = select(Customer).where(Customer.workspace_id == workspace_id)

    if status_filter:
        stmt = stmt.where(Customer.status == status_filter)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            (Customer.company_name.ilike(pattern))
            | (Customer.contact_email.ilike(pattern))
            | (Customer.contact_phone.ilike(pattern))
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    customers_raw = db.scalars(
        stmt.order_by(desc(Customer.created_at)).limit(page_size).offset((page - 1) * page_size)
    ).all()

    cust_out = []
    for c in customers_raw:
        p_count = db.scalar(
            select(func.count()).select_from(DeliveryProject).where(
                DeliveryProject.customer_id == c.id,
                DeliveryProject.workspace_id == workspace_id,
            )
        ) or 0
        cust_out.append(
            CustomerRead(
                id=c.id,
                workspace_id=c.workspace_id,
                lead_id=c.lead_id,
                company_name=c.company_name,
                contact_name=c.contact_name,
                contact_email=c.contact_email,
                contact_phone=c.contact_phone,
                website=c.website,
                status=c.status,
                lifetime_value=c.lifetime_value,
                currency=c.currency,
                notes=c.notes,
                onboarded_at=c.onboarded_at,
                created_at=c.created_at,
                updated_at=c.updated_at,
                projects_count=p_count,
            )
        )

    return CustomerListResponse(total=total, page=page, page_size=page_size, customers=cust_out)


@router.get("/operations/delivery/projects", response_model=DeliveryProjectListResponse)
def list_delivery_projects(
    status_filter: str | None = Query(None, alias="status"),
    service_type: str | None = None,
    customer_id: uuid.UUID | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
):
    """Lists delivery projects with customer name and deliverables."""
    stmt = select(DeliveryProject, Customer.company_name).join(
        Customer, DeliveryProject.customer_id == Customer.id
    ).where(
        DeliveryProject.workspace_id == workspace_id
    )

    if status_filter:
        stmt = stmt.where(DeliveryProject.status == status_filter)
    if service_type:
        stmt = stmt.where(DeliveryProject.service_type == service_type)
    if customer_id:
        stmt = stmt.where(DeliveryProject.customer_id == customer_id)
    if search:
        pat = f"%{search}%"
        stmt = stmt.where(
            (DeliveryProject.project_name.ilike(pat)) | (Customer.company_name.ilike(pat))
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    results_raw = db.execute(
        stmt.order_by(desc(DeliveryProject.created_at)).limit(page_size).offset((page - 1) * page_size)
    ).all()

    projects_out = []
    for proj, cust_name in results_raw:
        projects_out.append(
            DeliveryProjectRead(
                id=proj.id,
                workspace_id=proj.workspace_id,
                customer_id=proj.customer_id,
                deal_id=proj.deal_id,
                proposal_id=proj.proposal_id,
                customer_name=cust_name,
                project_name=proj.project_name,
                service_type=proj.service_type,
                contract_value=proj.contract_value,
                currency=proj.currency,
                status=proj.status,
                progress_percent=proj.progress_percent,
                start_date=proj.start_date,
                target_completion_date=proj.target_completion_date,
                actual_completion_date=proj.actual_completion_date,
                owner=proj.owner,
                notes=proj.notes,
                created_at=proj.created_at,
                updated_at=proj.updated_at,
                deliverables=[],
            )
        )

    return DeliveryProjectListResponse(total=total, page=page, page_size=page_size, projects=projects_out)


@router.get("/operations/delivery/projects/{project_id}", response_model=DeliveryProjectRead)
def get_project_detail(
    project_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
):
    """Retrieves full delivery project details including all deliverable items."""
    row = db.execute(
        select(DeliveryProject, Customer.company_name)
        .join(Customer, DeliveryProject.customer_id == Customer.id)
        .where(DeliveryProject.id == project_id, DeliveryProject.workspace_id == workspace_id)
    ).first()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery project not found")

    proj, cust_name = row

    deliverables = db.scalars(
        select(ProjectDeliverable)
        .where(ProjectDeliverable.project_id == proj.id, ProjectDeliverable.workspace_id == workspace_id)
        .order_by(ProjectDeliverable.sort_order)
    ).all()

    return DeliveryProjectRead(
        id=proj.id,
        workspace_id=proj.workspace_id,
        customer_id=proj.customer_id,
        deal_id=proj.deal_id,
        proposal_id=proj.proposal_id,
        customer_name=cust_name,
        project_name=proj.project_name,
        service_type=proj.service_type,
        contract_value=proj.contract_value,
        currency=proj.currency,
        status=proj.status,
        progress_percent=proj.progress_percent,
        start_date=proj.start_date,
        target_completion_date=proj.target_completion_date,
        actual_completion_date=proj.actual_completion_date,
        owner=proj.owner,
        notes=proj.notes,
        created_at=proj.created_at,
        updated_at=proj.updated_at,
        deliverables=[
            DeliverableRead(
                id=d.id,
                project_id=d.project_id,
                title=d.title,
                status=d.status,
                due_date=d.due_date,
                completed_at=d.completed_at,
                sort_order=d.sort_order,
                notes=d.notes,
                created_at=d.created_at,
            )
            for d in deliverables
        ],
    )


@router.patch("/operations/delivery/projects/{project_id}/status", response_model=DeliveryProjectRead)
def update_project_status(
    project_id: uuid.UUID,
    payload: DeliveryProjectStatusUpdate,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
):
    """Transitions delivery project stages and updates timeline milestones."""
    proj = db.scalar(
        select(DeliveryProject).where(
            DeliveryProject.id == project_id, DeliveryProject.workspace_id == workspace_id
        )
    )
    if not proj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    now = datetime.now(UTC)
    proj.status = payload.status
    proj.updated_at = now

    if payload.status == "COMPLETED":
        proj.actual_completion_date = now
        proj.progress_percent = 100.0

    customer = db.scalar(
        select(Customer).where(Customer.id == proj.customer_id, Customer.workspace_id == workspace_id)
    )
    if customer and customer.lead_id:
        action = LeadAction(
            workspace_id=workspace_id,
            lead_id=customer.lead_id,
            channel="OTHER",
            outcome="CONVERTED",
            notes=f"Delivery Stage Updated: Project '{proj.project_name}' moved to {payload.status}.",
        )
        db.add(action)

    db.commit()
    db.refresh(proj)

    return get_project_detail(project_id=proj.id, workspace_id=workspace_id, db=db)


@router.post("/operations/delivery/projects/{project_id}/deliverables", response_model=DeliverableRead, status_code=status.HTTP_201_CREATED)
def add_project_deliverable(
    project_id: uuid.UUID,
    payload: DeliverableCreate,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
):
    """Adds a new deliverable milestone to a delivery project."""
    proj = db.scalar(
        select(DeliveryProject).where(
            DeliveryProject.id == project_id, DeliveryProject.workspace_id == workspace_id
        )
    )
    if not proj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    cur_count = db.scalar(
        select(func.count()).select_from(ProjectDeliverable).where(
            ProjectDeliverable.project_id == proj.id
        )
    ) or 0

    deliv = ProjectDeliverable(
        workspace_id=workspace_id,
        project_id=proj.id,
        title=payload.title,
        status="PENDING",
        due_date=payload.due_date,
        sort_order=cur_count + 1,
        notes=payload.notes,
    )
    db.add(deliv)
    db.commit()
    db.refresh(deliv)

    recalculate_project_progress(db=db, project=proj)

    return DeliverableRead(
        id=deliv.id,
        project_id=deliv.project_id,
        title=deliv.title,
        status=deliv.status,
        due_date=deliv.due_date,
        completed_at=deliv.completed_at,
        sort_order=deliv.sort_order,
        notes=deliv.notes,
        created_at=deliv.created_at,
    )


@router.patch("/operations/delivery/deliverables/{deliverable_id}", response_model=DeliverableRead)
def update_deliverable_status(
    deliverable_id: uuid.UUID,
    payload: DeliverableStatusUpdate,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
):
    """Updates deliverable status and recalculates overall project progress percent."""
    deliv = db.scalar(
        select(ProjectDeliverable).where(
            ProjectDeliverable.id == deliverable_id,
            ProjectDeliverable.workspace_id == workspace_id,
        )
    )
    if not deliv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deliverable not found")

    deliv.status = payload.status
    if payload.status == "COMPLETED":
        deliv.completed_at = datetime.now(UTC)
    else:
        deliv.completed_at = None

    db.commit()
    db.refresh(deliv)

    proj = db.scalar(
        select(DeliveryProject).where(
            DeliveryProject.id == deliv.project_id,
            DeliveryProject.workspace_id == workspace_id,
        )
    )
    if proj:
        recalculate_project_progress(db=db, project=proj)

    return DeliverableRead(
        id=deliv.id,
        project_id=deliv.project_id,
        title=deliv.title,
        status=deliv.status,
        due_date=deliv.due_date,
        completed_at=deliv.completed_at,
        sort_order=deliv.sort_order,
        notes=deliv.notes,
        created_at=deliv.created_at,
    )
