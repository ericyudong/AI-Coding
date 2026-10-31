"""模型基座、编码器许可体检与训练任务接口（对应设计文档第四章与第六章）。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import func, select

from app.api.v1.common import crud_router, list_query, ok, serialize
from app.api.v1.common import job_brief, want_async
from app.core.config import settings
from app.core.deps import CurrentUser, DbSession, audit, require
from app.models.modeling import ComputeResource, EncoderRegistry, LoraAdapter, ModelBase, ModelVersion, TrainingJob
from app.services.encoder_service import LicenseViolation, encoder_service
from app.services.pipeline_service import TASK_DEFINITIONS, TIER_TASKS
from app.services import job_service

router = APIRouter(tags=["04 模型与算力"])

router.include_router(crud_router(
    model=ModelBase, prefix="/models/bases", tag="模型基座", resource_type="model_base",
    permission_read="model:read", permission_write="model:write",
    search_fields=("code", "name", "description", "owner_name"),
    filter_fields=("track", "current_stage", "status"),
    json_fields=("cancer_types_json", "task_scope_json"), order_by="id",
))

router.include_router(crud_router(
    model=ModelVersion, prefix="/models/versions", tag="模型版本", resource_type="model_version",
    permission_read="model:read", permission_write="model:write",
    search_fields=("semver", "name", "encoder_code", "changelog"),
    filter_fields=("base_id", "status", "locked", "is_registration_candidate", "encoder_code"),
    json_fields=("mil_config_json", "metrics_json"), order_by="id",
))

router.include_router(crud_router(
    model=TrainingJob, prefix="/models/training-jobs", tag="训练任务", resource_type="training_job",
    permission_read="model:read", permission_write="model:write",
    search_fields=("code", "encoder_code", "triggered_by", "log_tail"),
    filter_fields=("job_type", "status", "stage", "license_env", "encoder_code"),
    json_fields=("dataset_ids_json", "params_json", "metrics_json"), order_by="id",
))

router.include_router(crud_router(
    model=ComputeResource, prefix="/models/compute", tag="算力资源", resource_type="compute_resource",
    permission_read="model:read", permission_write="model:write",
    search_fields=("code", "name", "gpu_model", "vendor", "location"),
    filter_fields=("resource_type", "status", "is_gateway"), order_by="id",
))

router.include_router(crud_router(
    model=LoraAdapter, prefix="/models/lora-adapters", tag="LoRA 适配器", resource_type="lora_adapter",
    permission_read="model:read", permission_write="model:write",
    search_fields=("code", "name", "target_encoder_code"),
    filter_fields=("status", "target_encoder_code"), order_by="id",
))


# ------------------------------------------------------------------ 编码器
@router.get("/models/encoders", summary="图块编码器注册表（含许可证）")
def list_encoders(db: DbSession, user: dict = Depends(require("model:read")),
                  search: str = Query(""), commercial_usable: str = Query(""),
                  family: str = Query("")) -> dict:
    rows = list(db.execute(select(EncoderRegistry).order_by(EncoderRegistry.sort_order.asc())).scalars())
    if search:
        needle = search.lower()
        rows = [r for r in rows
                if needle in (r.code or "").lower() or needle in (r.name or "").lower()
                or needle in (r.family or "").lower()]
    if commercial_usable not in ("", None):
        want = commercial_usable.lower() in ("1", "true", "yes")
        rows = [r for r in rows if bool(r.commercial_usable) is want]
    if family:
        rows = [r for r in rows if (r.family or "") == family]
    return ok({"items": [r.to_dict() for r in rows], "total": len(rows)})


# ------------------------------------------------------------------ 模型权重仓库
@router.get("/models/registry", summary="模型权重清单（许可/安装状态/校验和）")
def model_registry_overview(db: DbSession,
                            user: dict = Depends(require("model:read"))) -> dict:
    """权重治理视图：每个权重的许可、是否已安装、SHA256、装载阶段。

    注册申报会问「模型基于什么权重」，这个接口就是那个问题的答案来源。
    """
    from app.services import model_registry

    return ok(model_registry.registry_overview())


@router.post("/models/registry/sync", summary="把清单里已安装的权重接入编码器注册表")
def model_registry_sync(db: DbSession,
                        user: dict = Depends(require("model:write"))) -> dict:
    """装完权重后调一次即可生效，无需重启服务。"""
    from app.services.encoder_service import encoder_service

    result = encoder_service.sync_from_registry(verbose=True)
    audit(db, user, action="sync_model_registry", resource_type="model_registry",
          summary=f"同步已安装权重 {result.get('synced', 0)} 个："
                  f"{', '.join(result.get('synced_codes', [])[:5])}")
    db.commit()
    return ok(result)


@router.post("/models/registry/{code}/verify",
             summary="校验指定权重（文件/校验和/ONNX 结构/维度）")
def model_registry_verify(code: str, db: DbSession,
                          user: dict = Depends(require("model:read"))) -> dict:
    from app.services import model_registry

    return ok(model_registry.verify_entry(code))


@router.get("/models/onnx-diagnostics",
            summary="ONNX 编码器诊断（是否真在跑真实权重）")
def onnx_diagnostics(db: DbSession, user: dict = Depends(require("model:read"))) -> dict:
    """区分「真实权重推理」与「内置占位实现」—— 这两者的指标不可比。"""
    from app.services.encoder_service import encoder_service

    return ok(encoder_service.onnx_diagnostics())


@router.get("/models/runtime-capabilities", summary="推理与读取运行时能力自述")
def runtime_capabilities(db: DbSession, user: dict = Depends(require("model:read"))) -> dict:
    """当前环境到底能做什么：ONNX 运行时、WSI 读取后端、图像编解码、DB 领取策略。"""
    import importlib.util

    from app.services.onnx_encoder import NORMALIZATION_PRESETS
    from app.services.wsi_readers import backend_capabilities

    def has(name: str) -> bool:
        try:
            return importlib.util.find_spec(name) is not None
        except Exception:
            return False

    try:
        import onnxruntime as ort

        providers = list(ort.get_available_providers())
    except Exception:
        providers = []

    return ok({
        "onnx": {"onnxruntime": has("onnxruntime"), "onnx": has("onnx"),
                 "providers": providers,
                 "normalization_presets": list(NORMALIZATION_PRESETS)},
        "wsi_readers": backend_capabilities(),
        "image": {"pillow": has("PIL"), "tifffile": has("tifffile"),
                  "imagecodecs": has("imagecodecs"), "openslide": has("openslide")},
        "database": {"backend": settings.db_backend,
                     "job_claim": ("FOR UPDATE SKIP LOCKED"
                                   if settings.db_backend == "postgresql"
                                   else "optimistic update")},
        "note": ("onnxruntime 或 tifffile/openslide 缺失时相关能力会降级；"
                 "运行 python scripts/doctor.py 查看完整预检。"),
    })


@router.get("/models/encoders/license-audit", summary="许可风险体检（双源并行策略的核查入口）")
def license_audit(user: dict = Depends(require("model:read")),
                  deployment_env: str = Query("", description="不传则取当前部署环境")) -> dict:
    return ok(encoder_service.license_audit(deployment_env or None))


@router.post("/models/encoders/license-check", summary="模拟许可门禁：某环境下能否调用该编码器")
def license_check(payload: dict = Body(...),
                  user: dict = Depends(require("model:read"))) -> dict:
    code = str(payload.get("encoder_code") or "").strip()
    env = str(payload.get("deployment_env") or "product")
    if not code:
        raise HTTPException(status_code=422, detail="必须提供 encoder_code")
    spec = encoder_service.get_spec(code)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"未注册的编码器：{code}")
    try:
        encoder_service.assert_commercial_usable(code, deployment_env=env)
        allowed, reason = True, "许可校验通过"
    except LicenseViolation as exc:
        allowed, reason = False, str(exc)
    return ok({
        "encoder_code": code,
        "encoder_name": spec.name,
        "license_name": spec.license_name,
        "commercial_usable": spec.commercial_usable,
        "deployment_env": env,
        "allowed": allowed,
        "reason": reason,
        "is_self_developed": spec.is_self_developed,
        "advice": (
            "该编码器在商用产品环境可用。"
            if allowed else
            "该编码器仅可用于 research 环境。商用主线请改用可商用许可编码器"
            "（Hibou 系列）或自研编码器（sh-encoder-*），以彻底消除许可风险。"
        ),
    })


@router.post("/models/encoders", summary="注册/更新编码器（须如实填写许可证字段）")
def upsert_encoder(db: DbSession, payload: dict = Body(...),
                   user: dict = Depends(require("model:write"))) -> dict:
    try:
        spec = encoder_service.upsert_from_dict(payload)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"编码器注册失败：{exc}") from exc
    row = db.execute(select(EncoderRegistry).where(EncoderRegistry.code == spec.code)).scalar_one_or_none()
    data = spec.to_dict()
    if row is None:
        row = EncoderRegistry(**data)
        db.add(row)
    else:
        row.update_from(data)
    db.flush()
    audit(db, user, action="upsert_encoder", resource_type="encoder", resource_id=row.id,
          summary=f"登记编码器 {spec.code}（许可 {spec.license_name}，可商用 {spec.commercial_usable}）",
          payload=data, risk_level="attention" if not spec.commercial_usable else "normal")
    db.commit()
    return ok(row.to_dict())


# ------------------------------------------------------------------ 训练
@router.post("/models/train", summary="发起训练（Stage B/C：继续预训练 + 监督微调 + 切片级聚合）")
def train(db: DbSession, payload: dict = Body(...),
          user: dict = Depends(require("model:train"))) -> dict:
    from app.models.asset import Slide
    from app.services.pipeline_service import train_mil_model

    if want_async(payload):
        try:
            job = job_service.submit_train(db, payload=payload, actor=user.get("username", ""),
                                           actor_name=user.get("real_name", ""),
                                           org_code=user.get("org_code") or "")
        except job_service.BusyError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return ok({"async": True, "job": job_brief(job)},
                  message="训练作业已提交，可在任务中心查看逐轮进度")

    base_id = payload.get("base_id")
    base = db.get(ModelBase, int(base_id)) if base_id else db.execute(select(ModelBase).limit(1)).scalar_one_or_none()
    if base is None:
        raise HTTPException(status_code=404, detail="模型基座不存在")

    encoder_code = str(payload.get("encoder_code") or base.default_encoder_code or settings.default_encoder)
    site_codes = payload.get("site_codes") or []
    split = str(payload.get("split") or "train")
    semver = str(payload.get("semver") or "")

    stmt = select(Slide).where(Slide.staining == "H&E")
    if split:
        stmt = stmt.where(Slide.split == split)
    if site_codes:
        stmt = stmt.where(Slide.site_code.in_(site_codes))
    slides = list(db.execute(stmt).scalars())
    if len(slides) < 6:
        raise HTTPException(status_code=400, detail=f"符合条件的切片仅 {len(slides)} 张，不足以训练")

    ordered = sorted(slides, key=lambda s: (s.site_code, s.code))
    val_size = max(2, int(len(ordered) * float(payload.get("val_ratio") or 0.2)))
    val = [(s, 1.0 if s.has_lesion else 0.0) for s in ordered[-val_size:]]
    train_slides = [(s, 1.0 if s.has_lesion else 0.0) for s in ordered[:-val_size]]

    try:
        result = train_mil_model(
            db, base=base, encoder_code=encoder_code,
            task_code=str(payload.get("task_code") or "lymph_node_metastasis"),
            train_slides=train_slides, val_slides=val, semver=semver,
            deployment_env=user.get("deployment_env"),
            triggered_by=user.get("username", ""),
            gpu_hourly_cost=float(payload.get("gpu_hourly_cost") or 0.0),
        )
    except LicenseViolation as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"训练失败：{exc}") from exc

    db.commit()
    return ok({
        "job": result["job"].to_dict(),
        "version": result["version"].to_dict(),
        "metrics": result["metrics"],
    })


@router.post("/models/versions/{version_id}/lock", summary="锁定注册基线版本（锁定后禁止就地修改）")
def lock_version(version_id: int, db: DbSession, payload: dict = Body(default={}),
                 user: dict = Depends(require("model:write"))) -> dict:
    version = db.get(ModelVersion, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="模型版本不存在")
    if version.locked:
        raise HTTPException(status_code=400, detail="该版本已锁定")
    version.locked = True
    version.is_registration_candidate = True
    version.status = "locked"
    version.changelog = (version.changelog or "") + (
        f"\n[{__import__('datetime').datetime.now().isoformat(timespec='seconds')}] "
        f"由 {user.get('username')} 锁定为注册申报基线版本。"
    )
    db.flush()
    audit(db, user, action="lock_model_version", resource_type="model_version", resource_id=version.id,
          summary=f"锁定模型版本 {version.semver} 为注册基线",
          payload={"reason": payload.get("reason", "")}, risk_level="attention")
    db.commit()
    return ok(version.to_dict())


@router.get("/models/tasks", summary="辅助诊断任务清单（Tier 1/2/3）")
def tasks(user: dict = Depends(require("model:read"))) -> dict:
    tiers = []
    for tier, codes in TIER_TASKS.items():
        tiers.append({
            "tier": tier,
            "tasks": [
                {**TASK_DEFINITIONS.get(code, {"code": code, "name": code}),
                 "registered_task": code in TASK_DEFINITIONS}
                for code in codes
            ],
        })
    return ok({"tiers": tiers, "definitions": list(TASK_DEFINITIONS.values())})


@router.get("/models/overview", summary="模型与算力总览")
def overview(db: DbSession, user: dict = Depends(require("model:read"))) -> dict:
    versions = list(db.execute(select(ModelVersion).order_by(ModelVersion.id.desc())).scalars())
    jobs = list(db.execute(select(TrainingJob).order_by(TrainingJob.id.desc()).limit(10)).scalars())
    resources = list(db.execute(select(ComputeResource)).scalars())
    license_audit = encoder_service.license_audit()
    base = db.execute(select(ModelBase).order_by(ModelBase.id.asc()).limit(1)).scalar_one_or_none()
    lock_count = int(db.execute(
        select(func.count(ModelVersion.id)).where(ModelVersion.locked.is_(True))
    ).scalar() or 0)
    return ok({
        "base": base.to_dict() if base else None,
        "version_count": len(versions),
        "locked_count": lock_count,
        "latest_versions": [
            {**v.to_dict(), "metrics": json.loads(v.metrics_json or "{}")} for v in versions[:6]
        ],
        "recent_jobs": [j.to_dict() for j in jobs],
        "compute_resources": [r.to_dict() for r in resources],
        "compute_total": {
            "gpu_count": sum(r.gpu_count for r in resources),
            "gpu_memory_gb": sum(r.gpu_memory_gb * max(r.gpu_count, 1) for r in resources),
            "storage_tb": round(sum(r.storage_tb for r in resources), 1),
            "avg_utilization": round(
                sum(r.utilization for r in resources) / max(len(resources), 1), 4
            ),
            "rented_count": sum(1 for r in resources if r.resource_type == "rented"),
            "gateway_count": sum(1 for r in resources if r.is_gateway),
        },
        "compute_note": (
            "算力不是本项目的瓶颈：业内已有仅用 16 张算力卡完成临床级病理大模型开发部署的公开案例。"
            "本项目首期算力投入建议以租用为主、自建为辅，把资本开支压后到产品验证通过之后。"
        ),
        "license_audit": license_audit,
    })
