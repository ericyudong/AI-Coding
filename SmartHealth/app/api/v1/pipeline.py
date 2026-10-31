"""推理流水线接口（对应设计文档第四章 4.3—4.4）。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pathlib import Path
from sqlalchemy import select

from app.api.v1.common import crud_router, list_query, ok, serialize
from app.api.v1.common import job_brief, want_async
from app.core.deps import CurrentUser, DbSession, audit, require
from app.models.asset import Slide
from app.models.modeling import ModelVersion
from app.models.pipeline import AttentionRegion, CaseEmbedding, InferenceJob, SlidePrediction
from app.services.encoder_service import LicenseViolation
from app.services import job_service
from app.services.pipeline_service import (
    DEFAULT_BAG_CONFIG,
    pipeline_overview,
    run_inference,
    similar_cases,
)

router = APIRouter(tags=["05 推理流水线"])

router.include_router(crud_router(
    model=InferenceJob, prefix="/inference/jobs", tag="推理任务", resource_type="inference_job",
    permission_read="inference:read", permission_write=None,
    search_fields=("code", "name", "model_version_label", "encoder_code", "triggered_by"),
    filter_fields=("status", "job_kind", "model_version_id", "encoder_code"),
    json_fields=("slide_ids_json", "params_json", "summary_json"), order_by="id",
))

router.include_router(crud_router(
    model=SlidePrediction, prefix="/inference/predictions", tag="切片预测", resource_type="slide_prediction",
    permission_read="inference:read", permission_write=None,
    search_fields=("slide_code", "model_version_label", "task_code", "reject_reason"),
    filter_fields=("decision", "rejected", "confidence_level", "job_id", "slide_id",
                   "model_version_id", "task_code"),
    json_fields=("attention_summary_json",), order_by="id",
))

router.include_router(crud_router(
    model=AttentionRegion, prefix="/inference/regions", tag="注意力热区", resource_type="attention_region",
    permission_read="inference:read", permission_write=None,
    search_fields=("slide_id",),
    filter_fields=("prediction_id", "slide_id", "level", "is_lesion_overlap"),
    order_by="id",
))

router.include_router(crud_router(
    model=CaseEmbedding, prefix="/inference/case-embeddings", tag="切片级向量索引",
    resource_type="case_embedding",
    permission_read="inference:read", permission_write=None,
    search_fields=("slide_code", "diagnosis_text", "cancer_type", "case_no"),
    filter_fields=("split", "site_code", "status", "encoder_code"),
    order_by="id",
))


@router.get("/inference/overview", summary="流水线总览（Stage A—D 完成度）")
def overview(db: DbSession, user: dict = Depends(require("inference:read"))) -> dict:
    return ok({
        **pipeline_overview(db),
        "bag_config": DEFAULT_BAG_CONFIG.to_dict(),
        "task_definitions": "见 /models/tasks",
    })


@router.get("/inference/predictions/{prediction_id}/detail", summary="预测详情（含注意力热区）")
def prediction_detail(prediction_id: int, db: DbSession,
                      user: dict = Depends(require("inference:read"))) -> dict:
    prediction = db.get(SlidePrediction, prediction_id)
    if prediction is None:
        raise HTTPException(status_code=404, detail="预测记录不存在")
    regions = list(db.execute(
        select(AttentionRegion).where(AttentionRegion.prediction_id == prediction.id)
        .order_by(AttentionRegion.rank.asc())
    ).scalars())
    attention = json.loads(prediction.attention_summary_json or "{}")
    return ok({
        **prediction.to_dict(),
        "attention_summary": attention,
        "regions": [r.to_dict() for r in regions],
        "evidence_note": (
            "注意力权重经 softmax 归一化后可直接映射回切片坐标，"
            "既是注册审评「算法可解释」的空间依据，也是 Agent 导航的候选区域池。"
        ),
        "reject_note": (
            f"该切片触发拒识：{prediction.reject_reason}，已转人工复核。"
            if prediction.rejected else "未触发拒识。"
        ),
    })


@router.get("/inference/predictions/{prediction_id}/heatmap", summary="注意力热力图")
def heatmap(prediction_id: int, db: DbSession,
            user: dict = Depends(require("inference:read"))):
    prediction = db.get(SlidePrediction, prediction_id)
    if prediction is None:
        raise HTTPException(status_code=404, detail="预测记录不存在")
    path = Path(prediction.heatmap_path or "")
    if not path.exists():
        raise HTTPException(status_code=404, detail="该预测未生成热力图")
    return FileResponse(path, media_type="image/png")


@router.get("/inference/regions/{region_id}/crop", summary="证据区域图像（按区域坐标裁剪高倍图）")
def region_crop(region_id: int, db: DbSession, level: int = Query(-1, ge=-1, le=4),
                user: dict = Depends(require("inference:read"))):
    from fastapi import Response

    region = db.get(AttentionRegion, region_id)
    if region is None:
        raise HTTPException(status_code=404, detail="区域不存在")
    slide = db.get(Slide, region.slide_id)
    if slide is None:
        raise HTTPException(status_code=404, detail="切片不存在")

    from app.services.wsi_service import open_slide

    reader = open_slide(slide)
    target_level = region.level if level < 0 else min(level, reader.level_count - 1)
    width, height = reader.dimensions(target_level)
    scale = 2 ** (region.level - target_level)
    size = max(64, region.w * max(scale, 1))
    x = min(max(region.x * max(scale, 1), 0), max(width - size, 0))
    y = min(max(region.y * max(scale, 1), 0), max(height - size, 0))
    png = reader.render_region_png(target_level, x, y, min(size, width), min(size, height))
    return Response(content=png, media_type="image/png")


@router.post("/inference/run", summary="运行推理（批量 / 单例）")
def run(db: DbSession, payload: dict = Body(...),
        user: dict = Depends(require("inference:run"))) -> dict:
    if want_async(payload):
        job = job_service.submit_inference(
            db, payload=payload, actor=user.get("username", ""),
            actor_name=user.get("real_name", ""),
            org_code=user.get("org_code") or "", site_code=user.get("site_code") or "")
        return ok({"async": True, "job": job_brief(job)},
                  message="批量推理作业已提交，可在任务中心查看逐片进度")

    version_id = payload.get("model_version_id")
    if version_id:
        version = db.get(ModelVersion, int(version_id))
    else:
        version = db.execute(
            select(ModelVersion).where(ModelVersion.is_registration_candidate.is_(True))
            .order_by(ModelVersion.id.desc()).limit(1)
        ).scalar_one_or_none() or db.execute(
            select(ModelVersion).order_by(ModelVersion.id.desc()).limit(1)
        ).scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=404, detail="没有可用的模型版本，请先执行训练")

    slide_ids = payload.get("slide_ids") or []
    if slide_ids:
        slides = list(db.execute(select(Slide).where(Slide.id.in_([int(i) for i in slide_ids]))).scalars())
    else:
        stmt = select(Slide).where(Slide.staining == "H&E")
        if payload.get("site_codes"):
            stmt = stmt.where(Slide.site_code.in_(payload["site_codes"]))
        if payload.get("split"):
            stmt = stmt.where(Slide.split == payload["split"])
        limit = int(payload.get("limit") or 200)
        slides = list(db.execute(stmt.order_by(Slide.id.asc()).limit(limit)).scalars())
    if not slides:
        raise HTTPException(status_code=400, detail="没有符合条件的切片")

    try:
        result = run_inference(
            db, slides=slides, model_version=version,
            task_code=str(payload.get("task_code") or "lymph_node_metastasis"),
            threshold=float(payload.get("threshold") or 0.5),
            job_kind=str(payload.get("job_kind") or "batch"),
            deployment_env=user.get("deployment_env"),
            triggered_by=user.get("username", ""),
            name=str(payload.get("name") or ""),
        )
    except LicenseViolation as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"推理失败：{exc}") from exc

    db.commit()
    return ok({"job": result["job"].to_dict(), "summary": result["summary"]})


@router.get("/inference/slides/{slide_id}/similar-cases", summary="相似病例检索")
def similar(slide_id: int, db: DbSession, top_k: int = Query(5, ge=1, le=20),
            user: dict = Depends(require("inference:read"))) -> dict:
    slide = db.get(Slide, slide_id)
    if slide is None:
        raise HTTPException(status_code=404, detail="切片不存在")
    embedding = db.execute(
        select(CaseEmbedding).where(CaseEmbedding.slide_id == slide.id).limit(1)
    ).scalar_one_or_none()
    encoder_code = embedding.encoder_code if embedding else "hibou-b-synth"
    return ok({
        "slide_code": slide.code,
        "encoder_code": encoder_code,
        "cases": similar_cases(db, slide, encoder_code, top_k=top_k),
        "note": "按切片级向量余弦相似检索；同一病例的其他切片已排除，避免数据泄漏式「相似」。",
    })


@router.get("/inference/summary", summary="推理结果汇总（决策分布 / 置信度分布 / 拒识率）")
def summary(db: DbSession, user: dict = Depends(require("inference:read"))) -> dict:
    from sqlalchemy import func

    rows = db.execute(
        select(SlidePrediction.decision, func.count(SlidePrediction.id))
        .group_by(SlidePrediction.decision)
    ).all()
    conf_rows = db.execute(
        select(SlidePrediction.confidence_level, func.count(SlidePrediction.id))
        .group_by(SlidePrediction.confidence_level)
    ).all()
    total = int(db.execute(select(func.count(SlidePrediction.id))).scalar() or 0)
    rejected = sum(int(c) for d, c in rows if d == "rejected")
    region_total = int(db.execute(select(func.count(AttentionRegion.id))).scalar() or 0)
    hits = int(db.execute(
        select(func.count(AttentionRegion.id)).where(AttentionRegion.is_lesion_overlap.is_(True))
    ).scalar() or 0)
    return ok({
        "prediction_total": total,
        "by_decision": {str(d): int(c) for d, c in rows},
        "by_confidence": {str(c): int(n) for c, n in conf_rows},
        "reject_rate": round(rejected / total, 6) if total else 0.0,
        "attention_region_total": region_total,
        "attention_lesion_overlap": hits,
        "attention_hit_rate": round(hits / region_total, 6) if region_total else 0.0,
        "note": (
            "注意力热区与金标准病灶框的重合率可作为「空间可解释性是否指向真实病灶」的量化证据。"
        ),
    })
