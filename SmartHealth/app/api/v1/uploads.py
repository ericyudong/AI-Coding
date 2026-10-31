"""数据接入接口：切片文件上传、批量元数据导入、导入模板。

这是「演示系统」与「能进医院的数据平台」最直观的分界线：
演示系统只能展示别人灌进去的数据；真实系统必须让科室自己把数据放进来，
并且放错的时候要能说清楚"错在第几行、错在哪一列"。

设计要点：
1. **流式落盘**：切片文件动辄数百 MB—数 GB，绝不能整文件读进内存。
   按块写入并同步计算 SHA256（同时用于去重与完整性校验）。
2. **先校验后入库**：扩展名、大小上限、checksum 唯一性都在写库前判定，
   避免半途失败留下"有记录没文件"的脏状态。
3. **上传成功但入库失败要对账**：文件保留在 `data/wsi/`，返回的文件路径写进响应，
   使运维可以人工对账而不是猜。
4. **导入模板可下载**：让科室按模板填表，比事后清洗省一个数量级的人力。
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select

from app.api.v1.common import job_brief, ok, want_async
from app.core.audit import record_audit
from app.core.config import settings
from app.core.deps import CurrentUser, DbSession, audit, require
from app.models.asset import DataAsset, Slide
from app.services import job_service

logger = logging.getLogger("smarthealth.upload")

router = APIRouter(tags=["02 数据资产"])

# 允许的切片格式。刻意限制为病理常用的几种，而不是"什么都能传"：
# 真实项目里最贵的错误不是拒绝合法格式，而是把 CT 影像混进病理库。
ALLOWED_SUFFIXES = {".svs", ".tif", ".tiff", ".ndpi", ".mrxs", ".scn", ".png", ".jpg", ".jpeg", ".npz"}
MAX_UPLOAD_MB = 4096
CHUNK = 1024 * 1024

IMPORT_TEMPLATE_COLUMNS = [
    ("code", "切片编号（必填，全局唯一，如 SITE-A-0001）"),
    ("case_no", "病例号（去标识后，如 C0001）"),
    ("patient_pseudo_id", "患者伪 ID（同一患者多张切片须一致）"),
    ("organ", "器官（如 淋巴结 / 胃 / 肺）"),
    ("cancer_type", "病种（如 淋巴结转移 / 胃早癌）"),
    ("staining", "染色类型（H&E / IHC 等）"),
    ("magnification", "扫描倍率（40X / 20X / 10X）"),
    ("mpp", "物理分辨率 µm/px（数值，如 0.5）"),
    ("has_lesion", "是否阳性（true/false/是/否）"),
    ("site_code", "中心编号（如 SITE-A）"),
    ("split", "数据划分（train / val / test / external）"),
    ("diagnosis_text", "诊断描述"),
    ("icd_o_3", "ICD-O-3 编码"),
    ("scanner", "扫描仪型号"),
    ("file_path", "切片文件本地路径（已上传则填返回的存储路径）"),
]


# ------------------------------------------------------------------ 工具
def _safe_name(name: str) -> str:
    """清洗上传文件名，防止路径穿越与非法字符。"""
    base = Path(name or "unnamed").name
    base = re.sub(r"[^\w.\-]+", "_", base, flags=re.UNICODE)
    return base[:180] or "unnamed"


def _slide_dir(site_code: str) -> Path:
    target = settings.wsi_dir / (site_code or "default")
    target.mkdir(parents=True, exist_ok=True)
    return target


def _stream_to_disk(upload: UploadFile, target: Path) -> tuple[int, str]:
    """分块写盘并计算 SHA256。返回 (字节数, checksum)。"""
    digest = hashlib.sha256()
    size = 0
    limit = MAX_UPLOAD_MB * 1024 * 1024
    with target.open("wb") as out:
        while True:
            chunk = upload.file.read(CHUNK)
            if not chunk:
                break
            size += len(chunk)
            if size > limit:
                out.close()
                target.unlink(missing_ok=True)
                raise HTTPException(status_code=413,
                                    detail=f"文件超过 {MAX_UPLOAD_MB} MB 上限（已接收 {size // 1024 // 1024} MB）")
            digest.update(chunk)
            out.write(chunk)
    return size, digest.hexdigest()


def _parse_bool(value, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "y", "是", "阳性")


def _clean(value) -> str:
    return str(value or "").strip()


# ------------------------------------------------------------------ 上传
@router.post("/uploads/slides", summary="上传切片文件（单个，流式落盘 + SHA256 去重）")
def upload_slide(
    db: DbSession,
    file: UploadFile = File(..., description="切片文件，支持 svs/tif/ndpi/mrxs/scn/png/jpg/npz"),
    code: str = Form("", description="切片编号，留空则用文件名"),
    case_no: str = Form(""),
    patient_pseudo_id: str = Form(""),
    organ: str = Form(""),
    cancer_type: str = Form(""),
    staining: str = Form("H&E"),
    magnification: str = Form("20X"),
    mpp: float = Form(0.5),
    has_lesion: str = Form("false"),
    site_code: str = Form(""),
    split: str = Form("train"),
    diagnosis_text: str = Form(""),
    asset_id: int = Form(0),
    auto_precompute: str = Form("true", description="上传后自动排队特征预计算"),
    user: dict = Depends(require("asset:write")),
) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=422,
            detail=f"不支持的格式 {suffix or '(无扩展名)'}；允许：{', '.join(sorted(ALLOWED_SUFFIXES))}")

    slide_code = _clean(code) or Path(_safe_name(file.filename)).stem
    if db.execute(select(Slide).where(Slide.code == slide_code)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"切片编号 {slide_code} 已存在")

    target_dir = _slide_dir(site_code or (user.get("site_code") or ""))
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    target = target_dir / f"{_safe_name(slide_code)}_{stamp}{suffix}"

    try:
        size, checksum = _stream_to_disk(file, target)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("切片上传落盘失败")
        raise HTTPException(status_code=500, detail=f"文件写入失败：{exc}") from exc

    duplicate = db.execute(
        select(Slide).where(Slide.checksum == checksum, Slide.checksum != "")
    ).scalar_one_or_none()
    if duplicate is not None:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=409,
                            detail=f"文件内容与已有切片 {duplicate.code} 重复（SHA256 一致），已拒绝重复入库")

    asset = db.get(DataAsset, asset_id) if asset_id else None
    slide = Slide(
        code=slide_code,
        asset_id=asset.id if asset else None,
        case_no=_clean(case_no),
        patient_pseudo_id=_clean(patient_pseudo_id),
        organ=_clean(organ),
        cancer_type=_clean(cancer_type),
        staining=_clean(staining) or "H&E",
        diagnosis_text=_clean(diagnosis_text),
        magnification=_clean(magnification) or "20X",
        mpp=float(mpp or 0.5),
        file_path=str(target),
        file_bytes=size,
        checksum=checksum,
        source_filename=_safe_name(file.filename or ""),
        uploaded_by=user.get("username", ""),
        site_code=_clean(site_code) or (user.get("site_code") or ""),
        split=_clean(split) or "train",
        has_lesion=_parse_bool(has_lesion),
        status="uploaded",
        storage_tier="hot",
    )
    db.add(slide)
    db.flush()

    job = None
    if _parse_bool(auto_precompute, True):
        job = job_service.submit_precompute(
            db, slide_ids=[slide.id], encoder_code=settings.default_encoder,
            actor=user.get("username", ""), actor_name=user.get("real_name", ""),
            org_code=user.get("org_code") or "", site_code=slide.site_code or "")

    if asset is not None:
        asset.slide_count = int(db.execute(
            select(func.count(Slide.id)).where(Slide.asset_id == asset.id)).scalar() or 0)
        asset.total_bytes = int(db.execute(
            select(func.coalesce(func.sum(Slide.file_bytes), 0))
            .where(Slide.asset_id == asset.id)).scalar() or 0)

    record_audit(db, action="upload_slide", resource_type="slide", resource_id=slide.id,
                 actor=user.get("username", ""),
                 summary=f"上传切片 {slide.code}（{size / 1024 / 1024:.1f} MB，checksum {checksum[:12]}）",
                 payload={"file_path": str(target), "checksum": checksum, "size": size})
    db.commit()

    return ok({
        "slide": slide.to_dict(),
        "file_path": str(target),
        "file_mb": round(size / 1024 / 1024, 3),
        "checksum": checksum,
        "auto_precompute_job": job_brief(job) if job else None,
    }, message="切片已上传并登记，特征预计算作业已排队")


@router.post("/uploads/slides/batch", summary="批量上传切片文件（多文件）")
async def upload_slides_batch(
    db: DbSession,
    files: list[UploadFile] = File(...),
    default_site_code: str = Form(""),
    default_split: str = Form("train"),
    auto_precompute: str = Form("true"),
    user: dict = Depends(require("asset:write")),
) -> dict:
    """批量上传。逐个处理，单个失败不影响其余 —— 这才是批处理该有的语义。

    注意：这里返回的是"每个文件的处理结果"，而不是一个笼统的成功/失败。
    科室上传 200 个文件时，必须能明确知道哪 3 个失败了、为什么。
    """
    accepted, rejected = [], []
    for item in files:
        try:
            result = upload_slide(
                db=db, file=item,
                code=Path(_safe_name(item.filename)).stem,
                site_code=default_site_code, split=default_split,
                auto_precompute=auto_precompute, user=user,
            )
            accepted.append({"filename": item.filename,
                             "slide_code": result["data"]["slide"]["code"],
                             "file_mb": result["data"]["file_mb"]})
        except HTTPException as exc:
            rejected.append({"filename": item.filename, "error": str(exc.detail)})
        except Exception as exc:  # pragma: no cover
            logger.exception("批量上传单项失败：%s", item.filename)
            rejected.append({"filename": item.filename, "error": f"{type(exc).__name__}: {exc}"})
    return ok({
        "accepted_count": len(accepted), "rejected_count": len(rejected),
        "accepted": accepted, "rejected": rejected,
    }, message=f"批量上传完成：成功 {len(accepted)} / 失败 {len(rejected)}")


# ------------------------------------------------------------------ 元数据导入
@router.get("/uploads/template.csv", summary="下载切片元数据导入模板（CSV，带表头与填写说明）")
def download_template() -> PlainTextResponse:
    buffer = io.StringIO()
    # BOM 让 Excel 正确识别 UTF-8 中文表头 —— 否则科室打开就是乱码，导入必然出错
    buffer.write("\ufeff")
    writer = csv.writer(buffer)
    writer.writerow([col for col, _ in IMPORT_TEMPLATE_COLUMNS])
    writer.writerow(["SITE-A-0001", "C0001", "P0001", "淋巴结", "淋巴结转移", "H&E",
                     "20X", "0.5", "true", "SITE-A", "train", "转移性腺癌", "8140/3",
                     "Scanner-X", ""])
    writer.writerow(["SITE-A-0002", "C0002", "P0002", "淋巴结", "淋巴结转移", "H&E",
                     "20X", "0.5", "false", "SITE-A", "train", "淋巴结反应性增生", "", "", ""])
    return PlainTextResponse(
        buffer.getvalue(), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="smarthealth-slides-template.csv"'})


@router.post("/uploads/slides/csv", summary="按 CSV 批量导入切片元数据（默认异步）")
async def import_slides_csv(
    db: DbSession,
    file: UploadFile = File(..., description="按模板填写的 CSV"),
    asset_id: int = Form(0),
    site_code: str = Form(""),
    split: str = Form("train"),
    enqueue_precompute: str = Form("false"),
    sync: str = Form("", description="传 true 则同步等待导入完成（小批量排障用）"),
    user: dict = Depends(require("asset:write")),
) -> dict:
    """CSV 导入。解析与校验在请求内完成（快），入库走异步作业（可长）。

    这样设计的原因：CSV 解析失败必须**立即**告诉用户（不然他得等作业跑完才知道），
    而真正的入库 + 排队预计算可能涉及数千行，属于长任务。
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="CSV 文件为空")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = raw.decode("gbk")  # 科室用 Excel 另存的常见编码
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=422,
                                detail="无法解析 CSV 编码，请使用 UTF-8 或 GBK") from exc

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=422, detail="CSV 缺少表头，请使用导入模板")
    rows: list[dict] = []
    for line in reader:
        cleaned = {(k or "").strip(): (v if v is not None else "") for k, v in line.items()}
        if not any(_clean(v) for v in cleaned.values()):
            continue  # 跳过空行
        rows.append(cleaned)
    if not rows:
        raise HTTPException(status_code=422, detail="CSV 中没有任何有效数据行")
    if len(rows) > 5000:
        raise HTTPException(status_code=422,
                            detail=f"单次导入上限 5000 行（当前 {len(rows)} 行），请分批")

    job_row = job_service.submit_import_slides(
        db, rows=rows, asset_id=asset_id or None, site_code=site_code, split=split,
        enqueue_precompute=_parse_bool(enqueue_precompute),
        actor=user.get("username", ""), actor_name=user.get("real_name", ""))

    if want_async({"sync": sync}):
        return ok({"async": True, "job": job_brief(job_row), "row_count": len(rows),
                   "columns": list(reader.fieldnames)},
                  message=f"已解析 {len(rows)} 行，导入作业已提交")

    # 同步路径（小批量排障）：等待作业结束并把结果一并返回
    from app.core.tasks import TASKS

    finished = TASKS.wait(job_row.id, timeout=900)
    return ok({"async": False, "job": job_brief(finished), "row_count": len(rows),
               "status": finished.status,
               "result": json.loads(finished.result_json or "{}"),
               "error": finished.error_text})


