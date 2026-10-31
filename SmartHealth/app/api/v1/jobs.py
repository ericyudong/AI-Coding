"""任务中心接口（异步作业的提交、进度、取消、重试、待办聚合）。

设计要点：
- 业务接口不再直接跑长任务，只**提交**作业并立刻返回 202 + 作业句柄；
- 前端凭 `job_id` 轮询进度（`GET /jobs/{id}`），做到「提交后不阻塞、进度可见、可取消」；
- `POST /jobs/{id}/retry` 与 `cancel` 是显式的运维动作，全部写审计链；
- `GET /jobs/workbench` 把「今天要处理的事」聚合为一屏，避免用户在各模块间找待办。
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import select

from app.api.v1.common import ok
from app.core.deps import CurrentUser, DbSession, audit, require
from app.core.tasks import TASKS
from app.models.job import JOB_STATUSES, JOB_TYPES, AsyncJob
from app.services import job_service
from app.services.job_service import BusyError

router = APIRouter(tags=["13 任务中心"])


def _serialize(job: AsyncJob, *, detail: bool = False) -> dict:
    payload = {
        **job.to_dict(),
        "type_label": job.type_label,
        "status_label": job.status_label,
        "is_terminal": job.is_terminal,
        "can_cancel": not job.is_terminal,
        "can_retry": job.is_terminal and job.status != "succeeded",
    }
    if not detail:
        payload.pop("error_detail", None)
    return payload


@router.get("/jobs", summary="作业列表（任务中心主视图）")
def list_jobs(db: DbSession, user: dict = Depends(require("job:read")),
              page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
              status: str = Query(""), job_type: str = Query(""),
              search: str = Query(""), only_active: bool = Query(False),
              mine: bool = Query(False, description="仅看我提交的作业")) -> dict:
    items, total = job_service.list_jobs(
        db, status=status, job_type=job_type, search=search,
        created_by=user.get("username", "") if mine else "",
        org_code=user.get("org_code") or "",
        page=page, page_size=page_size, only_active=only_active,
    )
    return ok({
        "items": [_serialize(j) for j in items],
        "meta": {"total": total, "page": page, "page_size": page_size,
                 "pages": (total + page_size - 1) // page_size},
        "type_options": [{"value": k, "label": v} for k, v in JOB_TYPES.items()],
        "status_options": [{"value": k, "label": v} for k, v in JOB_STATUSES.items()],
    })


@router.get("/jobs/stats", summary="作业统计与引擎状态")
def stats(db: DbSession, user: dict = Depends(require("job:read"))) -> dict:
    return ok(job_service.job_stats(db))


@router.get("/jobs/workbench", summary="待办中心（一屏聚合需要人处理的事）")
def workbench(db: DbSession, user: dict = Depends(require("job:read"))) -> dict:
    return ok(job_service.workbench(db, actor=user.get("username", ""),
                                    org_code=user.get("org_code") or ""))


@router.get("/jobs/types", summary="作业类型与注册的 handler 清单")
def job_types(user: dict = Depends(require("job:read"))) -> dict:
    return ok({
        "types": [{"value": k, "label": v} for k, v in JOB_TYPES.items()],
        "registered": TASKS.registered_types(),
        "engine": TASKS.stats(),
    })


@router.get("/jobs/{job_id}", summary="作业详情（含完整事件流与进度）")
def job_detail(job_id: int, db: DbSession, user: dict = Depends(require("job:read")),
               include_events: bool = Query(True)) -> dict:
    try:
        include_error = bool(user.get("is_admin"))
        return ok(job_service.job_detail(db, job_id, include_events=include_events,
                                         include_error_detail=include_error))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/jobs/{job_id}/progress", summary="轻量进度查询（轮询专用，避免拉全量事件）")
def job_progress(job_id: int, db: DbSession, user: dict = Depends(require("job:read"))) -> dict:
    job = db.get(AsyncJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="作业不存在")
    return ok({
        "id": job.id, "code": job.code, "status": job.status,
        "status_label": job.status_label, "progress": job.progress,
        "stage_text": job.stage_text, "is_terminal": job.is_terminal,
        "can_cancel": not job.is_terminal,
        "can_retry": job.is_terminal and job.status != "succeeded",
        "error_text": job.error_text, "duration_sec": job.duration_sec,
        "attempts": job.attempts, "max_attempts": job.max_attempts,
        "heartbeat_at": job.heartbeat_at,
    })


@router.get("/jobs/{job_id}/log", summary="作业事件流（日志尾部，用于排障）")
def job_log(job_id: int, db: DbSession, user: dict = Depends(require("job:read")),
            limit: int = Query(60, ge=1, le=500)) -> dict:
    if db.get(AsyncJob, job_id) is None:
        raise HTTPException(status_code=404, detail="作业不存在")
    return ok({"items": job_service.job_log_tail(db, job_id, limit)})


@router.post("/jobs/{job_id}/cancel", summary="取消作业（请求式，安全检查点响应）")
def cancel(job_id: int, db: DbSession, user: dict = Depends(require("job:write"))) -> dict:
    try:
        job = TASKS.cancel(db, job_id, actor=user.get("username", ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    audit(db, user, action="cancel_job", resource_type="async_job", resource_id=job.id,
          summary=f"取消作业 {job.code}（{job.title}）",
          payload={"status": job.status}, risk_level="attention")
    db.commit()
    return ok(_serialize(job, detail=True))


@router.post("/jobs/{job_id}/retry", summary="重试失败作业")
def retry(job_id: int, db: DbSession, user: dict = Depends(require("job:write"))) -> dict:
    try:
        job = TASKS.retry(db, job_id, actor=user.get("username", ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    audit(db, user, action="retry_job", resource_type="async_job", resource_id=job.id,
          summary=f"重试作业 {job.code}（{job.title}），第 {job.attempts + 1} 次尝试",
          payload={"attempts": job.attempts}, risk_level="attention")
    db.commit()
    return ok(_serialize(job, detail=True))


@router.post("/jobs/bulk-retry", summary="批量重试失败作业")
def bulk_retry(db: DbSession, payload: dict = Body(default={}),
               user: dict = Depends(require("job:write"))) -> dict:
    ids = [int(i) for i in (payload.get("job_ids") or [])]
    if not ids and payload.get("all_failed"):
        ids = [j.id for j in db.execute(
            select(AsyncJob).where(AsyncJob.status.in_(("failed", "dead", "timeout")))
            .order_by(AsyncJob.id.desc()).limit(50)
        ).scalars()]
    results, errors = [], []
    for job_id in ids:
        try:
            TASKS.retry(db, job_id, actor=user.get("username", ""))
            results.append(job_id)
        except ValueError as exc:
            errors.append({"job_id": job_id, "error": str(exc)})
    audit(db, user, action="bulk_retry_jobs", resource_type="async_job",
          summary=f"批量重试作业：成功 {len(results)} / 失败 {len(errors)}",
          payload={"retried": results, "errors": errors})
    db.commit()
    return ok({"retried": results, "errors": errors})


# ------------------------------------------------------------------ 任务提交入口
@router.post("/jobs/precompute", summary="提交特征预计算作业", status_code=202)
def submit_precompute(db: DbSession, payload: dict = Body(...),
                      user: dict = Depends(require("pipeline:run"))) -> dict:
    slide_ids = [int(i) for i in (payload.get("slide_ids") or [])]
    if payload.get("slide_id"):
        slide_ids.append(int(payload["slide_id"]))
    try:
        job = job_service.submit_precompute(
            db, slide_ids=slide_ids, encoder_code=str(payload.get("encoder_code") or ""),
            force=bool(payload.get("force")),
            actor=user.get("username", ""), actor_name=user.get("real_name", ""),
            org_code=user.get("org_code") or "", site_code=user.get("site_code") or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ok({"async": True, "job": _serialize(job)}, message="作业已提交")


@router.post("/jobs/train", summary="提交训练作业", status_code=202)
def submit_train(db: DbSession, payload: dict = Body(default={}),
                 user: dict = Depends(require("model:train"))) -> dict:
    try:
        job = job_service.submit_train(db, payload=payload, actor=user.get("username", ""),
                                       actor_name=user.get("real_name", ""),
                                       org_code=user.get("org_code") or "")
    except BusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ok({"async": True, "job": _serialize(job)}, message="训练作业已提交，可在任务中心查看进度")


@router.post("/jobs/inference", summary="提交批量推理作业", status_code=202)
def submit_inference(db: DbSession, payload: dict = Body(default={}),
                     user: dict = Depends(require("pipeline:run"))) -> dict:
    job = job_service.submit_inference(
        db, payload=payload, actor=user.get("username", ""),
        actor_name=user.get("real_name", ""),
        org_code=user.get("org_code") or "", site_code=user.get("site_code") or "")
    return ok({"async": True, "job": _serialize(job)}, message="推理作业已提交")


@router.post("/jobs/evaluate", summary="提交评测作业", status_code=202)
def submit_eval(db: DbSession, payload: dict = Body(...),
                user: dict = Depends(require("eval:write"))) -> dict:
    if not payload.get("dataset_id"):
        raise HTTPException(status_code=422, detail="必须提供 dataset_id")
    job = job_service.submit_eval(
        db, dataset_id=int(payload["dataset_id"]),
        model_version_id=payload.get("model_version_id"),
        threshold=float(payload.get("threshold") or 0.5),
        bootstrap_rounds=int(payload.get("bootstrap_rounds") or 300),
        allow_missing=bool(payload.get("allow_missing")),
        actor=user.get("username", ""), actor_name=user.get("real_name", ""))
    return ok({"async": True, "job": _serialize(job)}, message="评测作业已提交")


@router.post("/jobs/mrmc", summary="提交 MRMC 对照作业", status_code=202)
def submit_mrmc(db: DbSession, payload: dict = Body(...),
                user: dict = Depends(require("eval:write"))) -> dict:
    if not payload.get("dataset_id"):
        raise HTTPException(status_code=422, detail="必须提供 dataset_id")
    job = job_service.submit_mrmc(db, payload=payload, actor=user.get("username", ""),
                                  actor_name=user.get("real_name", ""))
    return ok({"async": True, "job": _serialize(job)}, message="MRMC 对照作业已提交")


@router.post("/jobs/federated", summary="提交联邦式增量微调作业", status_code=202)
def submit_federated(db: DbSession, payload: dict = Body(...),
                     user: dict = Depends(require("edge:write"))) -> dict:
    if not payload.get("federated_job_id"):
        raise HTTPException(status_code=422, detail="必须提供 federated_job_id")
    job = job_service.submit_federated(
        db, federated_job_id=int(payload["federated_job_id"]),
        rounds=payload.get("rounds"), local_epochs=payload.get("local_epochs"),
        actor=user.get("username", ""), actor_name=user.get("real_name", ""))
    return ok({"async": True, "job": _serialize(job)}, message="联邦作业已提交")


@router.post("/jobs/import-slides", summary="提交切片批量导入作业", status_code=202)
def submit_import(db: DbSession, payload: dict = Body(...),
                  user: dict = Depends(require("asset:write"))) -> dict:
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise HTTPException(status_code=422, detail="rows 必须是非空数组")
    if len(rows) > 5000:
        raise HTTPException(status_code=422, detail="单次导入上限 5000 行，请分批提交")
    job = job_service.submit_import_slides(
        db, rows=rows, asset_id=payload.get("asset_id"),
        site_code=str(payload.get("site_code") or ""),
        split=str(payload.get("split") or "train"),
        enqueue_precompute=bool(payload.get("enqueue_precompute")),
        actor=user.get("username", ""), actor_name=user.get("real_name", ""))
    return ok({"async": True, "job": _serialize(job)}, message="导入作业已提交")


@router.post("/jobs/qc-recompute", summary="提交标注一致性与质控重算作业", status_code=202)
def submit_qc(db: DbSession, user: dict = Depends(require("label:write"))) -> dict:
    job = job_service.submit_qc_recompute(db, actor=user.get("username", ""),
                                          actor_name=user.get("real_name", ""))
    return ok({"async": True, "job": _serialize(job)}, message="质控重算作业已提交")


@router.post("/jobs/explainability", summary="提交可解释性材料重建作业", status_code=202)
def submit_explainability(db: DbSession, payload: dict = Body(default={}),
                          user: dict = Depends(require("compliance:write"))) -> dict:
    job = job_service.submit_explainability(
        db, model_version_id=payload.get("model_version_id"),
        actor=user.get("username", ""), actor_name=user.get("real_name", ""))
    return ok({"async": True, "job": _serialize(job)}, message="可解释性重建作业已提交")


@router.post("/jobs/boundary-check", summary="提交数据不出域校验作业", status_code=202)
def submit_boundary(db: DbSession, user: dict = Depends(require("compliance:write"))) -> dict:
    job = job_service.submit_boundary_check(db, actor=user.get("username", ""),
                                            actor_name=user.get("real_name", ""))
    return ok({"async": True, "job": _serialize(job)}, message="校验作业已提交")
