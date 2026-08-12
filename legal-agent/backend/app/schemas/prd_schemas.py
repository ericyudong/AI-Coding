"""Schemas for auth, roles, performance AI, and system admin."""
from datetime import date, datetime

from pydantic import BaseModel, Field


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    display_name: str
    role: str = "legal"
    department_id: int | None = None
    department_name: str | None = None
    is_active: bool = True
    features: list[str] = []

    model_config = {"from_attributes": True}


class DepartmentOut(BaseModel):
    id: int
    name: str
    code: str = ""

    model_config = {"from_attributes": True}


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    email: str = ""
    display_name: str = ""
    role: str = "legal"
    department_id: int | None = None


class UserUpdateRequest(BaseModel):
    email: str | None = None
    display_name: str | None = None
    role: str | None = None
    department_id: int | None = None
    is_active: bool | None = None
    password: str | None = None


class WorkbenchRecommendResponse(BaseModel):
    questions: list[str]
    role: str
    role_label: str


class SupplierOut(BaseModel):
    id: int
    name: str
    credit_code: str = ""
    contact: str = ""
    industry: str = ""
    risk_level: str = "low"
    contract_count: int = 0
    total_amount: float = 0
    first_coop_date: date | None = None
    last_coop_date: date | None = None
    delay_count: int = 0
    notes: str = ""

    model_config = {"from_attributes": True}


class CustomerOut(BaseModel):
    id: int
    name: str
    credit_code: str = ""
    contact: str = ""
    industry: str = ""
    risk_level: str = "low"
    contract_count: int = 0
    order_count: int = 0
    total_sales: float = 0
    total_qty: float = 0
    first_coop_date: date | None = None
    last_coop_date: date | None = None
    payment_delay_count: int = 0
    notes: str = ""
    related: list[dict] = []

    model_config = {"from_attributes": True}


class CustomerRelationRequest(BaseModel):
    related_customer_id: int
    relation_type: str = "custom"
    equity_ratio: float = 1.0


class PerformanceNodeOut(BaseModel):
    id: int
    title: str
    node_type: str
    due_date: date | None = None
    duration_days: int | None = None
    status: str
    confirm_status: str
    owner_ids: list[int] = []
    primary_owner_id: int | None = None
    notes: str = ""

    model_config = {"from_attributes": True}


class PerformancePlanOut(BaseModel):
    id: int
    contract_id: int
    contract_name: str = ""
    status: str
    nodes: list[PerformanceNodeOut] = []
    confirmed_at: datetime | None = None


class PerformanceNodeUpdate(BaseModel):
    title: str | None = None
    due_date: date | None = None
    duration_days: int | None = None
    owner_ids: list[int] | None = None
    primary_owner_id: int | None = None
    confirm_status: str | None = None
    status: str | None = None
    notes: str | None = None


class PerformanceOverview(BaseModel):
    total_plans: int = 0
    active_plans: int = 0
    pending_confirm: int = 0
    upcoming_alerts: int = 0
    overdue_nodes: int = 0
    my_todos: list[dict] = []


class PerformanceAdjustmentRequest(BaseModel):
    reason: str = Field(min_length=1)
    new_due_date: date | None = None
    new_owner_ids: list[int] = []
    evidence_note: str = ""
    evidence_path: str = ""
    evidence_filename: str = ""


class TagTaxonomyCreate(BaseModel):
    level: int = Field(ge=1, le=3)
    name: str = Field(min_length=1, max_length=128)
    code: str = ""
    parent_id: int | None = None
    sort_order: int = 0


class TagTaxonomyUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    parent_id: int | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class OrderLinkRequest(BaseModel):
    customer_id: int | None = None
    contract_id: int | None = None


class TagUpdateRequest(BaseModel):
    tags: list[str] = []
    tag_level1: str | None = None
    tag_level2: str | None = None


class SummaryUpdateRequest(BaseModel):
    ai_summary: str = Field(min_length=1)
