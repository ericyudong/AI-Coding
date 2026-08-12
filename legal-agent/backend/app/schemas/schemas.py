"""Pydantic schemas."""
from datetime import datetime

from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


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


class NewsItem(BaseModel):
    id: int
    title: str
    date: str
    category: str = "legal"


class QuickLink(BaseModel):
    id: str
    label: str
    icon: str


class AiModuleCard(BaseModel):
    id: str
    title: str
    subtitle: str
    features: list[str]
    route: str


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    search_type: str = "comprehensive"
    optimize: bool = False


class SearchResponse(BaseModel):
    answer: str
    search_type: str
    references: list[str] = []


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    module: str = "labor_law"
    session_id: int | None = None


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionResponse(BaseModel):
    id: int
    module: str
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatResponse(BaseModel):
    session_id: int
    message: ChatMessageResponse
    reply: ChatMessageResponse


class ContractDraftRequest(BaseModel):
    draft_type: str = "contract"
    purpose: str = Field(min_length=1, max_length=4000)
    position: str = ""
    extra_info: str = ""
    style: str = "简明居中"


class ContractDraftResponse(BaseModel):
    id: int
    draft_type: str = "contract"
    purpose: str = ""
    position: str = ""
    style: str = ""
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ContractReviewResponse(BaseModel):
    id: int
    filename: str
    review_mode: str
    status: str
    result: str
    content_text: str = ""
    content_preview: str = ""
    char_count: int = 0
    parse_status: str = "pending"
    parse_warnings: list[str] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class ContractCompareChangeItem(BaseModel):
    change_type: str
    section: str
    left_text: str
    right_text: str
    detail: str | None = None
    ai_note: str | None = None


class ContractCompareResponse(BaseModel):
    left_filename: str
    right_filename: str
    summary: dict
    changes: list[ContractCompareChangeItem]
    risk_note: str
    elapsed_ms: int
