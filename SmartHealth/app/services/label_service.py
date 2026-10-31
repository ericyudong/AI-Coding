"""标签体系与标注质量分析。

设计文档依据：第三章「数据资产盘点与治理方案」四层标签体系与质控层。

真实计算标注一致性：
- Cohen's kappa（两标注者，分类标签）
- Fleiss' kappa（多标注者）
- 各层标签覆盖率与注册必备标签的缺口统计（直接对接审评「问一 数据可溯源」）

这些指标是「自有医生标注是比切片数量更稀缺的资产」这一判断的量化依据：
标注再多，若一致性低，也支撑不起注册。
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Sequence

import numpy as np
from sqlalchemy import func, select

from app.core.audit import record_audit
from sqlalchemy.orm import Session

from app.models.asset import Slide
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


# --------------------------------------------------------------------- kappa
def cohen_kappa(labels_a: Sequence[str], labels_b: Sequence[str]) -> dict[str, Any]:
    """两标注者分类标签的一致性（Cohen's kappa）。

    κ = (Po − Pe) / (1 − Pe)；κ ≥ 0.80 视为高度一致（Landis & Koch）。
    """
    pairs = [(str(a), str(b)) for a, b in zip(labels_a, labels_b) if a is not None and b is not None]
    n = len(pairs)
    if n == 0:
        return {"kappa": 0.0, "observed_agreement": 0.0, "expected_agreement": 0.0, "sample_count": 0,
                "interpretation": "无成对样本"}
    a_counts = Counter(p[0] for p in pairs)
    b_counts = Counter(p[1] for p in pairs)
    observed = sum(1 for a, b in pairs if a == b) / n
    expected = sum((a_counts[k] / n) * (b_counts[k] / n) for k in set(a_counts) | set(b_counts))
    kappa = 0.0 if abs(1 - expected) < 1e-12 else (observed - expected) / (1 - expected)
    return {
        "kappa": round(float(kappa), 6),
        "observed_agreement": round(observed, 6),
        "expected_agreement": round(expected, 6),
        "sample_count": n,
        "interpretation": _kappa_band(kappa),
    }


def fleiss_kappa(ratings: Sequence[Sequence[str]]) -> dict[str, Any]:
    """多标注者分类标签一致性（Fleiss' kappa）。`ratings` 为「每例的各标注者标签」。"""
    rows = [[str(x) for x in row if x is not None] for row in ratings]
    rows = [row for row in rows if row]
    if len(rows) < 2:
        return {"kappa": 0.0, "sample_count": len(rows), "interpretation": "样本不足"}

    categories = sorted({c for row in rows for c in row})
    if len(categories) < 2:
        return {"kappa": 1.0, "sample_count": len(rows), "interpretation": "全部一致（无变异类别）"}

    index = {c: i for i, c in enumerate(categories)}
    n_items = len(rows)
    counts = np.zeros((n_items, len(categories)), dtype=np.float64)
    for i, row in enumerate(rows):
        for value in row:
            counts[i, index[value]] += 1
    n_raters = counts.sum(axis=1)
    n_raters = n_raters[n_raters > 1]
    if n_raters.size == 0:
        return {"kappa": 0.0, "sample_count": n_items, "interpretation": "每例标注者不足 2 人"}
    n = float(n_raters.mean())

    p_i = ((counts ** 2).sum(axis=1) - n) / (n * (n - 1))
    p_bar = float(p_i.mean())
    p_j = counts.sum(axis=0) / counts.sum()
    p_e = float((p_j ** 2).sum())
    kappa = 0.0 if abs(1 - p_e) < 1e-12 else (p_bar - p_e) / (1 - p_e)
    return {
        "kappa": round(float(kappa), 6),
        "observed_agreement": round(p_bar, 6),
        "expected_agreement": round(p_e, 6),
        "sample_count": n_items,
        "rater_count": round(n, 3),
        "categories": categories,
        "interpretation": _kappa_band(kappa),
    }


