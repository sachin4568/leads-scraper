from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.app.api import current_workspace_id
from backend.app.database import get_db
from backend.app.models import Customer, CustomerRetainer, DeliveryProject, LeadAction, ProjectDeliverable, UpsellOpportunity

router = APIRouter(tags=["Customer Success, Retention & Recurring Revenue"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class RetainerCreate(BaseModel):
    service_type: str = Field(..., min_length=2, max_length=64)
    billing_frequency: str = Field(..., pattern="^(MONTHLY|QUARTERLY|ANNUAL)$")
    billing_amount: float = Field(..., ge=0.0)
    currency: str = "INR"
    start_date: datetime | None = None
    duration_months: int = Field(1, ge=1, le=36)
    auto_renew: bool = True
    notes: str | None = None


class RetainerRead(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    customer_id: uuid.UUID
    customer_name: str
    service_type: str
    billing_frequency: str
    billing_amount: float
    monthly_mrr: float
    currency: str
    status: str
    start_date: datetime
    renewal_date: datetime
    auto_renew: bool
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class RetainerStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(ACTIVE|EXPIRING_SOON|RENEWED|EXPIRED|CANCELLED)$")
    notes: str | None = None


class UpsellOpportunityRead(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    customer_id: uuid.UUID
    customer_name: str
    service_type: str
    estimated_mrr: float
    estimated_value: float
    reason: str
    status: str
    created_at: datetime
    updated_at: datetime


class UpsellStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(IDENTIFIED|PITCHED|ACCEPTED|DECLINED)$")


class CustomerHealthRead(BaseModel):
    id: uuid.UUID
    company_name: str
    status: str
    health_score: str
    health_reason: str | None = None
    mrr: float
    arr: float
    lifetime_value: float
    next_renewal_date: datetime | None = None
    active_retainers_count: int
    last_activity_at: datetime | None = None


class SuccessMetricsResponse(BaseModel):
    total_customers: int
    active_customers: int
    healthy_customers: int
    at_risk_customers: int
    critical_customers: int
    dormant_customers: int
    total_mrr: float
    total_arr: float
    active_retainers_count: int
    renewals_due_30d_count: int
    expansion_pipeline_value: float
    avg_customer_ltv: float


# ─── Helper Functions ────────────────────────────────────────────────────────

def recalculate_customer_health_and_financials(db: Session, customer: Customer) -> None:
    """Deterministically computes MRR, ARR, Next Renewal Date, and Customer Health Score."""
    now = datetime.now(UTC)
    retainers = db.scalars(
        select(CustomerRetainer).where(
            CustomerRetainer.customer_id == customer.id,
            CustomerRetainer.workspace_id == customer.workspace_id,
        )
    ).all()

    active_retainers = [r for r in retainers if r.status in ["ACTIVE", "EXPIRING_SOON", "RENEWED"]]
    total_mrr = 0.0
    earliest_renewal: datetime | None = None

    for r in active_retainers:
        if r.renewal_date.tzinfo is None:
            r_renewal = r.renewal_date.replace(tzinfo=UTC)
        else:
            r_renewal = r.renewal_date

        if r_renewal <= now + timedelta(days=14) and r.status == "ACTIVE":
            r.status = "EXPIRING_SOON"
            r.updated_at = now

        total_mrr += r.monthly_mrr
        if earliest_renewal is None or r_renewal < earliest_renewal:
            earliest_renewal = r_renewal

    customer.mrr = round(total_mrr, 2)
    customer.arr = round(total_mrr * 12.0, 2)
    customer.next_renewal_date = earliest_renewal

    # Check Projects & Health Logic
    projects = db.scalars(
        select(DeliveryProject).where(
            DeliveryProject.customer_id == customer.id,
            DeliveryProject.workspace_id == customer.workspace_id,
        )
    ).all()

    has_expiring = any(r.status == "EXPIRING_SOON" for r in active_retainers)
    has_cancelled_or_expired = any(r.status in ["EXPIRED", "CANCELLED"] for r in retainers)
    has_active_projects = any(p.status in ["ONBOARDING", "REQUIREMENTS", "IN_PROGRESS", "REVIEW", "CLIENT_APPROVAL"] for p in projects)
    has_completed_projects = any(p.status == "COMPLETED" for p in projects)

    if has_expiring:
        customer.health_score = "AT_RISK"
        customer.health_reason = "Recurring contract renewal due within 14 days"
    elif has_cancelled_or_expired and len(active_retainers) == 0:
        customer.health_score = "CRITICAL"
        customer.health_reason = "Recurring retainer cancelled or expired without renewal"
    elif len(active_retainers) > 0 or has_active_projects:
        customer.health_score = "HEALTHY"
        customer.health_reason = "Active recurring contracts and ongoing project engagement"
    elif has_completed_projects and len(active_retainers) == 0:
        customer.health_score = "DORMANT"
        customer.health_reason = "Project delivered but no active recurring maintenance or retainers"
    else:
        customer.health_score = "HEALTHY"
        customer.health_reason = "Customer in good standing"

    customer.updated_at = now
    db.commit()
    db.refresh(customer)


def generate_deterministic_upsells_for_customer(db: Session, customer: Customer) -> None:
    """Generates rule-based expansion opportunities from existing delivery & retainer data."""
    projects = db.scalars(
        select(DeliveryProject).where(
            DeliveryProject.customer_id == customer.id,
            DeliveryProject.workspace_id == customer.workspace_id,
        )
    ).all()
    retainers = db.scalars(
        select(CustomerRetainer).where(
            CustomerRetainer.customer_id == customer.id,
            CustomerRetainer.workspace_id == customer.workspace_id,
        )
    ).all()

    existing_services = {p.service_type for p in projects} | {r.service_type for r in retainers}
    now = datetime.now(UTC)

    # Rule 1: Website delivered -> SEO Retainer
    if any("WEBSITE" in s for s in existing_services) and not any("SEO" in s for s in existing_services):
        exists = db.scalar(
            select(UpsellOpportunity).where(
                UpsellOpportunity.customer_id == customer.id,
                UpsellOpportunity.service_type == "SEO_RETAINER",
                UpsellOpportunity.workspace_id == customer.workspace_id,
            )
        )
        if not exists:
            opp = UpsellOpportunity(
                workspace_id=customer.workspace_id,
                customer_id=customer.id,
                service_type="SEO_RETAINER",
                estimated_mrr=15000.0,
                estimated_value=180000.0,
                reason="Website Modernization completed — Missing ongoing SEO & local search ranking retainer",
                status="IDENTIFIED",
                created_at=now,
            )
            db.add(opp)

    # Rule 2: Website delivered -> Maintenance Retainer
    if any("WEBSITE" in s for s in existing_services) and not any("MAINTENANCE" in s for s in existing_services):
        exists = db.scalar(
            select(UpsellOpportunity).where(
                UpsellOpportunity.customer_id == customer.id,
                UpsellOpportunity.service_type == "WEBSITE_MAINTENANCE",
                UpsellOpportunity.workspace_id == customer.workspace_id,
            )
        )
        if not exists:
            opp = UpsellOpportunity(
                workspace_id=customer.workspace_id,
                customer_id=customer.id,
                service_type="WEBSITE_MAINTENANCE",
                estimated_mrr=3000.0,
                estimated_value=36000.0,
                reason="Live production website — Recommended monthly security patches, backups & uptime SLA",
                status="IDENTIFIED",
                created_at=now,
            )
            db.add(opp)

    # Rule 3: Website or SEO -> SMMA Retainer
    if (any("WEBSITE" in s for s in existing_services) or any("SEO" in s for s in existing_services)) and not any("SMMA" in s for s in existing_services):
        exists = db.scalar(
            select(UpsellOpportunity).where(
                UpsellOpportunity.customer_id == customer.id,
                UpsellOpportunity.service_type == "SMMA_RETAINER",
                UpsellOpportunity.workspace_id == customer.workspace_id,
            )
        )
        if not exists:
            opp = UpsellOpportunity(
                workspace_id=customer.workspace_id,
                customer_id=customer.id,
                service_type="SMMA_RETAINER",
                estimated_mrr=20000.0,
                estimated_value=240000.0,
                reason="Established digital foundation — Ready for social media management & brand campaigns",
                status="IDENTIFIED",
                created_at=now,
            )
            db.add(opp)

    db.commit()


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/operations/success/metrics", response_model=SuccessMetricsResponse)
def get_success_metrics(
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
):
    """Aggregates customer health, MRR, ARR, renewals, and expansion pipeline metrics."""
    customers = db.scalars(
        select(Customer).where(Customer.workspace_id == workspace_id)
    ).all()
    retainers = db.scalars(
        select(CustomerRetainer).where(CustomerRetainer.workspace_id == workspace_id)
    ).all()
    upsells = db.scalars(
        select(UpsellOpportunity).where(
            UpsellOpportunity.workspace_id == workspace_id,
            UpsellOpportunity.status.in_(["IDENTIFIED", "PITCHED"]),
        )
    ).all()

    now = datetime.now(UTC)
    total_cust = len(customers)
    active_cust = sum(1 for c in customers if c.status in ["ACTIVE", "ONBOARDING"])
    healthy_c = sum(1 for c in customers if c.health_score == "HEALTHY")
    at_risk_c = sum(1 for c in customers if c.health_score == "AT_RISK")
    critical_c = sum(1 for c in customers if c.health_score == "CRITICAL")
    dormant_c = sum(1 for c in customers if c.health_score == "DORMANT")

    active_retainers_list = [r for r in retainers if r.status in ["ACTIVE", "EXPIRING_SOON", "RENEWED"]]
    total_mrr = sum(r.monthly_mrr for r in active_retainers_list)
    total_arr = total_mrr * 12.0
    active_retainers = len(active_retainers_list)

    renewals_30d = 0
    for r in retainers:
        if r.status in ["ACTIVE", "EXPIRING_SOON"]:
            r_renewal = r.renewal_date.replace(tzinfo=UTC) if r.renewal_date.tzinfo is None else r.renewal_date
            if now <= r_renewal <= now + timedelta(days=30):
                renewals_30d += 1

    expansion_val = sum(u.estimated_value for u in upsells)
    avg_ltv = round(sum(c.lifetime_value for c in customers) / total_cust, 2) if total_cust > 0 else 0.0

    return SuccessMetricsResponse(
        total_customers=total_cust,
        active_customers=active_cust,
        healthy_customers=healthy_c,
        at_risk_customers=at_risk_c,
        critical_customers=critical_c,
        dormant_customers=dormant_c,
        total_mrr=round(total_mrr, 2),
        total_arr=round(total_arr, 2),
        active_retainers_count=active_retainers,
        renewals_due_30d_count=renewals_30d,
        expansion_pipeline_value=round(expansion_val, 2),
        avg_customer_ltv=avg_ltv,
    )


@router.post("/operations/customers/{customer_id}/retainers", response_model=RetainerRead, status_code=status.HTTP_201_CREATED)
def create_customer_retainer(
    customer_id: uuid.UUID,
    payload: RetainerCreate,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
):
    """Creates a new recurring retainer contract for a customer and updates MRR/ARR."""
    customer = db.scalar(
        select(Customer).where(Customer.id == customer_id, Customer.workspace_id == workspace_id)
    )
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    now = datetime.now(UTC)
    start_dt = payload.start_date or now

    # Calculate monthly MRR contribution
    if payload.billing_frequency == "MONTHLY":
        monthly_mrr = payload.billing_amount
        renewal_dt = start_dt + timedelta(days=30 * payload.duration_months)
    elif payload.billing_frequency == "QUARTERLY":
        monthly_mrr = payload.billing_amount / 3.0
        renewal_dt = start_dt + timedelta(days=90 * payload.duration_months)
    else:  # ANNUAL
        monthly_mrr = payload.billing_amount / 12.0
        renewal_dt = start_dt + timedelta(days=365 * payload.duration_months)

    retainer = CustomerRetainer(
        workspace_id=workspace_id,
        customer_id=customer.id,
        service_type=payload.service_type,
        billing_frequency=payload.billing_frequency,
        billing_amount=payload.billing_amount,
        monthly_mrr=round(monthly_mrr, 2),
        currency=payload.currency,
        status="ACTIVE",
        start_date=start_dt,
        renewal_date=renewal_dt,
        auto_renew=payload.auto_renew,
        notes=payload.notes,
    )
    db.add(retainer)
    db.flush()

    # Update customer lifetime value and financials
    customer.lifetime_value += payload.billing_amount
    customer.last_activity_at = now
    recalculate_customer_health_and_financials(db=db, customer=customer)
    generate_deterministic_upsells_for_customer(db=db, customer=customer)

    if customer.lead_id:
        action = LeadAction(
            workspace_id=workspace_id,
            lead_id=customer.lead_id,
            channel="OTHER",
            outcome="CONVERTED",
            notes=f"🔄 Recurring Retainer Started: {payload.service_type} at ₹{payload.billing_amount:,.2f}/{payload.billing_frequency.lower()} (MRR: +₹{monthly_mrr:,.2f})",
        )
        db.add(action)

    db.commit()
    db.refresh(retainer)

    return RetainerRead(
        id=retainer.id,
        workspace_id=retainer.workspace_id,
        customer_id=retainer.customer_id,
        customer_name=customer.company_name,
        service_type=retainer.service_type,
        billing_frequency=retainer.billing_frequency,
        billing_amount=retainer.billing_amount,
        monthly_mrr=retainer.monthly_mrr,
        currency=retainer.currency,
        status=retainer.status,
        start_date=retainer.start_date,
        renewal_date=retainer.renewal_date,
        auto_renew=retainer.auto_renew,
        notes=retainer.notes,
        created_at=retainer.created_at,
        updated_at=retainer.updated_at,
    )


@router.get("/operations/retainers", response_model=list[RetainerRead])
def list_retainers(
    status_filter: str | None = Query(None, alias="status"),
    customer_id: uuid.UUID | None = None,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
):
    """Lists recurring retainers with customer names and status filters."""
    stmt = select(CustomerRetainer, Customer.company_name).join(
        Customer, CustomerRetainer.customer_id == Customer.id
    ).where(CustomerRetainer.workspace_id == workspace_id)

    if status_filter:
        stmt = stmt.where(CustomerRetainer.status == status_filter)
    if customer_id:
        stmt = stmt.where(CustomerRetainer.customer_id == customer_id)

    results = db.execute(stmt.order_by(desc(CustomerRetainer.created_at))).all()

    retainers_out = []
    for ret, cust_name in results:
        retainers_out.append(
            RetainerRead(
                id=ret.id,
                workspace_id=ret.workspace_id,
                customer_id=ret.customer_id,
                customer_name=cust_name,
                service_type=ret.service_type,
                billing_frequency=ret.billing_frequency,
                billing_amount=ret.billing_amount,
                monthly_mrr=ret.monthly_mrr,
                currency=ret.currency,
                status=ret.status,
                start_date=ret.start_date,
                renewal_date=ret.renewal_date,
                auto_renew=ret.auto_renew,
                notes=ret.notes,
                created_at=ret.created_at,
                updated_at=ret.updated_at,
            )
        )
    return retainers_out


@router.patch("/operations/retainers/{retainer_id}/renew", response_model=RetainerRead)
def renew_retainer(
    retainer_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
):
    """Renews a recurring retainer contract, advances renewal date, and updates customer LTV."""
    ret = db.scalar(
        select(CustomerRetainer).where(
            CustomerRetainer.id == retainer_id, CustomerRetainer.workspace_id == workspace_id
        )
    )
    if not ret:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retainer not found")

    customer = db.scalar(
        select(Customer).where(Customer.id == ret.customer_id, Customer.workspace_id == workspace_id)
    )
    now = datetime.now(UTC)

    if ret.billing_frequency == "MONTHLY":
        ret.renewal_date = ret.renewal_date + timedelta(days=30)
    elif ret.billing_frequency == "QUARTERLY":
        ret.renewal_date = ret.renewal_date + timedelta(days=90)
    else:  # ANNUAL
        ret.renewal_date = ret.renewal_date + timedelta(days=365)

    ret.status = "ACTIVE"
    ret.updated_at = now

    if customer:
        customer.lifetime_value += ret.billing_amount
        customer.last_activity_at = now
        recalculate_customer_health_and_financials(db=db, customer=customer)

        if customer.lead_id:
            action = LeadAction(
                workspace_id=workspace_id,
                lead_id=customer.lead_id,
                channel="OTHER",
                outcome="CONVERTED",
                notes=f"🎉 Retainer RENEWED: {ret.service_type} renewed for ₹{ret.billing_amount:,.2f}. Next renewal: {ret.renewal_date.strftime('%Y-%m-%d')}.",
            )
            db.add(action)

    db.commit()
    db.refresh(ret)

    return RetainerRead(
        id=ret.id,
        workspace_id=ret.workspace_id,
        customer_id=ret.customer_id,
        customer_name=customer.company_name if customer else "Customer",
        service_type=ret.service_type,
        billing_frequency=ret.billing_frequency,
        billing_amount=ret.billing_amount,
        monthly_mrr=ret.monthly_mrr,
        currency=ret.currency,
        status=ret.status,
        start_date=ret.start_date,
        renewal_date=ret.renewal_date,
        auto_renew=ret.auto_renew,
        notes=ret.notes,
        created_at=ret.created_at,
        updated_at=ret.updated_at,
    )


@router.patch("/operations/retainers/{retainer_id}/status", response_model=RetainerRead)
def update_retainer_status(
    retainer_id: uuid.UUID,
    payload: RetainerStatusUpdate,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
):
    """Updates recurring retainer status and recalculates customer health."""
    ret = db.scalar(
        select(CustomerRetainer).where(
            CustomerRetainer.id == retainer_id, CustomerRetainer.workspace_id == workspace_id
        )
    )
    if not ret:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retainer not found")

    customer = db.scalar(
        select(Customer).where(Customer.id == ret.customer_id, Customer.workspace_id == workspace_id)
    )
    now = datetime.now(UTC)
    ret.status = payload.status
    if payload.notes:
        ret.notes = payload.notes
    ret.updated_at = now

    if customer:
        customer.last_activity_at = now
        recalculate_customer_health_and_financials(db=db, customer=customer)

    db.commit()
    db.refresh(ret)

    return RetainerRead(
        id=ret.id,
        workspace_id=ret.workspace_id,
        customer_id=ret.customer_id,
        customer_name=customer.company_name if customer else "Customer",
        service_type=ret.service_type,
        billing_frequency=ret.billing_frequency,
        billing_amount=ret.billing_amount,
        monthly_mrr=ret.monthly_mrr,
        currency=ret.currency,
        status=ret.status,
        start_date=ret.start_date,
        renewal_date=ret.renewal_date,
        auto_renew=ret.auto_renew,
        notes=ret.notes,
        created_at=ret.created_at,
        updated_at=ret.updated_at,
    )


@router.get("/operations/success/upsells", response_model=list[UpsellOpportunityRead])
def list_upsell_opportunities(
    status_filter: str | None = Query(None, alias="status"),
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
):
    """Lists deterministic expansion and upsell opportunities across customers."""
    stmt = select(UpsellOpportunity, Customer.company_name).join(
        Customer, UpsellOpportunity.customer_id == Customer.id
    ).where(UpsellOpportunity.workspace_id == workspace_id)

    if status_filter:
        stmt = stmt.where(UpsellOpportunity.status == status_filter)

    results = db.execute(stmt.order_by(desc(UpsellOpportunity.created_at))).all()

    upsells_out = []
    for opp, cust_name in results:
        upsells_out.append(
            UpsellOpportunityRead(
                id=opp.id,
                workspace_id=opp.workspace_id,
                customer_id=opp.customer_id,
                customer_name=cust_name,
                service_type=opp.service_type,
                estimated_mrr=opp.estimated_mrr,
                estimated_value=opp.estimated_value,
                reason=opp.reason,
                status=opp.status,
                created_at=opp.created_at,
                updated_at=opp.updated_at,
            )
        )
    return upsells_out


@router.patch("/operations/success/upsells/{upsell_id}/status", response_model=UpsellOpportunityRead)
def update_upsell_status(
    upsell_id: uuid.UUID,
    payload: UpsellStatusUpdate,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
):
    """Updates upsell pitch status; on ACCEPTED, automatically starts the recurring retainer."""
    opp = db.scalar(
        select(UpsellOpportunity).where(
            UpsellOpportunity.id == upsell_id, UpsellOpportunity.workspace_id == workspace_id
        )
    )
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upsell opportunity not found")

    customer = db.scalar(
        select(Customer).where(Customer.id == opp.customer_id, Customer.workspace_id == workspace_id)
    )
    now = datetime.now(UTC)
    opp.status = payload.status
    opp.updated_at = now

    if payload.status == "ACCEPTED" and customer:
        # Convert upsell into active recurring retainer
        retainer = CustomerRetainer(
            workspace_id=workspace_id,
            customer_id=customer.id,
            service_type=opp.service_type,
            billing_frequency="MONTHLY",
            billing_amount=opp.estimated_mrr,
            monthly_mrr=opp.estimated_mrr,
            currency="INR",
            status="ACTIVE",
            start_date=now,
            renewal_date=now + timedelta(days=30),
            auto_renew=True,
            notes=f"Upsell Accepted: {opp.reason}",
        )
        db.add(retainer)
        customer.lifetime_value += opp.estimated_mrr
        recalculate_customer_health_and_financials(db=db, customer=customer)

    db.commit()
    db.refresh(opp)

    return UpsellOpportunityRead(
        id=opp.id,
        workspace_id=opp.workspace_id,
        customer_id=opp.customer_id,
        customer_name=customer.company_name if customer else "Customer",
        service_type=opp.service_type,
        estimated_mrr=opp.estimated_mrr,
        estimated_value=opp.estimated_value,
        reason=opp.reason,
        status=opp.status,
        created_at=opp.created_at,
        updated_at=opp.updated_at,
    )


@router.get("/operations/success/health", response_model=list[CustomerHealthRead])
def get_customer_health_matrix(
    health_score: str | None = None,
    workspace_id: uuid.UUID = Depends(current_workspace_id),
    db: Session = Depends(get_db),
):
    """Re-evaluates and returns the customer retention & health matrix."""
    customers = db.scalars(
        select(Customer).where(Customer.workspace_id == workspace_id)
    ).all()

    for c in customers:
        recalculate_customer_health_and_financials(db=db, customer=c)
        generate_deterministic_upsells_for_customer(db=db, customer=c)

    stmt = select(Customer).where(Customer.workspace_id == workspace_id)
    if health_score:
        stmt = stmt.where(Customer.health_score == health_score)

    customers_evaluated = db.scalars(stmt.order_by(desc(Customer.mrr))).all()

    health_out = []
    for c in customers_evaluated:
        r_count = db.scalar(
            select(func.count()).select_from(CustomerRetainer).where(
                CustomerRetainer.customer_id == c.id,
                CustomerRetainer.status.in_(["ACTIVE", "EXPIRING_SOON", "RENEWED"]),
            )
        ) or 0
        health_out.append(
            CustomerHealthRead(
                id=c.id,
                company_name=c.company_name,
                status=c.status,
                health_score=c.health_score,
                health_reason=c.health_reason,
                mrr=c.mrr,
                arr=c.arr,
                lifetime_value=c.lifetime_value,
                next_renewal_date=c.next_renewal_date,
                active_retainers_count=r_count,
                last_activity_at=c.last_activity_at,
            )
        )
    return health_out
