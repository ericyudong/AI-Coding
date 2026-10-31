"""评测基座接口（对应设计文档第四章 M3 里程碑、第七章临床可验证、第十章 R3）。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import func, select

from app.api.v1.common import crud_router, list_query, ok, serialize
from app.core.config import settings
from app.core.deps import CurrentUser, DbSession, audit, require
from app.models.evaluation import (
    EvalDataset,
    EvalDatasetItem,
    EvalMetric,
    EvalRocPoint,
    EvalRun,
    MrMcComparison,
)
from app.models.modeling import ModelVersion
from app.models.pipeline import SlidePrediction
from app.services import experiment_service, job_service
from app.services.evaluation_service import (
    best_threshold,
    confusion_at_threshold,
    full_report,
    generalization_gap,
    mrmc_report,
    roc_curve_points,
)

router = APIRouter(tags=["07 评测基座"])


def _want_async(payload: dict) -> bool:
    """是否走异步作业：默认异步，显式 sync=true 才同步。"""
    if str(payload.get("sync")).lower() in ("1", "true", "yes"):
        return False
    return bool(settings.job_async_default)


def _job_brief(job) -> dict:
    return {"id": job.id, "code": job.code, "status": job.status,
            "type": job.job_type, "title": job.title,
            "status_label": job.status_label, "progress": job.progress}

router.include_router(crud_router(
    model=EvalDataset, prefix="/eval/datasets", tag="评测集", resource_type="eval_dataset",
    permission_read="eval:read", permission_write="eval:write",
    search_fields=("code", "name", "description", "owner_name"),
    filter_fields=("dataset_kind", "is_external", "task_code", "frozen"),
    order_by="id", summary_template="更新评测集 {row.code} {row.name}",
))

router.include_router(crud_router(
    model=EvalDatasetItem, prefix="/eval/dataset-items", tag="评测集成员",
    resource_type="eval_dataset_item",
    permission_read="eval:read", permission_write="eval:write",
    search_fields=("slide_code", "case_no", "label_truth"),
    filter_fields=("dataset_id", "site_code", "label_truth"),
    order_by="id",
))

router.include_router(crud_router(
    model=EvalRun, prefix="/eval/runs", tag="评测运行", resource_type="eval_run",
    permission_read="eval:read", permission_write=None,
    search_fields=("code", "model_version_label", "task_code", "pass_note"),
    filter_fields=("dataset_id", "model_version_id", "status", "passed", "task_code"),
    json_fields=("confusion_json", "by_site_json", "reliability_json", "generalization_json"),
    order_by="id",
))

router.include_router(crud_router(
    model=EvalMetric, prefix="/eval/metrics", tag="评测指标", resource_type="eval_metric",
    permission_read="eval:read", permission_write=None,
    search_fields=("metric_key", "metric_label"),
    filter_fields=("run_id", "group_key", "metric_key"),
    order_by="id",
))

router.include_router(crud_router(
    model=MrMcComparison, prefix="/eval/mrmc", tag="MRMC 对照", resource_type="mrmc_comparison",
    permission_read="eval:read", permission_write=None,
    search_fields=("code", "conclusion", "reader_a_name", "reader_b_name"),
    filter_fields=("dataset_id", "status"),
    order_by="id",
))


@router.get("/eval/datasets/{dataset_id}/detail", summary="评测集详情（含按中心分组统计）")
def dataset_detail(dataset_id: int, db: DbSession,
                   user: dict = Depends(require("eval:read"))) -> dict:
    dataset = db.get(EvalDataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="评测集不存在")
    items = list(db.execute(
        select(EvalDatasetItem).where(EvalDatasetItem.dataset_id == dataset.id)
    ).scalars())
    by_site: dict[str, dict] = {}
    for item in items:
        bucket = by_site.setdefault(item.site_code, {"slides": 0, "positive": 0, "case_count": 0})
        bucket["slides"] += 1
        bucket["positive"] += 1 if item.label_truth == "转移阳性" else 0
    runs = list(db.execute(
        select(EvalRun).where(EvalRun.dataset_id == dataset.id).order_by(EvalRun.id.desc())
    ).scalars())
    return ok({
        **dataset.to_dict(),
        "by_site": by_site,
        "item_count": len(items),
        "items": [i.to_dict() for i in items],
        "runs": [r.to_dict() for r in runs],
        "freeze_note": (
            "评测集已冻结，禁止增删成员 —— 冻结是注册阶段保证「不同版本结果可比」的前提。"
            if dataset.frozen else
            "评测集未冻结，版本间结果不可直接比较。"
        ),
    })


@router.get("/eval/runs/{run_id}/detail", summary="评测运行详情（ROC / 混淆矩阵 / 校准曲线 / 分组）")
def run_detail(run_id: int, db: DbSession,
               user: dict = Depends(require("eval:read"))) -> dict:
    run = db.get(EvalRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="评测运行不存在")
    roc = list(db.execute(
        select(EvalRocPoint).where(EvalRocPoint.run_id == run.id).order_by(EvalRocPoint.fpr.asc())
    ).scalars())
    metrics = list(db.execute(
        select(EvalMetric).where(EvalMetric.run_id == run.id).order_by(EvalMetric.id.asc())
    ).scalars())
    dataset = db.get(EvalDataset, run.dataset_id)
    return ok({
        **run.to_dict(),
        "confusion": json.loads(run.confusion_json or "{}"),
        "by_site": json.loads(run.by_site_json or "{}"),
        "reliability": json.loads(run.reliability_json or "[]"),
        "generalization": json.loads(run.generalization_json or "{}"),
        "roc_points": [p.to_dict() for p in roc],
        "metrics": [m.to_dict() for m in metrics],
        "dataset": dataset.to_dict() if dataset else None,
        "metric_guide": {
            "auroc": "排序能力。临床关注灵敏度的场景下需与敏感度/特异度联合看。",
            "ece": "期望校准误差。校准质量直接决定「置信度分级」与「拒识」是否可信。",
            "brier": "概率预测的综合误差（越低越好）。",
            "ci": "自举百分位置信区间（默认 300—500 轮）。",
        },
    })


@router.post("/eval/run", summary="执行评测（默认异步，返回作业句柄）")
def run_eval(db: DbSession, payload: dict = Body(...),
             user: dict = Depends(require("eval:write"))) -> dict:
    """执行评测。

    默认**异步**：评测含自举置信区间（数百轮重采样），同步执行会让请求挂住数十秒。
    提交后立即返回作业句柄，前端凭 `job_id` 轮询进度。
    传 `sync=true` 可退回同步执行（自动化测试与小数据集排障用）。
    """
    if not payload.get("dataset_id"):
        raise HTTPException(status_code=422, detail="必须提供 dataset_id")

    if _want_async(payload):
        job = job_service.submit_eval(
            db, dataset_id=int(payload["dataset_id"]),
            model_version_id=payload.get("model_version_id"),
            threshold=float(payload.get("threshold") or 0.5),
            bootstrap_rounds=int(payload.get("bootstrap_rounds") or 300),
            allow_missing=bool(payload.get("allow_missing")),
            actor=user.get("username", ""), actor_name=user.get("real_name", ""))
        return ok({"async": True, "job": _job_brief(job)}, message="评测作业已提交")

    try:
        outcome = experiment_service.execute_eval_run(
            db, dataset_id=int(payload["dataset_id"]),
            model_version_id=payload.get("model_version_id"),
            threshold=float(payload.get("threshold") or 0.5),
            bootstrap_rounds=int(payload.get("bootstrap_rounds") or 300),
            allow_missing=bool(payload.get("allow_missing")),
            actor=user.get("username", ""))
    except experiment_service.DomainError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return ok(outcome)


@router.post("/eval/mrmc-run", summary="执行 MRMC 对照（AI vs 两名阅片者；默认异步）")
def run_mrmc(db: DbSession, payload: dict = Body(...),
             user: dict = Depends(require("eval:write"))) -> dict:
    if not payload.get("dataset_id"):
        raise HTTPException(status_code=422, detail="必须提供 dataset_id")

    if _want_async(payload):
        job = job_service.submit_mrmc(db, payload=payload, actor=user.get("username", ""),
                                      actor_name=user.get("real_name", ""))
        return ok({"async": True, "job": _job_brief(job)}, message="MRMC 对照作业已提交")

    try:
        outcome = experiment_service.execute_mrmc_run(
            db, dataset_id=int(payload["dataset_id"]),
            model_version_id=payload.get("model_version_id"),
            reader_a_name=str(payload.get("reader_a_name") or "阅片者 A"),
            reader_a_title=str(payload.get("reader_a_title") or ""),
            reader_b_name=str(payload.get("reader_b_name") or "阅片者 B"),
            reader_b_title=str(payload.get("reader_b_title") or ""),
            positive_label=str(payload.get("positive_label") or "转移阳性"),
            bootstrap_rounds=int(payload.get("bootstrap_rounds") or 300),
            actor=user.get("username", ""))
    except experiment_service.DomainError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return ok(outcome)


@router.get("/eval/threshold-sweep", summary="阈值扫描（按 Youden 指数择优）")
def threshold_sweep(db: DbSession, dataset_id: int = Query(...),
                    user: dict = Depends(require("eval:read"))) -> dict:
    dataset = db.get(EvalDataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="评测集不存在")
    items = list(db.execute(
        select(EvalDatasetItem).where(EvalDatasetItem.dataset_id == dataset.id)
    ).scalars())
    version = db.execute(select(ModelVersion).order_by(ModelVersion.id.desc()).limit(1)).scalar_one_or_none()
    preds = {
        p.slide_code: p for p in db.execute(
            select(SlidePrediction).where(SlidePrediction.model_version_id == version.id)
        ).scalars()
    } if version else {}
    y = [1.0 if i.label_truth == "转移阳性" else 0.0 for i in items]
    scores = [preds[i.slide_code].calibrated_probability if i.slide_code in preds else 0.5
              for i in items]
    if not y:
        raise HTTPException(status_code=400, detail="评测集为空")

    sweep = []
    for threshold in [i / 100 for i in range(5, 100, 5)]:
        metrics = confusion_at_threshold(y, scores, threshold)
        sweep.append({
            "threshold": threshold,
            "sensitivity": metrics["sensitivity"],
            "specificity": metrics["specificity"],
            "youden_index": metrics["youden_index"],
            "ppv": metrics["ppv"],
            "npv": metrics["npv"],
        })
    return ok({
        "dataset": dataset.code,
        "sweep": sweep,
        "best": best_threshold(y, scores),
        "note": (
            "筛查场景通常优先保证高敏感度（减少漏诊），再由医生终审控制特异度；"
            "阈值选择必须在冻結的评测集上进行，且需在注册资料中固定。"
        ),
    })


@router.get("/eval/overview", summary="评测基座总览")
def overview(db: DbSession, user: dict = Depends(require("eval:read"))) -> dict:
    datasets = list(db.execute(select(EvalDataset)).scalars())
    runs = list(db.execute(select(EvalRun).order_by(EvalRun.id.desc()).limit(10)).scalars())
    datasets_by_kind: dict[str, int] = {}
    for dataset in datasets:
        datasets_by_kind[dataset.dataset_kind] = datasets_by_kind.get(dataset.dataset_kind, 0) + 1
    latest_internal = next((r for r in runs if not json.loads(r.by_site_json or "{}") == {}), None)
    mrmc = list(db.execute(
        select(MrMcComparison).order_by(MrMcComparison.id.desc()).limit(5)
    ).scalars())
    return ok({
        "dataset_count": len(datasets),
        "datasets_by_kind": datasets_by_kind,
        "external_dataset_count": sum(1 for d in datasets if d.is_external),
        "run_count": int(db.execute(select(func.count(EvalRun.id))).scalar() or 0),
        "recent_runs": [{**r.to_dict(),
                         "generalization": json.loads(r.generalization_json or "{}")}
                        for r in runs],
        "mrmc_comparisons": [m.to_dict() for m in mrmc],
        "latest_internal_auroc": latest_internal.auroc if latest_internal else 0.0,
        "milestone_m3_gate": {
            "criterion": "内部验证集 AUROC 达预设阈值（≥0.90），外部验证通过",
            "internal_passed": any(r.passed for r in runs if not r.dataset_id),
            "note": "请在「评测集详情」中查看每个评测集的判定结果。",
        },
    })
