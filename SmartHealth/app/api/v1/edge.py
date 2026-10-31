"""云边协同与联邦式增量微调接口（对应设计文档第六章、第十章 R3）。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import select

from app.api.v1.common import crud_router, ok, serialize
from app.api.v1.common import job_brief, want_async
from app.core.config import settings
from app.core.deps import CurrentUser, DbSession, audit, require
from app.models.edge import DeploymentTask, EdgeNode, FederatedJob, FederatedRound
from app.models.modeling import ModelVersion
from app.services import edge_service
from app.services import job_service

router = APIRouter(tags=["09 云边协同"])

router.include_router(crud_router(
    model=EdgeNode, prefix="/edge/nodes", tag="边缘节点", resource_type="edge_node",
    permission_read="edge:read", permission_write="edge:write",
    search_fields=("code", "name", "hospital", "site_code", "region", "gpu_model"),
    filter_fields=("node_type", "deployment_mode", "status", "realtime_inference", "site_code"),
    order_by="id", summary_template="更新边缘节点 {row.code}",
))

router.include_router(crud_router(
    model=FederatedJob, prefix="/edge/federated-jobs", tag="联邦任务", resource_type="federated_job",
    permission_read="edge:read", permission_write="edge:write",
    search_fields=("code", "name", "base_version_label", "note"),
    filter_fields=("status", "strategy"),
    order_by="id", allow_create=False, summary_template="更新联邦任务 {row.code}",
))

router.include_router(crud_router(
    model=FederatedRound, prefix="/edge/federated-rounds", tag="联邦轮次", resource_type="federated_round",
    permission_read="edge:read", permission_write=None,
    search_fields=("aggregated_at",),
    filter_fields=("job_id",),
    json_fields=("participants_json",), order_by="round_no",
))

router.include_router(crud_router(
    model=DeploymentTask, prefix="/edge/deployments", tag="模型下发", resource_type="deployment_task",
    permission_read="edge:read", permission_write=None,
    search_fields=("code", "node_code", "model_version_label", "triggered_by"),
    filter_fields=("status", "action", "node_id"),
    order_by="id",
))


@router.get("/edge/overview", summary="云边协同总览")
def edge_overview(db: DbSession, user: dict = Depends(require("edge:read"))) -> dict:
    return ok(edge_service.edge_overview(db))


@router.get("/edge/federated-jobs/{job_id}/detail", summary="联邦任务详情（含逐轮参与方）")
def federated_detail(job_id: int, db: DbSession,
                     user: dict = Depends(require("edge:read"))) -> dict:
    job = db.get(FederatedJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="联邦任务不存在")
    rounds = list(db.execute(
        select(FederatedRound).where(FederatedRound.job_id == job.id)
        .order_by(FederatedRound.round_no)
    ).scalars())
    sample_domain_violations = 0
    for rnd in rounds:
        for participant in json.loads(rnd.participants_json or "[]"):
            if participant.get("data_left_domain"):
                sample_domain_violations += 1
    return ok({
        **job.to_dict(),
        "rounds": [serialize(r, ("participants_json",)) for r in rounds],
        "metric_series": [
            {"round": r.round_no, "metric": r.global_metric, "loss": r.global_loss,
             "clients": r.client_count, "upload_kb": r.upload_kb}
            for r in rounds
        ],
        "improvement": round(job.global_metric_final - job.global_metric_init, 6),
        "sample_left_domain_count": sample_domain_violations,
        "compliance_note": (
            "「样本出域次数」是本接口最关键的一个数字：它必须恒为 0。"
            "联邦式增量微调只交换模型参数（约 1 MB 量级），"
            "数万张切片的原始影像始终留在各机构本地。"
        ),
    })


@router.post("/edge/federated-jobs", summary="创建联邦式增量微调任务")
def create_federated_job(db: DbSession, payload: dict = Body(...),
                         user: dict = Depends(require("edge:write"))) -> dict:
    code = str(payload.get("code") or "").strip()
    if not code:
        raise HTTPException(status_code=422, detail="任务编码不能为空")
    if db.execute(select(FederatedJob).where(FederatedJob.code == code)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"联邦任务编码 {code} 已存在")

    base_version_id = int(payload.get("base_version_id") or 0)
    base_version = db.get(ModelVersion, base_version_id) if base_version_id else None
    if base_version is None:
        base_version = db.execute(
            select(ModelVersion).order_by(ModelVersion.id.desc()).limit(1)
        ).scalar_one_or_none()
    if base_version is None:
        raise HTTPException(status_code=400, detail="没有可用的基础模型版本")

    job = FederatedJob(
        code=code,
        name=str(payload.get("name") or "跨中心联邦式增量微调"),
        base_version_id=base_version.id,
        base_version_label=base_version.semver or base_version.version_label,
        strategy=str(payload.get("strategy") or "fedavg"),
        target_rounds=int(payload.get("target_rounds") or 4),
        min_clients=int(payload.get("min_clients") or 2),
        local_epochs=int(payload.get("local_epochs") or 1),
        learning_rate=float(payload.get("learning_rate") or 0.001),
        metric_key=str(payload.get("metric_key") or "auroc"),
        status="pending",
        note=str(payload.get("note") or ""),
    )
    db.add(job)
    db.flush()
    audit(db, user, action="create_federated_job", resource_type="federated_job", resource_id=job.id,
          summary=f"创建联邦任务 {code}（策略 {job.strategy}，目标 {job.target_rounds} 轮）",
          payload={"base_version_id": base_version.id})
    db.commit()
    return ok(job.to_dict())


@router.post("/edge/federated-jobs/{job_id}/run", summary="执行联邦式增量微调")
def run_federated(job_id: int, db: DbSession, payload: dict = Body(default={}),
                  user: dict = Depends(require("edge:write"))) -> dict:
    job = db.get(FederatedJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="联邦任务不存在")
    if job.status == "running":
        raise HTTPException(status_code=409, detail="该任务正在运行中")
    base_version = db.get(ModelVersion, job.base_version_id) if job.base_version_id else None
    if base_version is None:
        raise HTTPException(status_code=400, detail="任务缺少基础模型版本")

    encoder_code = str(payload.get("encoder_code") or base_version.encoder_code
                       or settings.default_encoder)

    if want_async(payload):
        job_out = job_service.submit_federated(
            db, federated_job_id=job.id, rounds=payload.get("rounds"),
            local_epochs=payload.get("local_epochs"), encoder_code=encoder_code,
            actor=user.get("username", ""), actor_name=user.get("real_name", ""))
        return ok({"async": True, "job": job_brief(job_out)},
                  message="联邦式增量微调作业已提交，可在任务中心查看逐轮进度")

    try:
        result = edge_service.run_federated_job(
            db, job=job, base_version=base_version, encoder_code=encoder_code,
            rounds=payload.get("rounds"), local_epochs=payload.get("local_epochs"),
            deployment_env=user.get("deployment_env"), triggered_by=user.get("username", ""),
        )
    except ValueError as exc:
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return ok(result)


@router.post("/edge/nodes/{node_id}/deploy", summary="向边缘节点下发/更新/回滚模型")
def deploy(node_id: int, db: DbSession, payload: dict = Body(default={}),
           user: dict = Depends(require("edge:write"))) -> dict:
    node = db.get(EdgeNode, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="边缘节点不存在")
    version_id = int(payload.get("model_version_id") or node.model_version_id or 0)
    version = db.get(ModelVersion, version_id) if version_id else None
    if version is None:
        version = db.execute(
            select(ModelVersion).order_by(ModelVersion.id.desc()).limit(1)
        ).scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=400, detail="没有可下发的模型版本")

    action = str(payload.get("action") or "install")
    if action not in ("install", "update", "rollback"):
        raise HTTPException(status_code=422, detail="action 仅支持 install / update / rollback")
    task = edge_service.deploy_model(db, node, version, action=action,
                                     triggered_by=user.get("username", ""))
    db.commit()
    return ok(task.to_dict())