@router.post("/uploads/validate-csv", summary="仅校验 CSV 不导入（先体检再入库）")
async def validate_csv(file: UploadFile = File(...)) -> dict:
    """预校验：在真正入库前告诉用户"这 40 行有问题，问题是这些"。

    这个接口看起来不起眼，但它把「导入失败→改表→重传」的三轮循环压成一轮。
    """
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("gbk", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = reader.fieldnames or []
    required = {"code"}
    missing_columns = sorted(required - set(fieldnames))
    problems: list[dict] = []
    seen_codes: set[str] = set()
    total = 0
    for index, line in enumerate(reader, start=2):  # 第 1 行是表头
        cleaned = {(k or "").strip(): (v or "") for k, v in line.items()}
        if not any(_clean(v) for v in cleaned.values()):
            continue
        total += 1
        code = _clean(cleaned.get("code"))
        if not code:
            problems.append({"row": index, "field": "code", "error": "切片编号为空"})
            continue
        if code in seen_codes:
            problems.append({"row": index, "field": "code", "error": f"文件内编号重复：{code}"})
        seen_codes.add(code)
        mpp_raw = _clean(cleaned.get("mpp"))
        if mpp_raw:
            try:
                value = float(mpp_raw)
                if not (0.05 <= value <= 10):
                    problems.append({"row": index, "field": "mpp",
                                     "error": f"mpp {value} 超出合理范围 0.05—10"})
            except ValueError:
                problems.append({"row": index, "field": "mpp", "error": f"mpp 非数值：{mpp_raw}"})
        staining = _clean(cleaned.get("staining"))
        if staining and "h&e" not in staining.lower() and "he" != staining.lower()[:2]:
            problems.append({"row": index, "field": "staining",
                             "error": f"染色为 {staining}；当前模型能力边界仅覆盖 H&E"})
    return ok({
        "row_count": total,
        "column_count": len(fieldnames),
        "missing_required_columns": missing_columns,
        "problem_count": len(problems),
        "problems": problems[:200],
        "verdict": ("可以导入" if not missing_columns and not problems
                    else ("缺少必填列，无法导入" if missing_columns
                          else f"存在 {len(problems)} 处问题，建议修正后再导入")),
        "importable": not missing_columns,
    })


# ------------------------------------------------------------------ 删除保护
@router.delete("/slides/{slide_id}", summary="删除切片（含下游引用保护）")
def delete_slide(slide_id: int, db: DbSession, force: bool = Query(False),
                 user: dict = Depends(require("asset:write"))) -> dict:
    """删除切片。

    硬约束：**已有下游引用（特征/预测/标注/Agent 会话）的切片默认拒绝删除**。
    演示系统允许随便删，生产系统里删掉一张参与过训练的切片 =
    模型的血缘关系断链，注册申报时无法回答「这个版本用了哪些数据」。
    force=True 需 asset:write 权限，并会在审计链上留下记录。
    """
    from app.models.agent import AgentSession
    from app.models.label import Annotation
    from app.models.pipeline import SlidePrediction

    slide = db.get(Slide, slide_id)
    if slide is None:
        raise HTTPException(status_code=404, detail="切片不存在")

    blockers = {
        "annotations": int(db.execute(select(func.count(Annotation.id))
                                      .where(Annotation.slide_id == slide.id)).scalar() or 0),
        "predictions": int(db.execute(select(func.count(SlidePrediction.id))
                                      .where(SlidePrediction.slide_id == slide.id)).scalar() or 0),
        "agent_sessions": int(db.execute(select(func.count(AgentSession.id))
                                         .where(AgentSession.slide_id == slide.id)).scalar() or 0),
    }
    referenced = {k: v for k, v in blockers.items() if v > 0}
    if referenced and not force:
        raise HTTPException(
            status_code=409,
            detail={"message": "该切片已被下游引用，删除会破坏模型血缘关系，默认拒绝",
                    "references": referenced,
                    "hint": "如确需删除，请传 force=true；操作将写入审计链",
                    "compliance_note": "注册申报要求可回答「某模型版本用了哪些数据」，"
                                       "删除参与过训练的数据会使该问题无法回答。"})

    file_path = Path(slide.file_path or "")
    db.delete(slide)
    record_audit(db, action="delete_slide", resource_type="slide", resource_id=slide_id,
                 actor=user.get("username", ""),
                 summary=(f"强制删除切片 {slide.code}（存在引用：{referenced}）" if referenced
                          else f"删除切片 {slide.code}"),
                 payload={"references": referenced, "forced": bool(referenced)},
                 risk_level="attention")
    db.commit()
    if file_path.exists() and file_path.is_file():
        try:
            file_path.unlink()
        except OSError:  # pragma: no cover - 文件被占用等情况不应导致接口失败
            logger.warning("切片已删除但文件未能移除：%s", file_path)
    return ok({"deleted": slide_id, "forced": bool(referenced), "references": referenced})
