from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class HumanOutcome(str, Enum):
    GENUINE_PRODUCTIVE = "GENUINE_PRODUCTIVE"
    GENUINE_UNPRODUCTIVE = "GENUINE_UNPRODUCTIVE"
    NOT_GENUINE = "NOT_GENUINE"
    INCORRECT_SERVICE_MATCH = "INCORRECT_SERVICE_MATCH"
    BAD_CONTACT = "BAD_CONTACT"
    DECISION_MAKER_NOT_FOUND = "DECISION_MAKER_NOT_FOUND"
    DUPLICATE = "DUPLICATE"


class ContactRole(str, Enum):
    OWNER = "OWNER"
    CEO = "CEO"
    DECISION_MAKER = "DECISION_MAKER"
    MARKETING_MANAGER = "MARKETING_MANAGER"
    DEPARTMENT_CONTACT = "DEPARTMENT_CONTACT"
    FRONT_DESK = "FRONT_DESK"
    GENERIC = "GENERIC"


class BusinessMaturity(str, Enum):
    MICRO_SOLO = "MICRO_SOLO"
    SMALL_BUSINESS = "SMALL_BUSINESS"
    STARTUP = "STARTUP"
    GROWING_SMB = "GROWING_SMB"
    MID_MARKET = "MID_MARKET"
    ENTERPRISE = "ENTERPRISE"
    MULTI_LOCATION = "MULTI_LOCATION"


class HumanOutcomeEvent(BaseModel):
    """Stores human feedback separately from original model prediction for continuous learning datasets."""

    lead_id: str
    original_prediction: str
    original_model_version: str
    original_probability: float
    human_outcome: HumanOutcome
    reason: str | None = None
    timestamp: float


class ContactHierarchyRecord(BaseModel):
    contact_id: str
    lead_id: str
    role: ContactRole = Field(default=ContactRole.GENERIC)
    priority_level: int = Field(default=7)  # 1=Owner, 7=Generic


class BusinessMaturityRecord(BaseModel):
    lead_id: str
    category: BusinessMaturity = Field(default=BusinessMaturity.SMALL_BUSINESS)
    employee_count_estimate: int | None = None


class ServiceOpportunityFoundation(BaseModel):
    website_status_category: str
    seo_opportunity_flag: bool = False
    smma_opportunity_flag: bool = False
    ads_opportunity_flag: bool = False
