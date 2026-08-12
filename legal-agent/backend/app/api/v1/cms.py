"""Contract Management System API."""
import csv
import io
import json
import uuid
from datetime import datetime
from pathlib import Path

import aiofiles
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.access import can_view_contract
from app.core.config import data_root, get_settings
from app.core.database import get_db
from app.core.roles import (
    FEATURE_CONTRACT_IMPORT,
    FEATURE_CONTRACT_SUMMARY_EDIT,
    FEATURE_CONTRACT_TAG_EDIT,
)
from app.models.cms_models import ContractImportTask, ContractVersion, ManagedContract
from app.models.models import User
from app.schemas.cms_schemas import (
    AnalyticsTrackRequest,
    AuditLogItem,
    BatchUpdateRequest,
    CompareChangeItem,
    CompareRequest,
    CompareResponse,
    ContractCreateRequest,
    ContractListResponse,
    ContractQaRequest,
    ContractQaResponse,
    ContractResponse,
    ContractStatsResponse,
    ContractUpdateRequest,
    ImportConfirmRequest,
    ImportConfirmResponse,
    ImportLinkSuggestionItem,
    ImportLinkSuggestionsResponse,
    ImportTaskListResponse,
    ImportTaskResponse,
    FieldFilter,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    SearchSuggestionsResponse,
    SummaryResponse,
    TagCloudItem,
    VersionResponse,
)
from app.schemas.prd_schemas import SummaryUpdateRequest, TagUpdateRequest
from app.services import audit_service, cms_service, search_service
from app.services.admin_service import require_feature
from app.services.import_queue import run_import_job

router = APIRouter(prefix="/cms", tags=["cms"])


def _task_response(task: ContractImportTask) -> ImportTaskResponse:
    return ImportTaskResponse(
        id=task.id,
        filename=task.filename,
        status=task.status,
        progress=task.progress,
        confidence=task.confidence,
        extracted=json.loads(task.extracted_json or "{}"),
        parse_warnings=json.loads(task.parse_warnings_json or "[]"),
        char_count=len(task.content_text or ""),
        retry_count=getattr(task, "retry_count", 0) or 0,
        created_at=task.created_at,
    )


ALLOWED_IMPORT_EXT = {".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png", ".xlsx"}


