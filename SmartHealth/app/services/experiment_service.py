"""实验编排层：把「评测 / MRMC 对照」这类多步业务从 API 路由中抽出。

为什么要单独一层（这是商用系统的结构性要求）：
同一个业务动作有两个入口 —— 用户点按钮（HTTP 同步）与作业引擎调度（后台异步）。
若逻辑写在路由函数里，异步作业就必须复制一份，两份代码必然逐渐分叉。
抽出编排层后，两个入口调用同一份实现，行为不可能不一致。

本模块负责：「取数据 → 调算法 → 落库 → 写审计」，不含任何 HTTP 概念（不抛 HTTPException，
只抛 ValueError/DomainError），由调用方决定如何转成响应或作业失败。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
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
from app.services.evaluation_service import (
    full_report,
    generalization_gap,
    mrmc_report,
    roc_curve_points,
)


class DomainError(ValueError):
    """业务规则不满足。调用方决定映射为 400 还是作业失败。

    `non_retryable=True` 供作业引擎识别：这类错误重试不会改变结果。
    """

    non_retryable = True


def resolve_model_version(db: Session, version_id: int | None,
                          *, require_registration_candidate: bool = False) -> ModelVersion:
    """解析模型版本。未指定时优先取注册候选，其次取最新。"""
    if version_id:
        version = db.get(ModelVersion, int(version_id))
        if version is None:
            raise DomainError(f"模型版本 #{version_id} 不存在")
        return version
    stmt = select(ModelVersion)
    if require_registration_candidate:
        stmt = stmt.where(ModelVersion.is_registration_candidate.is_(True))
    version = db.execute(stmt.order_by(ModelVersion.id.desc()).limit(1)).scalar_one_or_none()
    if version is None:
        raise DomainError("没有可用的模型版本，请先执行训练")
    return version


def _best_version_for_dataset(db: Session, items: list[EvalDatasetItem]) -> ModelVersion | None:
    """未指定模型版本时，自动选取「在该评测集上覆盖预测最多」的版本。

    为什么不简单取最新：最新版本往往是刚训出来、还没跑推理的那个，
    直接评测必然报「缺少预测结果」。这是最容易让用户困惑的一类失败 ——
    与其报错，不如按实际数据选一个可评测的版本，并在结果里注明选了谁。
    """
    codes = [i.slide_code for i in items]
    if not codes:
        return None
    rows = db.execute(
        select(SlidePrediction.model_version_id, func.count(SlidePrediction.id))
        .where(SlidePrediction.slide_code.in_(codes))
        .group_by(SlidePrediction.model_version_id)
        .order_by(func.count(SlidePrediction.id).desc())
    ).all()
    for version_id, _count in rows:
        if version_id:
            version = db.get(ModelVersion, int(version_id))
            if version is not None:
                return version
    return None


def _load_dataset_items(db: Session, dataset_id: int) -> tuple[EvalDataset, list[EvalDatasetItem]]:
    dataset = db.get(EvalDataset, int(dataset_id))
    if dataset is None:
        raise DomainError(f"评测集 #{dataset_id} 不存在")
    items = list(db.execute(
        select(EvalDatasetItem).where(EvalDatasetItem.dataset_id == dataset.id)
    ).scalars())
    if not items:
        raise DomainError("评测集为空")
    return dataset, items


def _positive_label(dataset: EvalDataset) -> str:
    return "转移阳性"


def execute_eval_run(
    db: Session,
    *,
    dataset_id: int,
    model_version_id: int | None = None,
    threshold: float = 0.5,
    bootstrap_rounds: int = 300,
    allow_missing: bool = False,
    actor: str = "",
    progress_cb: Callable[[float, str], None] | None = None,
) -> dict[str, Any]:
    """执行一次评测并落库。返回 {run, report, generalization}。"""

    def _report(pct: float, stage: str) -> None:
        if progress_cb is not None:
            progress_cb(pct, stage)

    _report(0.05, "加载评测集与模型版本")
    dataset, items = _load_dataset_items(db, dataset_id)
    version = (resolve_model_version(db, model_version_id) if model_version_id
               else _best_version_for_dataset(db, items) or resolve_model_version(db, None))

    _report(0.25, f"收集模型 {version.semver} 在评测集上的预测结果")
    preds = {
        p.slide_code: p for p in db.execute(
            select(SlidePrediction).where(SlidePrediction.model_version_id == version.id)
        ).scalars()
    }
    missing = [i.slide_code for i in items if i.slide_code not in preds]
    if missing and not allow_missing:
        raise DomainError(
            f"评测集中有 {len(missing)} 张切片尚无该版本的预测结果"
            f"（例如 {missing[:3]}）。请先运行推理，或开启 allow_missing 以 0.5 占位。"
        )

    pos_label = _positive_label(dataset)
    y = [1.0 if i.label_truth == pos_label else 0.0 for i in items]
    scores = [preds[i.slide_code].calibrated_probability if i.slide_code in preds else 0.5
              for i in items]

    _report(0.45, f"计算指标（{len(items)} 例，自举 {bootstrap_rounds} 轮）")
    report = full_report(y, scores, threshold=float(threshold),
                         groups=[i.site_code for i in items],
                         bootstrap_rounds=int(bootstrap_rounds))

    _report(0.75, "计算跨中心泛化衰减与 ROC 曲线")
    gap = generalization_gap(report.get("by_group") or {}, in_domain_keys=["SITE-A", "SITE-B"])
    points = roc_curve_points(y, scores, max_points=120)

    _report(0.88, "落库评测结果与指标明细")
    now = datetime.now().isoformat(timespec="seconds")
    run = EvalRun(
        code=f"ER-{dataset.code}-{datetime.now().strftime('%m%d%H%M%S')}",
        dataset_id=dataset.id, model_version_id=version.id,
        model_version_label=version.semver, task_code=dataset.task_code,
        threshold=float(threshold), bootstrap_rounds=int(bootstrap_rounds), status="succeeded",
        sample_count=report["sample_count"], positive_count=report["positive_count"],
        auroc=report["auroc"], auprc=report["auprc"], accuracy=report["accuracy"],
        sensitivity=report["sensitivity"], specificity=report["specificity"],
        ppv=report["ppv"], npv=report["npv"], f1=report["f1"],
        brier=report["brier"], ece=report["ece"],
        auroc_ci_low=report["auroc_ci_low"], auroc_ci_high=report["auroc_ci_high"],
        confusion_json=json.dumps(report["confusion"], ensure_ascii=False),
        by_site_json=json.dumps(report.get("by_group") or {}, ensure_ascii=False),
        reliability_json=json.dumps(report.get("reliability") or [], ensure_ascii=False),
        generalization_json=json.dumps({**gap, "missing_prediction_count": len(missing)},
                                       ensure_ascii=False),
        started_at=now, finished_at=now, elapsed_ms=0,
        passed=report["auroc"] >= 0.90,
        pass_note=("达到预设 AUROC ≥ 0.90 的里程碑门槛" if report["auroc"] >= 0.90
                   else "未达预设 AUROC ≥ 0.90 门槛"),
        triggered_by=actor,
    )
    db.add(run)
    db.flush()
    for point in points:
        db.add(EvalRocPoint(run_id=run.id, group_key="overall", **point))
    for key, label, value, low, high in (
        ("auroc", "AUROC", report["auroc"], report["auroc_ci_low"], report["auroc_ci_high"]),
        ("auprc", "AUPRC", report["auprc"], 0.0, 0.0),
        ("accuracy", "准确率", report["accuracy"], 0.0, 0.0),
        ("sensitivity", "敏感度", report["sensitivity"], 0.0, 0.0),
        ("specificity", "特异度", report["specificity"], 0.0, 0.0),
        ("ppv", "阳性预测值", report["ppv"], 0.0, 0.0),
        ("npv", "阴性预测值", report["npv"], 0.0, 0.0),
        ("f1", "F1", report["f1"], 0.0, 0.0),
        ("brier", "Brier 分数", report["brier"], 0.0, 0.0),
        ("ece", "期望校准误差(ECE)", report["ece"], 0.0, 0.0),
    ):
        db.add(EvalMetric(run_id=run.id, group_key="overall", metric_key=key,
                          metric_label=label, value=value, ci_low=low, ci_high=high,
                          sample_count=report["sample_count"]))
    for site, payload_site in (report.get("by_group") or {}).items():
        db.add(EvalMetric(run_id=run.id, group_key=f"site:{site}", metric_key="auroc",
                          metric_label="AUROC", value=payload_site["auroc"],
                          sample_count=payload_site["sample_count"]))
    db.flush()

    record_audit(db, action="run_eval", resource_type="eval_run", resource_id=run.id, actor=actor,
                 summary=f"评测 {run.code}：AUROC {report['auroc']:.4f}"
                         f"（数据集 {dataset.code}，模型 {version.semver}）",
                 payload={"report": {k: v for k, v in report.items() if k != "reliability"},
                          "generalization": gap, "as_job": bool(progress_cb)})
    _report(0.98, "评测完成")
    return {"run": run.to_dict(), "report": report, "generalization": gap,
            "missing_prediction_count": len(missing)}


def execute_mrmc_run(
    db: Session,
    *,
    dataset_id: int,
    model_version_id: int | None = None,
    reader_a_name: str = "阅片者 A",
    reader_a_title: str = "",
    reader_b_name: str = "阅片者 B",
    reader_b_title: str = "",
    positive_label: str = "转移阳性",
    bootstrap_rounds: int = 300,
    actor: str = "",
    progress_cb: Callable[[float, str], None] | None = None,
) -> dict[str, Any]:
    """执行 MRMC 对照（AI vs 两名阅片者）并落库。"""

    def _report(pct: float, stage: str) -> None:
        if progress_cb is not None:
            progress_cb(pct, stage)

    _report(0.05, "加载评测集与阅片者判读记录")
    dataset, items = _load_dataset_items(db, dataset_id)
    version = (resolve_model_version(db, model_version_id) if model_version_id
               else _best_version_for_dataset(db, items) or resolve_model_version(db, None))

    _report(0.3, "收集 AI 与阅片者判读")
    preds = {
        p.slide_code: p for p in db.execute(
            select(SlidePrediction).where(SlidePrediction.model_version_id == version.id)
        ).scalars()
    }
    y = [1.0 if i.label_truth == positive_label else 0.0 for i in items]
    scores = [preds[i.slide_code].calibrated_probability if i.slide_code in preds else 0.5
              for i in items]

    _report(0.55, f"配对自举检验（{bootstrap_rounds} 轮）")
    outcome = mrmc_report(
        y, scores, [i.reader_a_label for i in items], [i.reader_b_label for i in items],
        positive_label=positive_label, bootstrap_rounds=int(bootstrap_rounds),
    )

    _report(0.85, "落库对照结果")
    row = MrMcComparison(
        code=f"MM-{dataset.code}-{datetime.now().strftime('%m%d%H%M%S')}",
        dataset_id=dataset.id, model_version_label=version.semver,
        reader_a_name=reader_a_name, reader_a_title=reader_a_title,
        reader_b_name=reader_b_name, reader_b_title=reader_b_title,
        auc_ai=outcome["auc_ai"], auc_reader_a=outcome["auc_reader_a"],
        auc_reader_b=outcome["auc_reader_b"], reader_average_auc=outcome["reader_average_auc"],
        delta_ai_vs_reader_a=outcome["delta_ai_vs_reader_a"],
        delta_ai_vs_reader_a_ci_low=outcome["delta_ai_vs_reader_a_ci_low"],
        delta_ai_vs_reader_a_ci_high=outcome["delta_ai_vs_reader_a_ci_high"],
        p_value=outcome["p_value"], method=outcome["method"], conclusion=outcome["conclusion"],
        status="done",
        note="参照《人工智能医疗器械注册审查指导原则》以 MRMC 方式设计对照。",
    )
    db.add(row)
    db.flush()
    record_audit(db, action="run_mrmc", resource_type="mrmc_comparison", resource_id=row.id,
                 actor=actor,
                 summary=f"MRMC 对照：AI AUC {outcome['auc_ai']:.4f} vs 阅片者均值 "
                         f"{outcome['reader_average_auc']:.4f}（p={outcome['p_value']:.3f}）",
                 payload=outcome)
    _report(0.98, "对照完成")
    return {"comparison": row.to_dict(), **outcome}