def _kappa_band(kappa: float) -> str:
    if kappa >= 0.80:
        return "高度一致（可用于注册申报证据）"
    if kappa >= 0.60:
        return "中等一致（建议加强 SOP 培训与仲裁）"
    if kappa >= 0.40:
        return "一般一致（存在系统性分歧，需复核标签定义）"
    return "一致性偏低（不足以支撑监督训练与注册证据）"


# ------------------------------------------------------------------ 一致性分析
def consistency_report(db: Session, schema_code: str | None = None,
                       layer: str | None = None) -> dict[str, Any]:
    """按标签（或层级）计算标注一致性。"""
    stmt = select(Annotation)
    if schema_code:
        stmt = stmt.where(Annotation.schema_code == schema_code)
    if layer:
        stmt = stmt.where(Annotation.layer == layer)
    rows = list(db.execute(stmt).scalars())
    if not rows:
        return {"scope": schema_code or layer or "all", "sample_count": 0, "note": "暂无标注记录"}

    grouped: dict[tuple[str, str], dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[(row.schema_code, row.slide_code)][row.annotator_name or f"annotator-{row.annotator_id}"] \
            .append(row.value_text or "")

    per_schema: dict[str, list[list[str]]] = defaultdict(list)
    for (code, _slide), annotators in grouped.items():
        if len(annotators) < 2:
            continue
        # 同一标注者对同一例可能有多条记录，取众数
        values = [Counter(v).most_common(1)[0][0] for v in annotators.values()]
        per_schema[code].append(values)

    results: dict[str, Any] = {}
    for code, ratings in per_schema.items():
        if len(ratings) < 2:
            continue
        if all(len(r) == 2 for r in ratings):
            pairs = [(r[0], r[1]) for r in ratings]
            results[code] = cohen_kappa([p[0] for p in pairs], [p[1] for p in pairs])
        else:
            results[code] = fleiss_kappa(ratings)

    kappas = [v["kappa"] for v in results.values()]
    return {
        "scope": schema_code or layer or "all",
        "annotation_total": len(rows),
        "multi_annotated_slide_count": len(grouped),
        "comparable_label_count": len(results),
        "per_label": results,
        "mean_kappa": round(float(np.mean(kappas)), 6) if kappas else None,
        "min_kappa": round(float(np.min(kappas)), 6) if kappas else None,
        "overall_interpretation": _kappa_band(float(np.mean(kappas))) if kappas else "样本不足，无法评估",
        "single_annotator_slide_count": sum(1 for v in grouped.values() if len(v) < 2),
    }


# ------------------------------------------------------------------ 标签覆盖
def coverage_report(db: Session, scope_stainings: Sequence[str] = ("H&E",)) -> dict[str, Any]:
    """四层标签体系覆盖率与注册必备标签缺口。

    覆盖率的**分母口径**只统计「在能力声明与预期用途范围内」的切片
    （默认仅 H&E 染色）。把超出声明范围的切片（如细胞学涂片）算进分母，
    会人为制造永远填不平的注册缺口 —— 这类口径错误在注册阶段代价很高。
    """
    all_slides = list(db.execute(select(Slide)).scalars())
    scopes = tuple(s.lower() for s in scope_stainings) if scope_stainings else ()
    slides = [
        s for s in all_slides
        if not scopes or any(scope in (s.staining or "").lower() for scope in scopes)
    ]
    schemas = list(db.execute(select(LabelSchema)).scalars())
    annotations = list(db.execute(select(Annotation)).scalars())

    covered: dict[int, set[str]] = defaultdict(set)
    layer_counts: Counter = Counter()
    scope_codes = {s.code for s in slides}
    for ann in annotations:
        if ann.slide_code not in scope_codes:
            continue
        covered[ann.schema_id].add(ann.slide_code)
        layer_counts[ann.layer] += 1

    total_slides = max(len(slides), 1)
    by_layer: dict[str, Any] = {}
    for layer in LABEL_LAYERS:
        layer_schemas = [s for s in schemas if s.layer == layer]
        annotated_slides: set[str] = set()
        for schema in layer_schemas:
            annotated_slides |= covered.get(schema.id, set())
        by_layer[layer] = {
            "label": LABEL_LAYER_LABELS[layer],
            "schema_count": len(layer_schemas),
            "annotation_count": layer_counts.get(layer, 0),
            "annotated_slide_count": len(annotated_slides),
            "coverage_rate": round(len(annotated_slides) / total_slides, 6),
            "schemas": [
                {
                    "code": s.code, "name": s.name, "value_type": s.value_type,
                    "required_for_training": s.required_for_training,
                    "required_for_registration": s.required_for_registration,
                    "annotated_slide_count": len(covered.get(s.id, set())),
                    "snomed_code": s.snomed_code,
                }
                for s in layer_schemas
            ],
        }

    registration_required = [s for s in schemas if s.required_for_registration]
    gaps: list[dict[str, Any]] = []
    for schema in registration_required:
        have = len(covered.get(schema.id, set()))
        if have < total_slides:
            gaps.append({
                "code": schema.code, "name": schema.name, "layer": schema.layer,
                "annotated": have, "expected": total_slides,
                "missing": total_slides - have,
                "coverage_rate": round(have / total_slides, 6),
                "blocking": True,
            })

    return {
        "slide_total": len(slides),
        "slide_total_all": len(all_slides),
        "scope_stainings": list(scope_stainings),
        "annotation_total": len(annotations),
        "schema_total": len(schemas),
        "by_layer": by_layer,
        "registration_required_count": len(registration_required),
        "registration_gaps": gaps,
        "registration_ready": len(gaps) == 0,
        "note": (
            "注册必备标签已全覆盖，可直接支撑「数据可溯源」的审评应答。"
            if not gaps else
            f"存在 {len(gaps)} 项注册必备标签未全覆盖，将阻断注册申报（对应审评问一）。"
        ),
    }


def annotator_scorecard(db: Session) -> list[dict[str, Any]]:
    """标注人员产能与质量评分卡（对应 SOP 要求的运行记录）。"""
    annotators = list(db.execute(select(AnnotatorProfile)).scalars())
    result: list[dict[str, Any]] = []
    for profile in annotators:
        ann_count = int(db.execute(
            select(func.count(Annotation.id)).where(Annotation.annotator_id == profile.id)
        ).scalar() or 0)
        qc_rows = list(db.execute(
            select(QcRecord).where(QcRecord.reviewer_name == profile.name)
        ).scalars())
        passed = sum(1 for q in qc_rows if q.result == "pass")
        arbitrations = int(db.execute(
            select(func.count(Arbitration.id)).where(Arbitration.arbitrator_name == profile.name)
        ).scalar() or 0)
        avg_elapsed = float(db.execute(
            select(func.avg(Annotation.elapsed_sec)).where(Annotation.annotator_id == profile.id)
        ).scalar() or 0.0)
        result.append({
            "id": profile.id,
            "name": profile.name,
            "title": profile.title,
            "subspecialty": profile.subspecialty,
            "hospital": profile.hospital,
            "years_experience": profile.years_experience,
            "qualification_verified": profile.qualification_verified,
            "training_hours": profile.training_hours,
            "annotation_count": ann_count,
            "avg_elapsed_sec": round(avg_elapsed, 2),
            "qc_reviewed": len(qc_rows),
            "qc_pass_rate": round(passed / len(qc_rows), 6) if qc_rows else None,
            "arbitration_count": arbitrations,
            "status": profile.status,
        })
    result.sort(key=lambda x: -x["annotation_count"])
    return result


def sop_status(db: Session) -> dict[str, Any]:
    """标注 SOP 的审核状态汇总。注册阶段必须提供完整 SOP 与运行记录。"""
    sops = list(db.execute(select(LabelSop)).scalars())
    approved = [s for s in sops if s.medical_review_status == "approved"]
    arbitrations = list(db.execute(select(Arbitration)).scalars())
    open_arbitrations = [a for a in arbitrations if a.status != "resolved"]
    return {
        "sop_total": len(sops),
        "approved_count": len(approved),
        "pending_count": len(sops) - len(approved),
        "all_approved": len(sops) > 0 and len(approved) == len(sops),
        "sops": [s.to_dict() for s in sops],
        "arbitration_total": len(arbitrations),
        "arbitration_open": len(open_arbitrations),
        "arbitration_resolved": len(arbitrations) - len(open_arbitrations),
        "note": (
            "标注 SOP 已全部通过医学审核，仲裁机制运行记录完整。"
            if sops and len(approved) == len(sops) else
            "仍有 SOP 未通过医学审核，注册申报前必须补齐。"
        ),
    }


# ================================================================ 标注写入闭环
def save_annotations(db: Session, *, slide: Any, items: list[dict[str, Any]], layer: str = "",
                     annotator_name: str = "", annotator_id: int | None = None,
                     auto_submit_qc: bool = True, actor: str = "") -> dict[str, Any]:
    """按标签定义批量写入/更新某张切片的标注。

    为什么必须走这一层而不是直接开 CRUD：
    1. **schema 校验**：值类型、允许值域、单位必须与 LabelSchema 一致。
       否则「分级 = 3a」这类脏值进库后，训练时会静默变成 NaN，很难倒查。
    2. **注册必备标签检查**：写入后立刻反馈「还缺哪些注册必备标签」，
       把合规缺口暴露在标注现场，而不是半年后在注册申报时才发现。
    3. **一致性触发**：标注变更后自动排队一致性重算，让 kappa 始终反映现状。
    """
    from app.models.label import Annotation, LabelSchema

    schemas = {s.code: s for s in db.execute(select(LabelSchema)).scalars()}
    applied: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    now = datetime.now().isoformat(timespec="seconds")

    for raw in items:
        code = str(raw.get("schema_code") or "").strip()
        schema = schemas.get(code)
        if schema is None:
            rejected.append({"schema_code": code, "error": "未定义的标签编码"})
            continue
        if layer and schema.layer != layer:
            rejected.append({"schema_code": code,
                             "error": f"标签层级为 {schema.layer}，与提交层级 {layer} 不符"})
            continue

        value_text = str(raw.get("value_text") or "").strip()
        value_num = raw.get("value_num")
        if value_num in ("", None):
            value_num = None
        else:
            try:
                value_num = float(value_num)
            except (TypeError, ValueError):
                rejected.append({"schema_code": code, "error": f"value_num 非数值：{value_num!r}"})
                continue

        if schema.value_type in ("numeric", "number") and value_num is None and not value_text:
            rejected.append({"schema_code": code, "error": "数值型标签必须提供 value_num"})
            continue
        if schema.value_type in ("categorical", "enum", "boolean") and not value_text:
            rejected.append({"schema_code": code, "error": "分类型标签必须提供 value_text"})
            continue
        if schema.value_type in ("categorical", "enum") and schema.allowed_values_json:
            try:
                allowed = json.loads(schema.allowed_values_json or "[]")
            except Exception:
                allowed = []
            if allowed and value_text not in allowed:
                rejected.append({"schema_code": code,
                                 "error": f"取值 {value_text} 不在允许集合 {allowed} 内"})
                continue

        existing = db.execute(
            select(Annotation).where(Annotation.slide_id == slide.id,
                                     Annotation.schema_code == code)
        ).scalar_one_or_none()
        # 只写入 Annotation 真实存在的列：多余键会让 SQLAlchemy 在构造时报 TypeError，
        # 而且这种错误在标注场景下会让整批提交失败，用户看到的是「保存失败」而非具体原因。
        payload = {
            "slide_id": slide.id,
            "slide_code": slide.code,
            "schema_id": schema.id,
            "schema_code": code,
            "layer": schema.layer,
            "value_text": value_text,
            "value_num": value_num,
            "region_json": json.dumps(raw.get("region") or [], ensure_ascii=False),
            "confidence": float(raw.get("confidence") or 1.0),
            "annotator_name": annotator_name,
            "annotator_id": annotator_id,
            "tool": "workbench",
            "status": str(raw.get("status") or "submitted"),
            "note": str(raw.get("note") or ""),
        }
        if existing is not None:
            payload["revision"] = int(existing.revision or 1) + 1
            existing.update_from(payload)
            applied.append({"schema_code": code, "action": "updated",
                            "revision": payload["revision"]})
        else:
            db.add(Annotation(**payload))
            applied.append({"schema_code": code, "action": "created", "revision": 1})

    db.flush()

    # 注册必备标签缺口（写入后立刻反馈）
    required = [s for s in schemas.values() if s.required_for_registration]
    have = {a.schema_code for a in db.execute(
        select(Annotation).where(Annotation.slide_id == slide.id)).scalars()}
    missing_required = [s.code for s in required if s.code not in have]

    slide_status = "annotated" if not missing_required else "partially_annotated"
    slide.status = slide_status

    qc_record = None
    if auto_submit_qc and applied:
        qc_record = submit_for_qc(db, slide=slide, reviewer_name=actor or annotator_name)

    record_audit(db, action="save_annotations", resource_type="slide", resource_id=slide.id,
                 actor=actor or annotator_name,
                 summary=(f"保存切片 {slide.code} 标注：成功 {len(applied)}、"
                          f"拒绝 {len(rejected)}、注册必备缺口 {len(missing_required)}"),
                 payload={"applied": applied, "rejected": rejected,
                          "missing_required": missing_required})

    return {
        "slide_id": slide.id,
        "slide_code": slide.code,
        "applied": applied,
        "rejected": rejected,
        "applied_count": len(applied),
        "rejected_count": len(rejected),
        "missing_required_labels": missing_required,
        "registration_blocking": bool(missing_required),
        "qc_record_id": qc_record.id if qc_record else None,
        "slide_status": slide_status,
    }


def submit_for_qc(db: Session, *, slide: Any, reviewer_name: str = "",
                  qc_type: str = "sampling", result: str = "pending") -> Any:
    """把标注提交质控。质控不通过的标注必须返工后才可进入训练集。"""
    from app.models.label import QcRecord

    record = QcRecord(
        slide_id=slide.id,
        slide_code=slide.code,
        qc_type=qc_type,
        reviewer_name=reviewer_name,
        result=result,
        score=0.0,
        defect_types_json="[]",
        rework_required=False,
        reviewed_at=datetime.now().isoformat(timespec="seconds"),
        note="标注提交后自动入质控队列",
    )
    db.add(record)
    db.flush()
    return record


def decide_qc(db: Session, *, record: Any, result: str, score: float = 0.0,
              defect_types: list[str] | None = None, reviewer: str = "",
              note: str = "") -> Any:
    """质控判定。判定为不通过时自动标记返工，并回写切片的标注状态。"""
    from app.models.asset import Slide

    if result not in ("pass", "fail", "conditional"):
        raise ValueError("result 仅支持 pass / fail / conditional")
    record.result = result
    record.score = float(score)
    record.defect_types_json = json.dumps(defect_types or [], ensure_ascii=False)
    record.rework_required = result == "fail"
    record.reviewer_name = reviewer or record.reviewer_name
    record.reviewed_at = datetime.now().isoformat(timespec="seconds")
    record.note = note or record.note
    if record.slide_id:
        slide = db.get(Slide, record.slide_id)
        if slide is not None:
            slide.status = "annotated" if result == "pass" else "needs_rework"
    record_audit(db, action="decide_qc", resource_type="qc_record", resource_id=record.id,
                 actor=reviewer,
                 summary=f"质控判定 {result}（切片 {record.slide_code}，评分 {score}）",
                 payload={"defects": defect_types or [], "rework": record.rework_required},
                 risk_level="attention" if result == "fail" else "normal")
    return record
