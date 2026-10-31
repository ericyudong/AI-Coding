"""作业服务：把业务能力注册进作业引擎，并对外提供提交/查询/取消/重试。

分工：
- `core/tasks.py`  只管调度与生命周期（不懂业务）
- 本模块            只管业务接入（决定 payload 怎么解析、调用哪个领域函数、结果怎么落库）

同时提供**并发度保护**：同一模型版本的训练不允许并行提交（否则两个版本互相污染基线），
同一张切片的特征预计算按 dedup_key 幂等。这类约束是业务语义，只能写在业务侧。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.config import settings
from app.core.tasks import TASKS, JobContext, JobCancelled
from app.models.asset import DataAsset, Slide
from app.models.edge import FederatedJob
from app.models.evaluation import EvalRun
from app.models.job import JOB_STATUSES, JOB_TYPES, AsyncJob, AsyncJobEvent
from app.models.label import Annotation, QcRecord
from app.models.modeling import ModelBase, ModelVersion
from app.models.system import User

logger = logging.getLogger("smarthealth.jobs")


# ==================================================================== payload 解析
def _payload(ctx: JobContext) -> dict[str, Any]:
    return ctx.payload or {}


def _require(payload: dict[str, Any], key: str) -> Any:
    value = payload.get(key)
    if value in (None, "", []):
        raise ValueError(f"作业参数缺少必填项：{key}")
    return value


def _slide_ids(payload: dict[str, Any]) -> list[int]:
    ids = payload.get("slide_ids") or []
    if ids:
        return [int(i) for i in ids]
    return []


def _slides_by_ids(db: Session, ids: list[int]) -> list[Slide]:
    if not ids:
        return []
    rows = list(db.execute(select(Slide).where(Slide.id.in_(ids))).scalars())
    order = {sid: i for i, sid in enumerate(ids)}
    rows.sort(key=lambda s: order.get(s.id, 1 << 30))
    return rows


# ==================================================================== Handler 实现
def _h_feature_precompute(ctx: JobContext) -> dict[str, Any]:
    from app.services.pipeline_service import DEFAULT_BAG_CONFIG, precompute_slide_feature

    payload = _payload(ctx)
    slide_ids = _slide_ids(payload)
    encoder_code = str(payload.get("encoder_code") or settings.default_encoder)
    force = bool(payload.get("force", False))

    with ctx.db() as db:
        slide = db.get(Slide, int(_require(payload, "slide_id"))) if not slide_ids else None
        targets = [slide] if slide is not None else _slides_by_ids(db, slide_ids)
        if not targets or any(t is None for t in targets):
            raise ValueError("切片不存在，请提供 slide_id 或 slide_ids")

        total = len(targets)
        results = []
        for index, target in enumerate(targets):
            ctx.check_cancel()
            ctx.progress(0.02 + 0.96 * (index / max(total, 1)),
                         f"特征预计算 {index + 1}/{total}（切片 {target.code}）")
            try:
                feature = precompute_slide_feature(
                    db, target, encoder_code, DEFAULT_BAG_CONFIG,
                    deployment_env=payload.get("deployment_env"),
                    force=force,
                    progress_cb=lambda pct, stage, _base=index / max(total, 1), _t=total: ctx.progress(
                        _base + (0.96 / _t) * pct, f"{stage}（{index + 1}/{total}）"),
                    cancel_cb=ctx.check_cancel,
                )
            except JobCancelled:
                raise
            except Exception as exc:
                logger.warning("切片 %s 特征预计算失败：%s", target.code, exc)
                results.append({"slide_code": target.code, "ok": False, "error": str(exc)})
                continue
            results.append({"slide_code": target.code, "ok": True,
                            "tile_count": feature.tile_count,
                            "embedding_dim": feature.embedding_dim,
                            "feature_path": feature.feature_path,
                            "elapsed_ms": feature.elapsed_ms})
        ok_count = sum(1 for r in results if r.get("ok"))
        ctx.log(f"特征预计算完成：成功 {ok_count} / 共 {total}（编码器 {encoder_code}）")
        record_audit(db, action="precompute_feature", resource_type="slide",
                     resource_id=targets[0].id if len(targets) == 1 else None,
                     actor=ctx.payload.get("_actor", "") or "system",
                     summary=f"特征预计算作业完成：{ok_count}/{total} 张切片（编码器 {encoder_code}）",
                     payload={"results": results[:200]})
        return {"encoder_code": encoder_code, "total": total, "ok_count": ok_count,
                "failed_count": total - ok_count, "items": results}


def _h_train(ctx: JobContext) -> dict[str, Any]:
    from app.services.pipeline_service import train_mil_model

    payload = _payload(ctx)
    with ctx.db() as db:
        base = None
        base_id = payload.get("base_id")
        base_code = payload.get("base_code")
        if base_id:
            base = db.get(ModelBase, int(base_id))
        elif base_code:
            base = db.execute(select(ModelBase).where(ModelBase.code == str(base_code))).scalar_one_or_none()
        if base is None:
            base = db.execute(select(ModelBase).order_by(ModelBase.id.asc()).limit(1)).scalar_one_or_none()
        if base is None:
            raise ValueError("没有可用的模型基座（ModelBase）")

        encoder_code = str(payload.get("encoder_code") or base.default_encoder_code or settings.default_encoder)
        task_code = str(payload.get("task_code") or "lymph_node_metastasis")

        train_ids = [int(i) for i in (payload.get("train_slide_ids") or [])]
        val_ids = [int(i) for i in (payload.get("val_slide_ids") or [])]
        if train_ids:
            train_slides = [(s, 1.0 if s.has_lesion else 0.0) for s in _slides_by_ids(db, train_ids)]
            val_slides = [(s, 1.0 if s.has_lesion else 0.0) for s in _slides_by_ids(db, val_ids)]
        else:
            # 未指定则按 split 字段自动划分（生产上应由数据版本固定，此处提供合理默认）
            rows = list(db.execute(
                select(Slide).where(Slide.staining.like("%H&E%")).order_by(Slide.id.asc())
            ).scalars())
            train_slides = [(s, 1.0 if s.has_lesion else 0.0) for s in rows if s.split == "train"]
            val_slides = [(s, 1.0 if s.has_lesion else 0.0) for s in rows if s.split in ("val", "valid")]
            if not val_slides and train_slides:
                cut = max(4, int(len(train_slides) * 0.2))
                val_slides, train_slides = train_slides[-cut:], train_slides[:-cut]
        if not train_slides:
            raise ValueError("训练集为空：请先导入切片并指定 split=train，或显式传 train_slide_ids")

        ctx.progress(0.01, f"训练准备：训练 {len(train_slides)} 张 / 验证 {len(val_slides)} 张")
        result = train_mil_model(
            db, base=base, encoder_code=encoder_code, task_code=task_code,
            train_slides=train_slides, val_slides=val_slides,
            semver=str(payload.get("semver") or ""),
            deployment_env=payload.get("deployment_env"),
            triggered_by=payload.get("_actor", "") or "",
            progress_cb=ctx.progress, cancel_cb=ctx.check_cancel,
        )
        version = result["version"]
        job_row = result["job"]
        ctx.log(f"训练完成：产出模型版本 {version.semver}（AUROC "
                f"{(result.get('metrics', {}).get('validation', {}) or {}).get('auroc', 0):.4f}）")
        return {
            "model_version_id": version.id,
            "semver": version.semver,
            "training_job_id": job_row.id,
            "training_job_code": job_row.code,
            "metrics": result.get("metrics", {}),
        }


def _h_inference(ctx: JobContext) -> dict[str, Any]:
    from app.services.pipeline_service import run_inference

    payload = _payload(ctx)
    with ctx.db() as db:
        version = None
        if payload.get("model_version_id"):
            version = db.get(ModelVersion, int(payload["model_version_id"]))
        if version is None:
            version = db.execute(
                select(ModelVersion).where(ModelVersion.is_registration_candidate.is_(True))
                .order_by(ModelVersion.id.desc()).limit(1)
            ).scalar_one_or_none() or db.execute(
                select(ModelVersion).order_by(ModelVersion.id.desc()).limit(1)
            ).scalar_one_or_none()
        if version is None:
            raise ValueError("没有可用的模型版本，请先执行训练")

        slides = _slides_by_ids(db, _slide_ids(payload))
        if not slides:
            split = str(payload.get("split") or "")
            stmt = select(Slide).order_by(Slide.id.asc())
            if split:
                stmt = stmt.where(Slide.split == split)
            limit = int(payload.get("limit") or 0)
            if limit:
                stmt = stmt.limit(limit)
            slides = list(db.execute(stmt).scalars())
        if not slides:
            raise ValueError("没有需要推理的切片")

        ctx.progress(0.01, f"批量推理准备：{len(slides)} 张切片")
        outcome = run_inference(
            db, slides=slides, model_version=version,
            task_code=str(payload.get("task_code") or "lymph_node_metastasis"),
            threshold=float(payload.get("threshold") or 0.5),
            job_kind=str(payload.get("job_kind") or "batch"),
            deployment_env=payload.get("deployment_env"),
            triggered_by=payload.get("_actor", "") or "",
            name=str(payload.get("name") or ""),
            progress_cb=ctx.progress, cancel_cb=ctx.check_cancel,
        )
        job_row = outcome["job"]
        ctx.log(f"推理完成：成功 {job_row.finished_count} / 失败 {job_row.failed_count}")
        return {
            "inference_job_id": job_row.id,
            "inference_job_code": job_row.code,
            "model_version_id": version.id,
            "summary": outcome.get("summary", {}),
            "finished_count": job_row.finished_count,
            "failed_count": job_row.failed_count,
        }


def _h_evaluate(ctx: JobContext) -> dict[str, Any]:
    from app.services.experiment_service import execute_eval_run

    payload = _payload(ctx)
    with ctx.db() as db:
        outcome = execute_eval_run(
            db,
            dataset_id=int(_require(payload, "dataset_id")),
            model_version_id=payload.get("model_version_id"),
            threshold=float(payload.get("threshold") or 0.5),
            bootstrap_rounds=int(payload.get("bootstrap_rounds") or 300),
            allow_missing=bool(payload.get("allow_missing")),
            actor=payload.get("_actor", "") or "",
            progress_cb=ctx.progress,
        )
        run = outcome["run"]
        ctx.log(f"评测完成：AUROC {run['auroc']:.4f}（{run['code']}）")
        return {
            "eval_run_id": run["id"], "eval_run_code": run["code"],
            "auroc": run["auroc"], "sensitivity": run["sensitivity"],
            "specificity": run["specificity"], "ece": run["ece"],
            "generalization": outcome.get("generalization", {}),
        }


def _h_mrmc(ctx: JobContext) -> dict[str, Any]:
    from app.services.experiment_service import execute_mrmc_run

    payload = _payload(ctx)
    with ctx.db() as db:
        outcome = execute_mrmc_run(
            db,
            dataset_id=int(_require(payload, "dataset_id")),
            model_version_id=payload.get("model_version_id"),
            reader_a_name=str(payload.get("reader_a_name") or "阅片者 A"),
            reader_a_title=str(payload.get("reader_a_title") or ""),
            reader_b_name=str(payload.get("reader_b_name") or "阅片者 B"),
            reader_b_title=str(payload.get("reader_b_title") or ""),
            positive_label=str(payload.get("positive_label") or "转移阳性"),
            bootstrap_rounds=int(payload.get("bootstrap_rounds") or 300),
            actor=payload.get("_actor", "") or "",
            progress_cb=ctx.progress,
        )
        ctx.log(f"MRMC 对照完成：AI {outcome['auc_ai']:.4f} vs 阅片者 "
                f"{outcome['reader_average_auc']:.4f}（p={outcome['p_value']:.3f}）")
        return {"mrmc_id": outcome["comparison"]["id"], **{
            k: outcome[k] for k in ("auc_ai", "reader_average_auc", "delta_ai_vs_reader_a",
                                    "p_value", "conclusion")}}


def _h_federated(ctx: JobContext) -> dict[str, Any]:
    from app.services.edge_service import run_federated_job

    payload = _payload(ctx)
    with ctx.db() as db:
        job_row = db.get(FederatedJob, int(_require(payload, "federated_job_id")))
        if job_row is None:
            raise ValueError("联邦任务不存在")
        base_version = db.get(ModelVersion, job_row.base_version_id) if job_row.base_version_id else None
        if base_version is None:
            raise ValueError("联邦任务缺少基础模型版本")
        outcome = run_federated_job(
            db, job=job_row, base_version=base_version,
            encoder_code=str(payload.get("encoder_code") or base_version.encoder_code
                             or settings.default_encoder),
            rounds=payload.get("rounds"), local_epochs=payload.get("local_epochs"),
            deployment_env=payload.get("deployment_env"),
            triggered_by=payload.get("_actor", "") or "",
            progress_cb=ctx.progress, cancel_cb=ctx.check_cancel,
        )
        ctx.log(f"联邦任务完成：{job_row.global_metric_init:.4f} → {job_row.global_metric_final:.4f}")
        return {"federated_job_id": job_row.id,
                "global_metric_init": job_row.global_metric_init,
                "global_metric_final": job_row.global_metric_final,
                **(outcome if isinstance(outcome, dict) else {})}


def _h_import_slides(ctx: JobContext) -> dict[str, Any]:
    """批量导入切片元数据（CSV / JSON 行）。逐行校验、错误行回报、编码去重。"""
    payload = _payload(ctx)
    rows = payload.get("rows") or []
    if not isinstance(rows, list) or not rows:
        raise ValueError("导入内容为空")
    asset_id = payload.get("asset_id")
    default_site = str(payload.get("site_code") or "")
    default_split = str(payload.get("split") or "train")

    created, skipped, errors = 0, 0, []
    total = len(rows)
    with ctx.db() as db:
        asset = db.get(DataAsset, int(asset_id)) if asset_id else None
        existing_codes = {c for (c,) in db.execute(select(Slide.code)).all()}
        new_slides: list[Slide] = []
        for index, raw in enumerate(rows, start=1):
            ctx.check_cancel()
            ctx.progress(0.02 + 0.9 * (index / total), f"导入 {index}/{total}")
            if not isinstance(raw, dict):
                errors.append({"row": index, "error": "行格式错误（应为对象）"})
                continue
            code = str(raw.get("code") or raw.get("切片编号") or "").strip()
            if not code:
                errors.append({"row": index, "error": "缺少切片编号 code"})
                continue
            if code in existing_codes:
                skipped += 1
                continue
            try:
                mpp = float(raw.get("mpp") or 0.5)
            except (TypeError, ValueError):
                errors.append({"row": index, "error": f"mpp 非法：{raw.get('mpp')!r}"})
                continue
            staining = str(raw.get("staining") or "H&E")
            has_lesion_raw = raw.get("has_lesion")
            if isinstance(has_lesion_raw, str):
                has_lesion = has_lesion_raw.strip().lower() in ("1", "true", "yes", "是", "阳性")
            else:
                has_lesion = bool(has_lesion_raw)

            slide = Slide(
                code=code,
                asset_id=asset.id if asset else None,
                case_no=str(raw.get("case_no") or ""),
                patient_pseudo_id=str(raw.get("patient_pseudo_id") or ""),
                organ=str(raw.get("organ") or ""),
                cancer_type=str(raw.get("cancer_type") or ""),
                staining=staining,
                diagnosis_text=str(raw.get("diagnosis_text") or ""),
                icd_o_3=str(raw.get("icd_o_3") or ""),
                magnification=str(raw.get("magnification") or "20X"),
                mpp=mpp,
                scanner=str(raw.get("scanner") or ""),
                file_path=str(raw.get("file_path") or ""),
                split=str(raw.get("split") or default_split),
                site_code=str(raw.get("site_code") or default_site),
                has_lesion=has_lesion,
                status="registered",
            )
            db.add(slide)
            existing_codes.add(code)
            new_slides.append(slide)
            created += 1
        db.flush()

        # 可选：导入后自动排队特征预计算
        precompute_ids = []
        if payload.get("enqueue_precompute"):
            precompute_ids = [s.id for s in new_slides]
        if asset is not None:
            asset.slide_count = int(db.execute(
                select(func.count(Slide.id)).where(Slide.asset_id == asset.id)
            ).scalar() or 0)
        record_audit(db, action="import_slides", resource_type="slide",
                     actor=payload.get("_actor", "") or "system",
                     summary=f"批量导入切片：新增 {created}、跳过（已存在）{skipped}、错误 {len(errors)}",
                     payload={"asset_id": asset_id, "errors": errors[:50]})
        ctx.log(f"导入完成：新增 {created}、跳过 {skipped}、错误 {len(errors)}")
    return {"created": created, "skipped": skipped, "error_count": len(errors),
            "errors": errors[:100], "slide_ids": precompute_ids[:2000]}


def _h_qc_recompute(ctx: JobContext) -> dict[str, Any]:
    """重算标注一致性，并把结果落为质控记录（可追溯的质控运行痕迹）。"""
    from app.services.label_service import consistency_report, coverage_report

    payload = _payload(ctx)
    with ctx.db() as db:
        ctx.progress(0.2, "重算四层标签覆盖率")
        coverage = coverage_report(db)
        ctx.progress(0.5, "重算标注一致性（Cohen / Fleiss kappa）")
        consistency = consistency_report(db)

        ctx.progress(0.8, "写入质控记录")
        now = datetime.now().isoformat(timespec="seconds")
        reviewer = payload.get("_actor", "") or "system"
        written = 0
        for item in consistency.get("by_schema", []) or []:
            kappa = item.get("kappa")
            if kappa is None:
                continue
            passed = float(kappa) >= 0.75
            db.add(QcRecord(
                slide_code="", qc_type="consistency_audit",
                reviewer_name=reviewer,
                result="pass" if passed else "fail",
                score=float(kappa),
                defect_types_json=json.dumps(
                    [] if passed else ["标注一致性低于 0.75"], ensure_ascii=False),
                rework_required=not passed,
                reviewed_at=now,
                note=f"标签 {item.get('schema_code')} 一致性重算（kappa={kappa}）",
            ))
            written += 1
        record_audit(db, action="qc_recompute", resource_type="qc_record", actor=reviewer,
                     summary=f"标注一致性重算完成：写入 {written} 条质控记录",
                     payload={"coverage_note": coverage.get("note"),
                              "consistency_note": consistency.get("note")})
        ctx.log(f"一致性重算完成：写入 {written} 条质控记录")
        return {"qc_written": written,
                "registration_ready": coverage.get("registration_ready"),
                "registration_gap_count": len(coverage.get("registration_gaps") or []),
                "consistency_note": consistency.get("note")}


def _h_explainability(ctx: JobContext) -> dict[str, Any]:
    from app.services.compliance_service import build_explainability_package
    from app.services.experiment_service import resolve_model_version

    payload = _payload(ctx)
    with ctx.db() as db:
        ctx.progress(0.3, "收集注意力热区与形态学统计量")
        version = resolve_model_version(db, payload.get("model_version_id"))
        ctx.progress(0.7, "生成可解释性材料")
        package = build_explainability_package(db, version, created_by=payload.get("_actor", "") or "")
        ctx.log(f"可解释性材料已重建：模型版本 {version.semver}")
        return {"package_id": package.id, "model_version_id": version.id,
                "model_version_label": version.semver}


def _h_boundary_check(ctx: JobContext) -> dict[str, Any]:
    from app.services.compliance_service import run_boundary_check

    payload = _payload(ctx)
    with ctx.db() as db:
        ctx.progress(0.5, "校验数据边界（出域扫描）")
        record = run_boundary_check(db, checked_by=payload.get("_actor", "") or "system")
        ctx.log(f"数据不出域校验完成：passed={record.passed}")
        return {"boundary_check_id": record.id, "passed": record.passed,
                "violations": json.loads(record.violations_json or "[]")}


# ==================================================================== 注册
_HANDLERS = {
    "feature_precompute": (_h_feature_precompute, 1800, 2),
    "train": (_h_train, 0, 1),                 # 训练不设硬超时；失败不自动重试（避免污染基线）
    "inference": (_h_inference, 3600, 2),
    "evaluate": (_h_evaluate, 1800, 2),
    "mrmc": (_h_mrmc, 1800, 2),
    "federated": (_h_federated, 0, 1),
    "import_slides": (_h_import_slides, 1800, 1),
    "qc_recompute": (_h_qc_recompute, 900, 1),
    "explainability": (_h_explainability, 900, 2),
    "boundary_check": (_h_boundary_check, 600, 2),
}


def register_handlers() -> None:
    for job_type, (handler, timeout, attempts) in _HANDLERS.items():
        TASKS.register(job_type, handler, default_timeout=timeout,
                       default_max_attempts=attempts,
                       description=JOB_TYPES.get(job_type, job_type))


register_handlers()


# ==================================================================== 业务侧并发保护
class BusyError(RuntimeError):
    """存在冲突的在跑作业。"""


def _assert_no_conflict(db: Session, job_type: str, conflict_filter, message: str) -> None:
    existing = db.execute(
        select(AsyncJob).where(
            AsyncJob.job_type == job_type,
            AsyncJob.status.in_(("queued", "running")),
            conflict_filter,
        ).limit(1)
    ).scalar_one_or_none()
    if existing is not None:
        raise BusyError(f"{message}（已在执行的作业：{existing.code} {existing.status_label}）")


def submit_precompute(db: Session, *, slide_ids: list[int], encoder_code: str = "",
                      force: bool = False, actor: str = "", actor_name: str = "",
                      org_code: str = "", site_code: str = "") -> AsyncJob:
    if not slide_ids:
        raise ValueError("必须提供至少一张切片")
    ctx_actor = _actor_payload(actor)
    slide_code = ""
    if len(slide_ids) == 1:
        row = db.get(Slide, slide_ids[0])
        if row is None:
            raise ValueError(f"切片 #{slide_ids[0]} 不存在")
        slide_code = row.code
    title = (f"特征预计算 · {slide_code}（{encoder_code or settings.default_encoder}）"
             if slide_code else f"特征预计算 · {len(slide_ids)} 张切片")
    # 幂等键按「是否强制重算」分流：force 与 force 之间也要去重，
    # 否则用户连点两次「重新提取特征」会排出两个同样的作业，
    # 既浪费算力，也会让后一个覆盖前一个刚写好的特征包。
    key_suffix = "force" if force else "reuse"
    dedup_key = (f"precompute:{key_suffix}:"
                 f"{','.join(str(i) for i in sorted(slide_ids))}:"
                 f"{encoder_code or settings.default_encoder}")
    return TASKS.submit(
        db, job_type="feature_precompute", title=title, priority=20,
        payload={"slide_ids": slide_ids, "encoder_code": encoder_code, "force": force, **ctx_actor},
        dedup_key=dedup_key,
        ref_type="slide", ref_id=slide_ids[0] if len(slide_ids) == 1 else None,
        ref_label=slide_code, created_by=actor, created_by_name=actor_name,
        org_code=org_code, site_code=site_code,
    )


def submit_train(db: Session, *, payload: dict[str, Any], actor: str = "", actor_name: str = "",
                 org_code: str = "") -> AsyncJob:
    _assert_no_conflict(
        db, "train",
        AsyncJob.payload_json.like(f'%"task_code": "{payload.get("task_code") or "lymph_node_metastasis"}"%'),
        "同一任务的训练正在执行中，请等待其结束再提交（避免两个版本互相污染基线）",
    )
    return TASKS.submit(
        db, job_type="train",
        title=f"模型训练 · {payload.get('task_code') or 'lymph_node_metastasis'}"
              f"（编码器 {payload.get('encoder_code') or settings.default_encoder}）",
        priority=60, payload={**payload, **_actor_payload(actor)},
        ref_type="model_base", ref_id=payload.get("base_id"),
        created_by=actor, created_by_name=actor_name, org_code=org_code,
    )


def submit_inference(db: Session, *, payload: dict[str, Any], actor: str = "", actor_name: str = "",
                     org_code: str = "", site_code: str = "") -> AsyncJob:
    count = len(payload.get("slide_ids") or [])
    return TASKS.submit(
        db, job_type="inference",
        title=(f"批量推理 · {count} 张切片" if count else
               f"批量推理 · {'split=' + payload['split'] if payload.get('split') else '全部切片'}"),
        priority=40, payload={**payload, **_actor_payload(actor)},
        created_by=actor, created_by_name=actor_name, org_code=org_code, site_code=site_code,
    )


def submit_eval(db: Session, *, dataset_id: int, model_version_id: int | None = None,
                threshold: float = 0.5, bootstrap_rounds: int = 300, allow_missing: bool = False,
                actor: str = "", actor_name: str = "") -> AsyncJob:
    return TASKS.submit(
        db, job_type="evaluate", title=f"评测运行 · 数据集 #{dataset_id}",
        priority=45,
        payload={"dataset_id": dataset_id, "model_version_id": model_version_id,
                 "threshold": threshold, "bootstrap_rounds": bootstrap_rounds,
                 "allow_missing": allow_missing, **_actor_payload(actor)},
        dedup_key=f"evaluate:{dataset_id}:{model_version_id or 'latest'}",
        ref_type="eval_dataset", ref_id=dataset_id,
        created_by=actor, created_by_name=actor_name,
    )


def submit_mrmc(db: Session, *, payload: dict[str, Any], actor: str = "",
                actor_name: str = "") -> AsyncJob:
    return TASKS.submit(
        db, job_type="mrmc", title=f"MRMC 对照 · 数据集 #{payload.get('dataset_id')}",
        priority=55, payload={**payload, **_actor_payload(actor)},
        ref_type="eval_dataset", ref_id=payload.get("dataset_id"),
        created_by=actor, created_by_name=actor_name,
    )


def submit_federated(db: Session, *, federated_job_id: int, actor: str = "",
                     actor_name: str = "", **extra: Any) -> AsyncJob:
    return TASKS.submit(
        db, job_type="federated", title=f"联邦式增量微调 · 任务 #{federated_job_id}",
        priority=65,
        payload={"federated_job_id": federated_job_id, **extra, **_actor_payload(actor)},
        ref_type="federated_job", ref_id=federated_job_id,
        created_by=actor, created_by_name=actor_name,
    )


def submit_import_slides(db: Session, *, rows: list[dict], asset_id: int | None = None,
                         site_code: str = "", split: str = "train",
                         enqueue_precompute: bool = False, actor: str = "",
                         actor_name: str = "") -> AsyncJob:
    return TASKS.submit(
        db, job_type="import_slides", title=f"切片批量导入 · {len(rows)} 行",
        priority=30,
        payload={"rows": rows, "asset_id": asset_id, "site_code": site_code, "split": split,
                 "enqueue_precompute": enqueue_precompute, **_actor_payload(actor)},
        ref_type="asset", ref_id=asset_id,
        created_by=actor, created_by_name=actor_name, site_code=site_code,
    )


def submit_qc_recompute(db: Session, *, actor: str = "", actor_name: str = "") -> AsyncJob:
    return TASKS.submit(
        db, job_type="qc_recompute", title="标注一致性与质控重算", priority=70,
        payload=_actor_payload(actor), created_by=actor, created_by_name=actor_name,
        dedup_key="qc_recompute:daily",
    )


def submit_explainability(db: Session, *, model_version_id: int | None = None,
                          actor: str = "", actor_name: str = "") -> AsyncJob:
    return TASKS.submit(
        db, job_type="explainability", title="可解释性材料重建", priority=50,
        payload={"model_version_id": model_version_id, **_actor_payload(actor)},
        ref_type="model_version", ref_id=model_version_id,
        created_by=actor, created_by_name=actor_name,
    )


def submit_boundary_check(db: Session, *, actor: str = "", actor_name: str = "") -> AsyncJob:
    return TASKS.submit(
        db, job_type="boundary_check", title="数据不出域校验", priority=35,
        payload=_actor_payload(actor), created_by=actor, created_by_name=actor_name,
    )


def _actor_payload(actor: str) -> dict[str, Any]:
    """把操作人透传给 handler（handler 里写审计需要，但 handler 拿不到请求上下文）。"""
    return {"_actor": actor or ""}


# ==================================================================== 查询与控制
def job_detail(db: Session, job_id: int, *, include_events: bool = True,
               include_error_detail: bool = False) -> dict[str, Any]:
    # populate_existing：强制从库里重读。作业状态由其它线程（Worker）修改，
    # 长会话（脚本/测试/批处理）若命中身份映射旧快照，会把「已完成」显示成「排队中」。
    job = db.execute(
        select(AsyncJob).where(AsyncJob.id == job_id).execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if job is None:
        raise ValueError("作业不存在")
    payload: dict[str, Any] = {
        **job.to_dict(exclude=() if include_error_detail else ("error_detail",)),
        "type_label": job.type_label,
        "status_label": job.status_label,
        "is_terminal": job.is_terminal,
        "can_cancel": not job.is_terminal,
        "can_retry": job.is_terminal and job.status != "succeeded",
    }
    for key in ("payload", "result"):
        raw = payload.pop(f"{key}_json", "{}")
        try:
            payload[key] = json.loads(raw or "{}")
        except Exception:
            payload[key] = {}
    if include_events:
        events = list(db.execute(
            select(AsyncJobEvent).where(AsyncJobEvent.job_id == job.id)
            .order_by(AsyncJobEvent.seq.asc()).limit(300)
        ).scalars())
        payload["events"] = [e.to_dict() for e in events]
    return payload


def job_log_tail(db: Session, job_id: int, limit: int = 40) -> list[dict[str, Any]]:
    events = list(db.execute(
        select(AsyncJobEvent).where(AsyncJobEvent.job_id == job_id)
        .order_by(AsyncJobEvent.seq.desc()).limit(limit)
    ).scalars())
    return [e.to_dict() for e in reversed(events)]


def list_jobs(db: Session, *, status: str = "", job_type: str = "", search: str = "",
              created_by: str = "", org_code: str = "", page: int = 1, page_size: int = 20,
              only_active: bool = False) -> tuple[list[AsyncJob], int]:
    stmt = select(AsyncJob)
    conditions = []
    if only_active:
        conditions.append(AsyncJob.status.in_(("queued", "running")))
    if status:
        conditions.append(AsyncJob.status == status)
    if job_type:
        conditions.append(AsyncJob.job_type == job_type)
    if created_by:
        conditions.append(AsyncJob.created_by == created_by)
    if org_code:
        conditions.append(or_(AsyncJob.org_code == org_code, AsyncJob.org_code == "",
                              AsyncJob.created_by == created_by) if created_by
                          else or_(AsyncJob.org_code == org_code, AsyncJob.org_code == ""))
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(or_(AsyncJob.code.like(pattern), AsyncJob.title.like(pattern),
                              AsyncJob.ref_label.like(pattern)))
    if conditions:
        stmt = stmt.where(*conditions)
    total = int(db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0)
    stmt = stmt.order_by(AsyncJob.id.desc()).offset(max(page - 1, 0) * page_size).limit(page_size)
    return list(db.execute(stmt).scalars()), total


def job_stats(db: Session) -> dict[str, Any]:
    rows = db.execute(select(AsyncJob.status, func.count(AsyncJob.id)).group_by(AsyncJob.status)).all()
    by_status = {str(s): int(c) for s, c in rows}
    type_rows = db.execute(
        select(AsyncJob.job_type, func.count(AsyncJob.id)).group_by(AsyncJob.job_type)
    ).all()
    recent_failed = list(db.execute(
        select(AsyncJob).where(AsyncJob.status.in_(("failed", "dead", "timeout")))
        .order_by(AsyncJob.id.desc()).limit(5)
    ).scalars())
    durations = [j.duration_sec for j in db.execute(
        select(AsyncJob).where(AsyncJob.status == "succeeded", AsyncJob.duration_sec > 0)
        .order_by(AsyncJob.id.desc()).limit(50)
    ).scalars()]
    avg_duration = round(sum(durations) / len(durations), 2) if durations else 0.0
    return {
        "by_status": by_status,
        "by_type": {str(t): int(c) for t, c in type_rows},
        "queued": by_status.get("queued", 0),
        "running": by_status.get("running", 0),
        "succeeded": by_status.get("succeeded", 0),
        "failed": by_status.get("failed", 0) + by_status.get("dead", 0),
        "cancelled": by_status.get("cancelled", 0),
        "avg_duration_sec_recent": avg_duration,
        "failure_rate": round(
            (by_status.get("failed", 0) + by_status.get("dead", 0))
            / max(sum(by_status.values()), 1), 4),
        "recent_failures": [{"id": j.id, "code": j.code, "title": j.title,
                             "error": (j.error_text or "")[:200], "status": j.status}
                            for j in recent_failed],
        "engine": TASKS.stats(),
        "type_labels": JOB_TYPES,
        "status_labels": JOB_STATUSES,
    }


def workbench(db: Session, *, actor: str = "", org_code: str = "") -> dict[str, Any]:
    """待办中心：把「需要人处理的事」一屏聚合。

    商用系统的价值不在看板多漂亮，而在「打开就知道今天要干什么」。
    """
    from app.models.agent import ReviewTicket
    from app.models.label import Arbitration

    pending_review = int(db.execute(
        select(func.count(ReviewTicket.id)).where(ReviewTicket.status == "pending")
    ).scalar() or 0)
    my_review = int(db.execute(
        select(func.count(ReviewTicket.id)).where(ReviewTicket.status == "pending",
                                                 ReviewTicket.claimed_by == actor)
    ).scalar() or 0) if actor else 0
    open_arbitration = int(db.execute(
        select(func.count(Arbitration.id)).where(Arbitration.status != "resolved")
    ).scalar() or 0)
    qc_failed = int(db.execute(
        select(func.count(QcRecord.id)).where(QcRecord.result != "pass",
                                              QcRecord.rework_required.is_(True))
    ).scalar() or 0)
    failed_jobs = list(db.execute(
        select(AsyncJob).where(AsyncJob.status.in_(("failed", "dead", "timeout")))
        .order_by(AsyncJob.id.desc()).limit(10)
    ).scalars())
    active_jobs = list(db.execute(
        select(AsyncJob).where(AsyncJob.status.in_(("queued", "running")))
        .order_by(AsyncJob.priority.asc(), AsyncJob.id.asc()).limit(10)
    ).scalars())
    unannotated = int(db.execute(
        select(func.count(Slide.id)).where(Slide.status.in_(("registered", "uploaded")))
    ).scalar() or 0)
    stale_cutoff = (datetime.now() - timedelta(days=90)).isoformat()
    stale_review = int(db.execute(
        select(func.count(ReviewTicket.id)).where(ReviewTicket.status == "pending",
                                                 ReviewTicket.created_at < stale_cutoff)
    ).scalar() or 0) if False else 0

    items = [
        {"key": "pending_review", "label": "待医生终审", "count": pending_review,
         "hint": "AI 结论需由医生确认后才成为最终诊断", "route": "agents"},
        {"key": "my_review", "label": "我已认领的终审", "count": my_review,
         "hint": "继续处理你认领的工单", "route": "agents"},
        {"key": "open_arbitration", "label": "待仲裁标注", "count": open_arbitration,
         "hint": "标注分歧未裁决会阻断训练数据可用性", "route": "labels"},
        {"key": "qc_failed", "label": "需返工的质控", "count": qc_failed,
         "hint": "质控不通过的标注必须返工后才可进入训练集", "route": "labels"},
        {"key": "failed_jobs", "label": "失败作业", "count": len(failed_jobs),
         "hint": "失败作业可一键重试或查看堆栈", "route": "jobs"},
        {"key": "active_jobs", "label": "进行中的作业", "count": len(active_jobs),
         "hint": "训练/推理/评测等长任务的实时进度", "route": "jobs"},
        {"key": "unannotated", "label": "待标注切片", "count": unannotated,
         "hint": "已登记但尚未产生任何标注的切片", "route": "labels"},
    ]
    return {
        "items": items,
        "total_actionable": sum(i["count"] for i in items
                                if i["key"] not in ("active_jobs", "unannotated")),
        "active_jobs": [{"id": j.id, "code": j.code, "title": j.title, "type": j.job_type,
                         "type_label": j.type_label, "status": j.status,
                         "progress": j.progress, "stage_text": j.stage_text} for j in active_jobs],
        "failed_jobs": [{"id": j.id, "code": j.code, "title": j.title, "type": j.job_type,
                         "type_label": j.type_label, "status": j.status,
                         "error": (j.error_text or "")[:300],
                         "attempts": j.attempts, "max_attempts": j.max_attempts} for j in failed_jobs],
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
