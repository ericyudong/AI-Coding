"""四层标签体系与标注质量接口（对应设计文档第三章）。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import func, select

from app.api.v1.common import crud_router, list_query, ok
from app.core.deps import CurrentUser, DbSession, audit, require
from app.models.label import (
    LABEL_LAYER_LABELS,
    LABEL_LAYERS,
    Annotation,
    AnnotatorProfile,
    Arbitration,
    LabelSchema,
    LabelSop,
    QcRecord,
)
from app.services import label_service

router = APIRouter(tags=["03 标签体系"])

router.include_router(crud_router(
    model=LabelSchema, prefix="/labels/schemas", tag="标签定义", resource_type="label_schema",
    permission_read="label:read", permission_write="label:write",
    search_fields=("code", "name", "description", "snomed_code", "icd_o_3_code"),
    filter_fields=("layer", "value_type", "required_for_training", "required_for_registration"),
    json_fields=("allowed_values_json",), order_by="sort_order", editable_fields=None,
    summary_template="更新标签定义 {row.code} {row.name}",
))

router.include_router(crud_router(
    model=AnnotatorProfile, prefix="/labels/annotators", tag="标注人员", resource_type="annotator",
    permission_read="label:read", permission_write="label:write",
    search_fields=("name", "title", "subspecialty", "hospital", "certificate_no"),
    filter_fields=("status", "qualification_verified", "hospital"),
    json_fields=("training_records_json",), order_by="id",
))

router.include_router(crud_router(
    model=LabelSop, prefix="/labels/sops", tag="标注 SOP", resource_type="label_sop",
    permission_read="label:read", permission_write="label:write",
    search_fields=("code", "name", "scope", "owner_name"),
    filter_fields=("medical_review_status", "status", "version"),
    order_by="id", summary_template="更新标注 SOP {row.code} {row.version}",
))

router.include_router(crud_router(
    model=Annotation, prefix="/labels/annotations", tag="标注记录", resource_type="annotation",
    permission_read="label:read", permission_write="label:write",
    search_fields=("slide_code", "schema_code", "annotator_name", "value_text"),
    filter_fields=("layer", "schema_code", "slide_code", "status", "annotator_name"),
    json_fields=("region_json",), order_by="id",
))

router.include_router(crud_router(
    model=QcRecord, prefix="/labels/qc", tag="质控记录", resource_type="qc_record",
    permission_read="label:read", permission_write="label:write",
    search_fields=("slide_code", "reviewer_name", "note"),
    filter_fields=("qc_type", "result", "rework_required"),
    json_fields=("defect_types_json",), order_by="id",
))

router.include_router(crud_router(
    model=Arbitration, prefix="/labels/arbitrations", tag="仲裁记录", resource_type="arbitration",
    permission_read="label:read", permission_write="label:write",
    search_fields=("slide_code", "schema_code", "conflict_summary", "arbitrator_name"),
    filter_fields=("status", "schema_code"),
    json_fields=("opinions_json",), order_by="id",
    summary_template="更新仲裁记录 {row.code or row.id}",
))


@router.get("/labels/coverage", summary="四层标签覆盖率与注册必备标签缺口")
def coverage(db: DbSession, user: dict = Depends(require("label:read"))) -> dict:
    return ok(label_service.coverage_report(db))


@router.get("/labels/layers", summary="四层标签体系 + 质控层定义")
def layers(db: DbSession, user: dict = Depends(require("label:read"))) -> dict:
    rows = db.execute(
        select(LabelSchema.layer, func.count(LabelSchema.id)).group_by(LabelSchema.layer)
    ).all()
    counts = {row[0]: int(row[1]) for row in rows}
    return ok([
        {
            "key": layer,
            "label": LABEL_LAYER_LABELS[layer],
            "schema_count": counts.get(layer, 0),
            "description": {
                "case": "以「一例患者/一个病例」为单位的结构化结论，是注册申报的金标准来源。",
                "slide": "以「一张切片」为单位的属性（部位、染色、制片质量、肿瘤占比等）。",
                "region": "以「区域框」标注病灶范围，是图块级模型的核心监督信号。",
                "cell": "以「细胞坐标点/计数」为单位，支撑细胞学任务与核形态学量化。",
                "qc": "质控层：一致性判定、图像缺陷与仲裁结论，驱动标注治理闭环。",
            }.get(layer, ""),
        }
        for layer in LABEL_LAYERS
    ])


@router.get("/labels/consistency", summary="标注一致性分析（Cohen / Fleiss kappa）")
def consistency(db: DbSession, user: dict = Depends(require("label:read")),
                schema_code: str = Query(""), layer: str = Query("")) -> dict:
    return ok(label_service.consistency_report(db, schema_code=schema_code or None,
                                               layer=layer or None))


@router.get("/labels/annotators/scorecard", summary="标注人员产能与质量评分卡")
def scorecard(db: DbSession, user: dict = Depends(require("label:read"))) -> dict:
    return ok(label_service.annotator_scorecard(db))


@router.get("/labels/sop-status", summary="标注 SOP 与仲裁机制运行状态")
def sop_status(db: DbSession, user: dict = Depends(require("label:read"))) -> dict:
    return ok(label_service.sop_status(db))


@router.post("/labels/arbitrations/{arbitration_id}/resolve", summary="执行仲裁裁决")
def resolve_arbitration(arbitration_id: int, db: DbSession, payload: dict = Body(...),
                        user: dict = Depends(require("label:arbitrate"))) -> dict:
    row = db.get(Arbitration, arbitration_id)
    if row is None:
        raise HTTPException(status_code=404, detail="仲裁记录不存在")
    if row.status == "resolved":
        raise HTTPException(status_code=400, detail="该仲裁已裁决，不可重复裁决")

    final_value = str(payload.get("final_value") or "").strip()
    if not final_value:
        raise HTTPException(status_code=422, detail="必须给出最终裁决值")
    row.update_from({
        "final_value": final_value,
        "arbitrator_name": payload.get("arbitrator_name") or user.get("real_name"),
        "arbitrator_title": payload.get("arbitrator_title") or user.get("title") or "",
        "rule_applied": payload.get("rule_applied") or row.rule_applied,
        "status": "resolved",
        "decided_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
    })
    # 同步把该切片对应标签的最终值写入标注（状态标记为已仲裁）
    if row.slide_id and row.schema_code:
        annotations = list(db.execute(
            select(Annotation).where(
                Annotation.slide_id == row.slide_id, Annotation.schema_code == row.schema_code
            )
        ).scalars())
        for ann in annotations:
            ann.value_text = final_value
            ann.status = "arbitrated"
    db.flush()
    audit(db, user, action="resolve_arbitration", resource_type="arbitration",
          resource_id=row.id, summary=f"裁决仲裁 #{row.id}：{final_value}",
          payload={"final_value": final_value, "slide_code": row.slide_code,
                   "schema_code": row.schema_code},
          risk_level="attention")
    db.commit()
    return ok(row.to_dict())


# ------------------------------------------------------------------ 标注工作台
@router.post("/labels/workbench/save", summary="标注工作台：批量保存某张切片的四层标注")
def workbench_save(db: DbSession, payload: dict = Body(...),
                   user: dict = Depends(require("label:write"))) -> dict:
    """一次提交某张切片的多条标注。

    返回体刻意包含 `missing_required_labels`：让标注者在**录入时**就看见
    注册必备标签还缺哪些，而不是等到注册申报阶段才发现数据不可用。
    """
    from app.models.asset import Slide

    slide_id = payload.get("slide_id")
    items = payload.get("items") or []
    if not slide_id:
        raise HTTPException(status_code=422, detail="必须提供 slide_id")
    if not isinstance(items, list) or not items:
        raise HTTPException(status_code=422, detail="items 必须是非空数组")
    slide = db.get(Slide, int(slide_id))
    if slide is None:
        raise HTTPException(status_code=404, detail="切片不存在")
    try:
        from app.core import scoping

        scoping.assert_slide_access(db, slide, user)
    except Exception as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    result = label_service.save_annotations(
        db, slide=slide, items=items, layer=str(payload.get("layer") or ""),
        annotator_name=str(payload.get("annotator_name") or user.get("real_name", "")),
        annotator_id=payload.get("annotator_id"),
        auto_submit_qc=bool(payload.get("auto_submit_qc", True)),
        actor=user.get("username", ""),
    )
    db.commit()
    return ok(result)


@router.post("/labels/qc/{record_id}/decide", summary="质控判定（不通过自动标记返工）")
def qc_decide(record_id: int, db: DbSession, payload: dict = Body(...),
              user: dict = Depends(require("label:write"))) -> dict:
    from app.models.label import QcRecord

    record = db.get(QcRecord, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="质控记录不存在")
    try:
        label_service.decide_qc(
            db, record=record, result=str(payload.get("result") or "pass"),
            score=float(payload.get("score") or 0.0),
            defect_types=payload.get("defect_types") or [],
            reviewer=user.get("username", ""), note=str(payload.get("note") or ""))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return ok(record.to_dict())


@router.get("/labels/workbench/{slide_id}", summary="标注工作台：拉取某张切片的标签定义与已录入标注")
def workbench_load(slide_id: int, db: DbSession, layer: str = Query(""),
                   user: dict = Depends(require("label:read"))) -> dict:
    """一次返回「要填什么」与「已经填了什么」，让标注页面无需二次请求。"""
    from app.models.asset import Slide
    from app.models.label import Annotation, LabelSchema

    slide = db.get(Slide, slide_id)
    if slide is None:
        raise HTTPException(status_code=404, detail="切片不存在")
    stmt = select(LabelSchema).order_by(LabelSchema.layer, LabelSchema.code)
    if layer:
        stmt = select(LabelSchema).where(LabelSchema.layer == layer).order_by(LabelSchema.code)
    schemas = list(db.execute(stmt).scalars())
    existing = {a.schema_code: a.to_dict() for a in db.execute(
        select(Annotation).where(Annotation.slide_id == slide.id)).scalars()}
    return ok({
        "slide": slide.to_dict(),
        "schemas": [{**s.to_dict(),
                     "allowed_values": __import__("json").loads(s.allowed_values_json or "[]")}
                    for s in schemas],
        "values": existing,
        "filled_count": len(existing),
        "required_missing": [s.code for s in schemas
                             if s.required_for_registration and s.code not in existing],
    })


@router.get("/labels/overview", summary="标签体系总览")
def overview(db: DbSession, user: dict = Depends(require("label:read"))) -> dict:
    coverage = label_service.coverage_report(db)
    consistency = label_service.consistency_report(db)
    sop = label_service.sop_status(db)
    annotation_total = int(db.execute(select(func.count(Annotation.id))).scalar() or 0)
    qc_total = int(db.execute(select(func.count(QcRecord.id))).scalar() or 0)
    qc_fail = int(db.execute(
        select(func.count(QcRecord.id)).where(QcRecord.result != "pass")
    ).scalar() or 0)
    return ok({
        "coverage": coverage,
        "consistency": consistency,
        "sop": sop,
        "annotation_total": annotation_total,
        "qc_total": qc_total,
        "qc_pass_rate": round((qc_total - qc_fail) / qc_total, 6) if qc_total else 0.0,
        "layer_labels": LABEL_LAYER_LABELS,
    })
