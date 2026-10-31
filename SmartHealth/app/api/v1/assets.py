"""数据资产与切片接口（对应设计文档第三章 3.1—3.3）。"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, select

from app.api.v1.common import crud_router, list_query, ok, serialize
from app.api.v1.common import job_brief, want_async
from app.core import scoping
from app.core.config import settings
from app.core.deps import CurrentUser, DbSession, audit, require
from app.models.asset import AssetExtension, DataAsset, Slide, SlideFeature, StorageStat
from app.services.pipeline_service import precompute_slide_feature
from app.services import job_service

router = APIRouter(tags=["02 数据资产"])

router.include_router(crud_router(
    model=DataAsset, prefix="/assets", tag="数据资产", resource_type="asset",
    permission_read="asset:read", permission_write="asset:write",
    search_fields=("code", "name", "source_org", "cancer_type", "owner_name"),
    filter_fields=("status", "source_type", "organ_system"),
    json_fields=(),
    order_by="id",
    scope_condition=scoping.asset_condition,
))

router.include_router(crud_router(
    model=Slide, prefix="/slides", tag="切片", resource_type="slide",
    permission_read="asset:read", permission_write="asset:write",
    search_fields=("code", "case_no", "patient_pseudo_id", "cancer_type", "diagnosis_text"),
    filter_fields=("asset_id", "site_code", "split", "staining", "status", "has_lesion", "storage_tier"),
    json_fields=("lesion_bbox_json",),
    order_by="id",
    scope_condition=scoping.slide_condition,
))

router.include_router(crud_router(
    model=AssetExtension, prefix="/asset-extensions", tag="数据扩展路径", resource_type="asset_extension",
    permission_read="asset:read", permission_write="asset:write",
    search_fields=("partner_name", "owner_name", "note"),
    filter_fields=("path_type", "status", "asset_id"),
    order_by="id",
))

router.include_router(crud_router(
    model=StorageStat, prefix="/storage-stats", tag="存储分层统计", resource_type="storage_stat",
    permission_read="asset:read", permission_write=None,
    search_fields=("media",),
    filter_fields=("tier", "stat_date"),
    order_by="stat_date",
))


@router.get("/assets/overview", summary="资产总览（盘点口径）")
def asset_overview(db: DbSession, user: dict = Depends(require("asset:read"))) -> dict:
    assets = list(db.execute(select(DataAsset)).scalars())
    slides = list(db.execute(select(Slide)).scalars())
    by_source = {}
    for asset in assets:
        bucket = by_source.setdefault(asset.source_type, {"count": 0, "slides": 0, "bytes": 0})
        bucket["count"] += 1
        bucket["slides"] += asset.slide_count
        bucket["bytes"] += asset.total_bytes
    by_staining = {}
    for slide in slides:
        by_staining[slide.staining] = by_staining.get(slide.staining, 0) + 1
    by_site = {}
    for slide in slides:
        bucket = by_site.setdefault(slide.site_code or "未标注", {"slides": 0, "positive": 0})
        bucket["slides"] += 1
        bucket["positive"] += 1 if slide.has_lesion else 0
    total_bytes = sum(s.file_bytes for s in slides)
    return ok({
        "asset_count": len(assets),
        "slide_count": len(slides),
        "patient_count": len({s.patient_pseudo_id for s in slides if s.patient_pseudo_id}),
        "annotated_slide_count": sum(a.annotated_slide_count for a in assets),
        "total_bytes": total_bytes,
        "total_tb": round(total_bytes / 1024 ** 4, 4),
        "by_source_type": by_source,
        "by_staining": by_staining,
        "by_site": by_site,
        "positive_slide_count": sum(1 for s in slides if s.has_lesion),
        "p0_action_assets": [a.code for a in assets if a.p0_action],
        "estimated_storage_note": (
            "按方案口径：万张级切片约 16—30 TB；扩展至 5 万张后约 80—150 TB。"
            "演示数据集为合成切片，体积按 JPEG 金字塔压缩比估算，不代表真实院内存量。"
        ),
    })


@router.get("/slides/{slide_id}/reader", summary="切片读取自述（格式/后端/金字塔/实际读取方式）")
def slide_reader(slide_id: int, db: DbSession, prefer: str = Query(""),
                 user: dict = Depends(require("asset:read"))) -> dict:
    """回答「这张切片是什么格式、用哪个后端读、读到几层金字塔」。

    排障时最常见的问题是"读出来的图不对"，而根因往往在后端选择上
    （例如厂商格式被当成普通位图，或 mpp 元数据没解析到）。
    这个接口把判定过程摊开；`prefer` 可强制换一个后端做对照。
    """
    from app.services.wsi_service import open_slide, slide_reader_info

    slide = db.get(Slide, slide_id)
    if slide is None:
        raise HTTPException(status_code=404, detail="切片不存在")
    try:
        scoping.assert_slide_access(db, slide, user)
    except Exception as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    info = slide_reader_info(slide, prefer_backend=prefer)
    if info.get("source") == "file":
        try:
            reader = open_slide(slide, prefer_backend=prefer)
            info["levels"] = [
                {"level": lv.level, "width": lv.width, "height": lv.height,
                 "mpp": round(lv.mpp, 4), "magnification": lv.magnification}
                for lv in reader.levels
            ]
            info["base_mpp_detected"] = round(reader.base_mpp, 4)
            info["reader_class"] = type(reader).__name__
            if hasattr(reader, "cache_stats"):
                info["cache"] = reader.cache_stats()
            if hasattr(reader, "close"):
                reader.close()
        except Exception as exc:
            info["read_error"] = f"{type(exc).__name__}: {exc}"[:300]
    return ok(info)


@router.get("/slides/{slide_id}/thumbnail", summary="切片缩略图")
def slide_thumbnail(slide_id: int, db: DbSession,
                    user: dict = Depends(require("asset:read"))):
    slide = db.get(Slide, slide_id)
    if slide is None:
        raise HTTPException(status_code=404, detail="切片不存在")
    path = Path(slide.thumbnail_path or "")
    if not path.exists():
        raise HTTPException(status_code=404, detail="缩略图尚未生成，请先执行特征预计算")
    return FileResponse(path, media_type="image/png")


@router.get("/slides/{slide_id}/preview", summary="指定层级的切片图像（含热力图叠加）")
def slide_preview(slide_id: int, db: DbSession, level: int = Query(2, ge=0, le=4),
                  overlay: bool = Query(True, description="是否叠加注意力热力图"),
                  user: dict = Depends(require("asset:read"))):
    from app.models.pipeline import SlidePrediction

    slide = db.get(Slide, slide_id)
    if slide is None:
        raise HTTPException(status_code=404, detail="切片不存在")

    if overlay:
        prediction = db.execute(
            select(SlidePrediction).where(SlidePrediction.slide_id == slide.id)
            .order_by(SlidePrediction.id.desc()).limit(1)
        ).scalar_one_or_none()
        if prediction and prediction.heatmap_path and Path(prediction.heatmap_path).exists():
            return FileResponse(prediction.heatmap_path, media_type="image/png")

    from app.services.wsi_service import open_slide

    reader = open_slide(slide)
    level = min(level, reader.level_count - 1)
    width, height = reader.dimensions(level)
    png = reader.render_region_png(level, 0, 0, width, height)
    from fastapi import Response

    return Response(content=png, media_type="image/png")


@router.get("/slides/{slide_id}/detail", summary="切片详情（含标注、预测、注意力热区）")
def slide_detail(slide_id: int, db: DbSession,
                 user: dict = Depends(require("asset:read"))) -> dict:
    from app.models.label import Annotation
    from app.models.pipeline import AttentionRegion, SlidePrediction

    slide = db.get(Slide, slide_id)
    if slide is None:
        raise HTTPException(status_code=404, detail="切片不存在")
    try:
        scoping.assert_slide_access(db, slide, user)
    except scoping.ScopeError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    annotations = list(db.execute(
        select(Annotation).where(Annotation.slide_id == slide.id).order_by(Annotation.layer, Annotation.id)
    ).scalars())
    prediction = db.execute(
        select(SlidePrediction).where(SlidePrediction.slide_id == slide.id)
        .order_by(SlidePrediction.id.desc()).limit(1)
    ).scalar_one_or_none()
    regions = []
    if prediction:
        regions = list(db.execute(
            select(AttentionRegion).where(AttentionRegion.prediction_id == prediction.id)
            .order_by(AttentionRegion.rank.asc())
        ).scalars())

    return ok({
        **slide.to_dict(),
        "lesion_bbox": json.loads(slide.lesion_bbox_json or "[]"),
        "annotations": [
            {**a.to_dict(), "region": json.loads(a.region_json or "[]")} for a in annotations
        ],
        "annotation_by_layer": _group_by_layer(annotations),
        "prediction": serialize(prediction, ("attention_summary_json",)) if prediction else None,
        "attention_regions": [r.to_dict() for r in regions],
    })


def _group_by_layer(annotations) -> dict:
    result: dict[str, list] = {}
    for ann in annotations:
        result.setdefault(ann.layer, []).append({
            "schema_code": ann.schema_code,
            "value": ann.value_text or ann.value_num,
            "annotator": ann.annotator_name,
            "status": ann.status,
            "confidence": ann.confidence,
        })
    return result


@router.post("/slides/{slide_id}/precompute", summary="Stage A：对单张切片执行特征预计算")
def precompute(slide_id: int, db: DbSession,
               payload: dict = Body(default={}),
               user: dict = Depends(require("pipeline:run"))) -> dict:
    slide = db.get(Slide, slide_id)
    if slide is None:
        raise HTTPException(status_code=404, detail="切片不存在")
    encoder_code = str(payload.get("encoder_code") or settings.default_encoder)
    force = bool(payload.get("force", False))

    if want_async(payload):
        job = job_service.submit_precompute(
            db, slide_ids=[slide_id], encoder_code=encoder_code, force=force,
            actor=user.get("username", ""), actor_name=user.get("real_name", ""),
            org_code=user.get("org_code") or "", site_code=slide.site_code or "")
        return ok({"async": True, "job": job_brief(job)}, message="特征预计算作业已提交")

    try:
        feature = precompute_slide_feature(
            db, slide, encoder_code,
            deployment_env=user.get("deployment_env"),
            force=force,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"特征预计算失败：{exc}") from exc
    audit(db, user, action="precompute_feature", resource_type="slide", resource_id=slide.id,
          summary=f"切片 {slide.code} 特征预计算完成（{feature.tile_count} 个图块，编码器 {encoder_code}）",
          payload={"tile_count": feature.tile_count, "checksum": feature.checksum})
    db.commit()
    return ok(serialize(feature, ()))


@router.get("/features", summary="特征库列表")
def feature_list(db: DbSession, user: dict = Depends(require("asset:read")),
                 page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
                 encoder_code: str = Query(""), slide_code: str = Query("")) -> dict:
    filters = {}
    columns = {c.key: c for c in SlideFeature.__table__.columns}
    if encoder_code:
        filters[columns["encoder_code"]] = encoder_code
    if slide_code:
        filters[columns["slide_code"]] = slide_code
    items, total = list_query(
        db, SlideFeature, page=page, page_size=page_size, search="", search_fields=[],
        filters=filters, order_by=columns["id"], descending=True,
    )
    return ok({
        "items": [f.to_dict() for f in items],
        "meta": {"total": total, "page": page, "page_size": page_size,
                 "pages": (total + page_size - 1) // page_size},
    })


@router.get("/features/overview", summary="特征库总览（Stage A 完成度）")
def feature_overview(db: DbSession, user: dict = Depends(require("asset:read"))) -> dict:
    rows = db.execute(
        select(SlideFeature.encoder_code, func.count(SlideFeature.id),
               func.avg(SlideFeature.tile_count), func.avg(SlideFeature.elapsed_ms))
        .group_by(SlideFeature.encoder_code)
    ).all()
    total_slides = int(db.execute(select(func.count(Slide.id))).scalar() or 0)
    total_features = int(db.execute(select(func.count(SlideFeature.id))).scalar() or 0)
    return ok({
        "slide_total": total_slides,
        "feature_rows": total_features,
        "by_encoder": [
            {
                "encoder_code": row[0],
                "slide_count": int(row[1] or 0),
                "avg_tile_count": round(float(row[2] or 0), 2),
                "avg_elapsed_ms": round(float(row[3] or 0), 1),
            }
            for row in rows
        ],
        "note": (
            "特征预计算（Stage A）一次性把切片转成可复用特征库，"
            "后续训练、推理、评测与 Agent 全部复用同一份特征，边际算力成本极低。"
        ),
    })
