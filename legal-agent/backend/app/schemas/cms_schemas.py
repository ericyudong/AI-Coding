"""CMS Pydantic schemas."""
import json
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ContractStatsResponse(BaseModel):
    total: int
    active: int
    expiring_soon: int
    expired: int
    pending_sign: int
    archived: int
    high_risk: int


class ContractCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    contract_type: str = "purchase"
    party_a: str = ""
    party_b: str = ""
    amount: float = 0
    currency: str = "CNY"
    sign_date: date | None = None
    effective_date: date | None = None
    expire_date: date | None = None
    status: str = "pending_sign"
    owner: str = ""
    tags: list[str] = []
    content_text: str = ""


class ContractUpdateRequest(BaseModel):
    name: str | None = None
    contract_type: str | None = None
    party_a: str | None = None
    party_b: str | None = None
    amount: float | None = None
    currency: str | None = None
    sign_date: date | None = None
    effective_date: date | None = None
    expire_date: date | None = None
    status: str | None = None
    owner: str | None = None
    tags: list[str] | None = None
    tag_level1: str | None = None
    tag_level2: str | None = None
    content_text: str | None = None
    ai_summary: str | None = None
    summary_locked: bool | None = None


class BatchUpdateRequest(BaseModel):
    ids: list[int]
    status: str | None = None
    owner: str | None = None
    add_tags: list[str] = []


class ContractResponse(BaseModel):
    id: int
    code: str
    name: str
    contract_type: str
    party_a: str
    party_b: str
    amount: float
    currency: str
    sign_date: date | None
    effective_date: date | None
    expire_date: date | None
    status: str
    owner: str
    risk_level: str
    tags: list[str]
    tag_level1: str = ""
    tag_level2: str = ""
    ai_summary: str
    summary_locked: bool = False
    department_id: int | None = None
    parse_status: str = "done"
    content_text: str
    key_clauses: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, obj: Any) -> "ContractResponse":
        tags = json.loads(obj.tags_json or "[]")
        clauses = json.loads(obj.key_clauses_json or "[]")
        return cls(
            id=obj.id,
            code=obj.code,
            name=obj.name,
            contract_type=obj.contract_type,
            party_a=obj.party_a,
            party_b=obj.party_b,
            amount=obj.amount,
            currency=obj.currency,
            sign_date=obj.sign_date,
            effective_date=obj.effective_date,
            expire_date=obj.expire_date,
            status=obj.status,
            owner=obj.owner,
            risk_level=obj.risk_level,
            tags=tags,
            tag_level1=getattr(obj, "tag_level1", "") or "",
            tag_level2=getattr(obj, "tag_level2", "") or "",
            ai_summary=obj.ai_summary or "",
            summary_locked=bool(getattr(obj, "summary_locked", False)),
            department_id=getattr(obj, "department_id", None),
            parse_status=getattr(obj, "parse_status", "done") or "done",
            content_text=obj.content_text or "",
            key_clauses=clauses,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )


class ContractListResponse(BaseModel):
    items: list[ContractResponse]
    total: int
    page: int
    page_size: int


class ImportTaskResponse(BaseModel):
    id: int
    filename: str
    status: str
    progress: int
    confidence: int
    extracted: dict
    parse_warnings: list[str] = []
    char_count: int = 0
    retry_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class ImportTaskListResponse(BaseModel):
    items: list[ImportTaskResponse]
    total: int


class AuditLogItem(BaseModel):
    id: int
    action: str
    before: dict
    after: dict
    note: str = ""
    user_id: int
    created_at: datetime


class AnalyticsTrackRequest(BaseModel):
    event_name: str
    props: dict = {}


class ImportConfirmRequest(BaseModel):
    target_contract_id: int | None = None
    version_label: str = "导入版本"


class ImportConfirmResponse(BaseModel):
    contract: ContractResponse
    import_mode: str  # "new" | "version"
    version: str | None = None


class ImportLinkSuggestionItem(BaseModel):
    contract: ContractResponse
    match_score: int
    match_reason: str


class ImportLinkSuggestionsResponse(BaseModel):
    items: list[ImportLinkSuggestionItem]
    extracted_name: str = ""
    extracted_party_a: str = ""
    extracted_party_b: str = ""


class FieldFilter(BaseModel):
    field: str
    operator: str = "eq"
    value: str


class SearchRequest(BaseModel):
    q: str = ""
    mode: str = "hybrid"
    filters: list[FieldFilter] = []
    limit: int = Field(default=50, ge=1, le=100)


class SearchResultItem(BaseModel):
    contract: ContractResponse
    relevance: float
    highlight: str
    match_type: str | None = None
    ai_suggestion: str | None = None


class SearchResponse(BaseModel):
    items: list[SearchResultItem]
    total: int
    elapsed_ms: int
    ai_suggestion: str | None = None
    mode: str = "hybrid"
    interpreted_query: str = ""
    applied_filters: list[FieldFilter] = []


class SearchSuggestionsResponse(BaseModel):
    suggestions: list[str]
    contracts: list[str]


class TagCloudItem(BaseModel):
    name: str
    count: int


class SummaryResponse(BaseModel):
    summary_type: str
    items: list[str]


class VersionResponse(BaseModel):
    id: int
    version: str
    label: str
    content: str
    is_current: bool
    created_by: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CompareRequest(BaseModel):
    left_version_id: int
    right_version_id: int


class CompareChangeItem(BaseModel):
    change_type: str
    section: str
    left_text: str
    right_text: str
    detail: str | None = None
    ai_note: str | None = None


class CompareResponse(BaseModel):
    summary: dict
    changes: list[CompareChangeItem]
    risk_note: str


class ContractQaRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class CitationDetail(BaseModel):
    section: str
    excerpt: str
    chunk_id: int | None = None


class ContractQaResponse(BaseModel):
    answer: str
    citations: list[str]
    citation_details: list[CitationDetail] = []
    confidence: str