@router.get("/stats", response_model=ContractStatsResponse)
async def stats(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await cms_service.get_stats(db, user.id, user=user)


@router.get("/contracts", response_model=ContractListResponse)
async def list_contracts(
    q: str = "",
    status: str | None = None,
    contract_type: str | None = None,
    risk_level: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items, total = await cms_service.list_contracts(
        db,
        user.id,
        q=q,
        status=status,
        contract_type=contract_type,
        risk_level=risk_level,
        page=page,
        page_size=page_size,
        user=user,
    )
    return ContractListResponse(
        items=[ContractResponse.from_orm_model(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/contracts", response_model=ContractResponse)
async def create_contract(
    body: ContractCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    payload = body.model_dump()
    payload["department_id"] = user.department_id
    contract = await cms_service.create_contract(db, user.id, payload)
    await audit_service.track_event(db, event_name="contract_create", user_id=user.id, props={"id": contract.id})
    return ContractResponse.from_orm_model(contract)


@router.get("/contracts/{contract_id}", response_model=ContractResponse)
async def get_contract(
    contract_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    contract = await _get_user_contract(db, user, contract_id)
    return ContractResponse.from_orm_model(contract)


@router.put("/contracts/{contract_id}", response_model=ContractResponse)
async def update_contract(
    contract_id: int,
    body: ContractUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    import json

    contract = await _get_user_contract(db, user, contract_id)
    data = body.model_dump(exclude_unset=True)
    before_status = contract.status
    tags = data.pop("tags", None)
    for k, v in data.items():
        setattr(contract, k, v)
    if tags is not None:
        contract.tags_json = json.dumps(tags, ensure_ascii=False)
    if "content_text" in data:
        contract.index_status = "pending"
    await db.commit()
    await db.refresh(contract)
    if "status" in data and data["status"] != before_status:
        await audit_service.write_audit(
            db,
            contract_id=contract.id,
            user_id=user.id,
            action="status_update",
            before={"status": before_status},
            after={"status": contract.status},
        )
        await audit_service.track_event(
            db, event_name="status_change", user_id=user.id, props={"contract_id": contract.id, "status": contract.status}
        )
    if "content_text" in data:
        from app.services import index_service

        await index_service.index_contract(db, contract)
    return ContractResponse.from_orm_model(contract)


@router.delete("/contracts/{contract_id}")
async def delete_contract(
    contract_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    contract = await _get_user_contract(db, user, contract_id)
    from app.services import vector_store

    vector_store.delete_by_contract(contract_id)
    await db.delete(contract)
    await db.commit()
    return {"ok": True}


@router.post("/contracts/batch")
async def batch_update(
    body: BatchUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    import json
    from app.core.access import contract_scope_filter

    query = contract_scope_filter(
        select(ManagedContract).where(ManagedContract.id.in_(body.ids)),
        user,
    )
    result = await db.execute(query)
    contracts = result.scalars().all()
    for c in contracts:
        if body.status:
            c.status = body.status
        if body.owner:
            c.owner = body.owner
        if body.add_tags:
            tags = json.loads(c.tags_json or "[]")
            tags.extend(t for t in body.add_tags if t not in tags)
            c.tags_json = json.dumps(tags, ensure_ascii=False)
    await db.commit()
    return {"updated": len(contracts)}


@router.get("/contracts/export/csv")
async def export_csv(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    items, _ = await cms_service.list_contracts(db, user.id, page=1, page_size=1000, user=user)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["编号", "名称", "类型", "金额", "乙方", "状态", "到期日", "负责人"])
    for c in items:
        writer.writerow([
            c.code,
            c.name,
            cms_service.TYPE_LABELS.get(c.contract_type, c.contract_type),
            c.amount,
            c.party_b,
            cms_service.STATUS_LABELS.get(c.status, c.status),
            c.expire_date or "",
            c.owner or "",
        ])
    # UTF-8 BOM：Excel 在 Windows 上才能正确识别中文
    csv_bytes = output.getvalue().encode("utf-8-sig")
    filename = f"contracts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import/upload", response_model=ImportTaskResponse)
async def import_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        require_feature(user, FEATURE_CONTRACT_IMPORT)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    settings = get_settings()
    filename = file.filename or "unknown"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_IMPORT_EXT:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {ext}")

    content = await file.read()
    if len(content) > settings.contract_max_upload_bytes:
        mb = settings.contract_max_upload_bytes // (1024 * 1024)
        raise HTTPException(status_code=400, detail=f"文件超过 {mb}MB 限制")

    upload_dir = data_root() / "cms_imports" / str(user.id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    path = upload_dir / f"{uuid.uuid4().hex}{ext}"
    async with aiofiles.open(path, "wb") as f:
        await f.write(content)

    task = await cms_service.enqueue_import(db, user.id, filename, str(path))
    await audit_service.track_event(
        db,
        event_name="contract_upload",
        user_id=user.id,
        props={"task_id": task.id, "filename": filename, "size": len(content)},
    )
    background_tasks.add_task(run_import_job, task.id)
    return _task_response(task)


@router.post("/import/upload-batch", response_model=ImportTaskListResponse)
async def import_upload_batch(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        require_feature(user, FEATURE_CONTRACT_IMPORT)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    settings = get_settings()
    if len(files) > settings.contract_max_batch_files:
        raise HTTPException(status_code=400, detail=f"单次最多上传 {settings.contract_max_batch_files} 个文件")

    items: list[ImportTaskResponse] = []
    for file in files:
        filename = file.filename or "unknown"
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_IMPORT_EXT:
            continue
        content = await file.read()
        if len(content) > settings.contract_max_upload_bytes:
            continue
        upload_dir = data_root() / "cms_imports" / str(user.id)
        upload_dir.mkdir(parents=True, exist_ok=True)
        path = upload_dir / f"{uuid.uuid4().hex}{ext}"
        async with aiofiles.open(path, "wb") as f:
            await f.write(content)
        task = await cms_service.enqueue_import(db, user.id, filename, str(path))
        background_tasks.add_task(run_import_job, task.id)
        items.append(_task_response(task))
    return ImportTaskListResponse(items=items, total=len(items))


@router.get("/import/tasks", response_model=ImportTaskListResponse)
async def list_import_tasks(
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tasks = await cms_service.list_import_tasks(db, user.id, limit=limit)
    return ImportTaskListResponse(items=[_task_response(t) for t in tasks], total=len(tasks))


@router.get("/import/{task_id}", response_model=ImportTaskResponse)
async def get_import_task(
    task_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await db.get(ContractImportTask, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _task_response(task)


@router.post("/import/{task_id}/retry", response_model=ImportTaskResponse)
async def retry_import_task(
    task_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await db.get(ContractImportTask, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status not in ("failed", "completed"):
        raise HTTPException(status_code=400, detail="当前状态不可重新解析")
    task.status = "queued"
    task.progress = 0
    await db.commit()
    background_tasks.add_task(run_import_job, task.id, True)
    await db.refresh(task)
    return _task_response(task)


@router.get("/import/{task_id}/link-suggestions", response_model=ImportLinkSuggestionsResponse)
async def import_link_suggestions(
    task_id: int,
    q: str = "",
    limit: int = Query(default=10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        items, meta = await cms_service.suggest_import_link_from_task(
            db, user.id, task_id, q=q, limit=limit
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return ImportLinkSuggestionsResponse(
        items=[
            ImportLinkSuggestionItem(
                contract=ContractResponse.from_orm_model(item["contract"]),
                match_score=item["match_score"],
                match_reason=item["match_reason"],
            )
            for item in items
        ],
        extracted_name=meta["extracted_name"],
        extracted_party_a=meta["extracted_party_a"],
        extracted_party_b=meta["extracted_party_b"],
    )


@router.post("/import/{task_id}/confirm", response_model=ImportConfirmResponse)
async def confirm_import(
    task_id: int,
    body: ImportConfirmRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        contract, import_mode, version = await cms_service.confirm_import(
            db,
            user.id,
            task_id,
            target_contract_id=body.target_contract_id,
            version_label=body.version_label,
            department_id=user.department_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return ImportConfirmResponse(
        contract=ContractResponse.from_orm_model(contract),
        import_mode=import_mode,
        version=version,
    )


def _build_search_response(data: dict) -> SearchResponse:
    return SearchResponse(
        items=[
            SearchResultItem(
                contract=ContractResponse.from_orm_model(item["contract"]),
                relevance=item["relevance"],
                highlight=item["highlight"],
                match_type=item.get("match_type"),
            )
            for item in data["items"]
        ],
        total=data["total"],
        elapsed_ms=data["elapsed_ms"],
        ai_suggestion=data.get("ai_suggestion"),
        mode=data.get("mode", "hybrid"),
        interpreted_query=data.get("interpreted_query", ""),
        applied_filters=[FieldFilter(**f) for f in data.get("applied_filters", [])],
    )


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(min_length=1),
    mode: str = "hybrid",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        data = await cms_service.search_contracts(db, user.id, q, mode=mode, user=user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _build_search_response(data)


@router.post("/search", response_model=SearchResponse)
async def search_advanced(
    body: SearchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not body.q.strip() and not body.filters:
        raise HTTPException(status_code=400, detail="请输入搜索词或添加筛选条件")
    try:
        data = await cms_service.search_contracts(
            db,
            user.id,
            body.q,
            mode=body.mode,
            filters=[f.model_dump() for f in body.filters],
            limit=body.limit,
            user=user,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _build_search_response(data)


@router.get("/search/suggestions", response_model=SearchSuggestionsResponse)
async def search_suggestions(
    q: str = "",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await search_service.search_suggestions(db, user.id, q=q, user=user)
    return SearchSuggestionsResponse(**data)


@router.get("/tags/cloud", response_model=list[TagCloudItem])
async def tags_cloud(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    items = await cms_service.tag_cloud(db, user.id, user=user)
    return [TagCloudItem(**i) for i in items]


@router.get("/tags/taxonomy")
async def tags_taxonomy(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.services import tag_service

    rows = await tag_service.list_tags(db, active_only=True)
    return tag_service.tags_to_tree(rows)


@router.get("/contracts/{contract_id}/summary", response_model=SummaryResponse)
async def contract_summary(
    contract_id: int,
    summary_type: str = "short",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    contract = await _get_user_contract(db, user, contract_id)
    items = await cms_service.build_summary_async(contract, summary_type)
    return SummaryResponse(summary_type=summary_type, items=items)


@router.post("/contracts/{contract_id}/qa", response_model=ContractQaResponse)
async def contract_qa(
    contract_id: int,
    body: ContractQaRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    contract = await _get_user_contract(db, user, contract_id)
    result = await cms_service.answer_contract_qa(db, contract, body.question)
    return ContractQaResponse(**result)


@router.get("/contracts/{contract_id}/versions", response_model=list[VersionResponse])
async def list_versions(
    contract_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_contract(db, user, contract_id)
    result = await db.execute(
        select(ContractVersion).where(ContractVersion.contract_id == contract_id).order_by(ContractVersion.id)
    )
    return result.scalars().all()


@router.post("/contracts/{contract_id}/compare", response_model=CompareResponse)
async def compare_versions(
    contract_id: int,
    body: CompareRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_contract(db, user, contract_id)
    try:
        data = await cms_service.compare_versions(
            db,
            contract_id,
            body.left_version_id,
            body.right_version_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return CompareResponse(
        summary=data["summary"],
        changes=[CompareChangeItem(**c) for c in data["changes"]],
        risk_note=data["risk_note"],
    )


@router.put("/contracts/{contract_id}/tags", response_model=ContractResponse)
async def update_tags(
    contract_id: int,
    body: TagUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        require_feature(user, FEATURE_CONTRACT_TAG_EDIT)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    contract = await _get_user_contract(db, user, contract_id)
    from app.services import tag_service

    try:
        await tag_service.validate_levels(db, body.tag_level1, body.tag_level2)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    before = {
        "tags": json.loads(contract.tags_json or "[]"),
        "tag_level1": contract.tag_level1,
        "tag_level2": contract.tag_level2,
    }
    contract.tags_json = json.dumps(body.tags, ensure_ascii=False)
    if body.tag_level1 is not None:
        contract.tag_level1 = body.tag_level1
    if body.tag_level2 is not None:
        contract.tag_level2 = body.tag_level2
    await db.commit()
    await db.refresh(contract)
    after = {
        "tags": body.tags,
        "tag_level1": contract.tag_level1,
        "tag_level2": contract.tag_level2,
    }
    await audit_service.write_audit(
        db, contract_id=contract.id, user_id=user.id, action="tag_update", before=before, after=after
    )
    await audit_service.track_event(db, event_name="tag_generate", user_id=user.id, props={"contract_id": contract.id})
    return ContractResponse.from_orm_model(contract)


@router.put("/contracts/{contract_id}/summary", response_model=ContractResponse)
async def update_summary(
    contract_id: int,
    body: SummaryUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        require_feature(user, FEATURE_CONTRACT_SUMMARY_EDIT)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    contract = await _get_user_contract(db, user, contract_id)
    before = {"ai_summary": contract.ai_summary, "summary_locked": contract.summary_locked}
    contract.ai_summary = body.ai_summary
    contract.summary_locked = True
    await db.commit()
    await db.refresh(contract)
    await audit_service.write_audit(
        db,
        contract_id=contract.id,
        user_id=user.id,
        action="summary_update",
        before=before,
        after={"ai_summary": contract.ai_summary, "summary_locked": True},
    )
    await audit_service.track_event(db, event_name="summary_edit", user_id=user.id, props={"contract_id": contract.id})
    return ContractResponse.from_orm_model(contract)


@router.get("/contracts/{contract_id}/audits", response_model=list[AuditLogItem])
async def list_contract_audits(
    contract_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_contract(db, user, contract_id)
    rows = await audit_service.list_audits(db, contract_id)
    return [
        AuditLogItem(
            id=r.id,
            action=r.action,
            before=json.loads(r.before_json or "{}"),
            after=json.loads(r.after_json or "{}"),
            note=r.note or "",
            user_id=r.user_id,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post("/analytics/track")
async def track_analytics(
    body: AnalyticsTrackRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await audit_service.track_event(db, event_name=body.event_name, user_id=user.id, props=body.props)
    return {"ok": True}


async def _get_user_contract(db: AsyncSession, user: User, contract_id: int) -> ManagedContract:
    contract = await db.get(ManagedContract, contract_id)
    if not contract or not can_view_contract(user, contract):
        raise HTTPException(status_code=404, detail="合同不存在")
    return contract
