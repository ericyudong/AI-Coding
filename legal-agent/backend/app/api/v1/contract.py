"""Contract review and drafting API."""

import json

import uuid

from pathlib import Path



import aiofiles

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession



from app.api.deps import get_current_user

from app.core.config import data_root, get_settings

from app.core.database import get_db

from app.models.models import ContractDraft, ContractReview, User

from app.schemas.schemas import (
    ContractCompareChangeItem,
    ContractCompareResponse,
    ContractDraftRequest,
    ContractDraftResponse,
    ContractReviewResponse,
)

from app.services.document_parser import parse_file

from app.services.llm_service import draft_contract, review_contract

from app.services.compare_service import compare_texts



router = APIRouter(prefix="/contract", tags=["contract"])



ALLOWED_EXT = {".doc", ".docx", ".pdf"}





def _review_to_response(record: ContractReview) -> ContractReviewResponse:

    warnings = json.loads(record.parse_warnings_json or "[]")

    text = record.content_text or ""

    return ContractReviewResponse(

        id=record.id,

        filename=record.filename,

        review_mode=record.review_mode,

        status=record.status,

        result=record.result,

        content_text=text,

        content_preview=text[:500] if text else "",

        char_count=len(text),

        parse_status=record.parse_status,

        parse_warnings=warnings,

        created_at=record.created_at,

    )





@router.post("/upload", response_model=ContractReviewResponse)

async def upload_contract(

    file: UploadFile = File(...),

    review_mode: str = Form("checklist"),

    user: User = Depends(get_current_user),

    db: AsyncSession = Depends(get_db),

):

    settings = get_settings()

    if not file.filename:

        raise HTTPException(status_code=400, detail="文件名无效")

    ext = Path(file.filename).suffix.lower()

    if ext not in ALLOWED_EXT:

        raise HTTPException(status_code=400, detail="仅支持 doc、docx、pdf 格式")



    content = await file.read()

    if len(content) > settings.contract_max_upload_bytes:

        raise HTTPException(status_code=400, detail="文件大小超过 100MB 限制")



    upload_dir = data_root() / "contracts" / str(user.id)

    upload_dir.mkdir(parents=True, exist_ok=True)

    safe_name = f"{uuid.uuid4().hex}{ext}"

    file_path = upload_dir / safe_name

    async with aiofiles.open(file_path, "wb") as f:

        await f.write(content)



    parsed = parse_file(file_path)

    parse_status = "ok" if parsed.char_count > 0 else "failed"



    record = ContractReview(

        user_id=user.id,

        filename=file.filename,

        file_path=str(file_path),

        review_mode=review_mode,

        status="uploaded",

        content_text=parsed.text,

        parse_status=parse_status,

        parse_warnings_json=json.dumps(parsed.warnings, ensure_ascii=False),

    )

    db.add(record)

    await db.commit()

    await db.refresh(record)

    return _review_to_response(record)





@router.post("/review/{review_id}", response_model=ContractReviewResponse)

async def run_review(

    review_id: int,

    user: User = Depends(get_current_user),

    db: AsyncSession = Depends(get_db),

):

    result = await db.execute(

        select(ContractReview).where(ContractReview.id == review_id, ContractReview.user_id == user.id)

    )

    record = result.scalar_one_or_none()

    if not record:

        raise HTTPException(status_code=404, detail="审核记录不存在")



    content_text = record.content_text or ""

    if not content_text and record.file_path:

        parsed = parse_file(record.file_path)

        content_text = parsed.text

        record.content_text = parsed.text

        record.parse_status = "ok" if parsed.char_count > 0 else "failed"

        record.parse_warnings_json = json.dumps(parsed.warnings, ensure_ascii=False)



    record.status = "processing"

    await db.commit()



    result_text = await review_contract(

        record.filename,

        content_text=content_text,

        review_mode=record.review_mode,

    )

    record.result = result_text

    record.status = "completed"

    await db.commit()

    await db.refresh(record)

    return _review_to_response(record)





@router.get("/reviews", response_model=list[ContractReviewResponse])

async def list_reviews(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):

    result = await db.execute(

        select(ContractReview).where(ContractReview.user_id == user.id).order_by(ContractReview.created_at.desc()).limit(20)

    )

    return [_review_to_response(r) for r in result.scalars().all()]





@router.post("/draft", response_model=ContractDraftResponse)

async def create_draft(

    body: ContractDraftRequest,

    user: User = Depends(get_current_user),

    db: AsyncSession = Depends(get_db),

):

    content = await draft_contract(

        body.purpose, body.position, body.extra_info, body.style, body.draft_type

    )

    record = ContractDraft(

        user_id=user.id,

        draft_type=body.draft_type,

        purpose=body.purpose,

        position=body.position,

        extra_info=body.extra_info,

        style=body.style,

        content=content,

    )

    db.add(record)

    await db.commit()

    await db.refresh(record)

    return record





@router.get("/drafts", response_model=list[ContractDraftResponse])

async def list_drafts(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):

    result = await db.execute(

        select(ContractDraft).where(ContractDraft.user_id == user.id).order_by(ContractDraft.created_at.desc()).limit(20)

    )

    return result.scalars().all()


async def _save_and_parse_upload(file: UploadFile, user_id: int) -> tuple[str, str, object]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名无效")
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail="仅支持 doc、docx、pdf 格式")
    settings = get_settings()
    content = await file.read()
    if len(content) > settings.contract_max_upload_bytes:
        raise HTTPException(status_code=400, detail="文件大小超过 100MB 限制")
    upload_dir = data_root() / "contracts" / str(user_id) / "compare"
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}{ext}"
    file_path = upload_dir / safe_name
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)
    parsed = parse_file(file_path)
    if not parsed.text.strip():
        raise HTTPException(
            status_code=400,
            detail=f"「{file.filename}」未能提取正文；扫描件 PDF 请确认已启用 PARSER_OCR_ENABLED=true 并安装 OCR 依赖",
        )
    return file.filename, parsed.text, parsed


@router.post("/compare", response_model=ContractCompareResponse)
async def compare_contract_files(
    left_file: UploadFile = File(...),
    right_file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    import time

    start = time.perf_counter()
    try:
        left_name, left_text, _ = await _save_and_parse_upload(left_file, user.id)
        right_name, right_text, _ = await _save_and_parse_upload(right_file, user.id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件解析失败: {e}") from e

    data = await compare_texts(left_text, right_text, left_label=left_name, right_label=right_name)
    elapsed = int((time.perf_counter() - start) * 1000) or 1
    return ContractCompareResponse(
        left_filename=left_name,
        right_filename=right_name,
        summary=data["summary"],
        changes=[ContractCompareChangeItem(**c) for c in data["changes"]],
        risk_note=data["risk_note"],
        elapsed_ms=elapsed,
    )
