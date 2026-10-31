"""系统管理与平台元信息接口（对应设计文档第二章平台能力矩阵）。"""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import func, select

from app.api.v1.common import crud_router, list_query, ok, serialize
from app.core.database import engine
from app.core.deps import CurrentUser, DbSession, audit, require
from app.core.security import ROLE_DEFINITIONS, hash_password, permissions_for_roles
from app.models.system import Dictionary, RoleModel, SystemConfig, User, user_roles

router = APIRouter(tags=["12 系统管理"])

router.include_router(crud_router(
    model=RoleModel, prefix="/system/roles", tag="角色", resource_type="sys_role",
    permission_read="system:read", permission_write="system:write",
    search_fields=("key", "name", "description"),
    filter_fields=("is_builtin",),
    json_fields=("permissions_json",), order_by="sort_order",
    summary_template="更新角色 {row.key}",
))

router.include_router(crud_router(
    model=SystemConfig, prefix="/system/configs", tag="系统配置", resource_type="sys_config",
    permission_read="system:read", permission_write="system:write",
    search_fields=("key", "value", "label", "description"),
    filter_fields=("category", "value_type", "editable"),
    order_by="id", summary_template="更新系统配置 {row.key}",
))

router.include_router(crud_router(
    model=Dictionary, prefix="/system/dictionaries", tag="数据字典", resource_type="dictionary",
    permission_read="system:read", permission_write="system:write",
    search_fields=("dict_type", "dict_key", "dict_label"),
    filter_fields=("dict_type", "enabled"),
    json_fields=("extra_json",), order_by="sort_order",
    summary_template="更新字典项 {row.dict_type}/{row.dict_key}",
))


# ------------------------------------------------------------------ 用户
def _user_payload(user: User) -> dict:
    return {
        **user.to_dict(exclude=("password_hash",)),
        "roles": [r.key for r in user.roles],
        "role_names": [r.name for r in user.roles],
        "permissions": permissions_for_roles([r.key for r in user.roles]),
    }


@router.get("/system/users", summary="用户列表")
def list_users(db: DbSession, user: dict = Depends(require("system:read")),
               page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
               search: str = Query(""), role: str = Query(""),
               is_active: str = Query("")) -> dict:
    columns = {c.key: c for c in User.__table__.columns}
    filters = {}
    if is_active not in ("", None):
        filters[columns["is_active"]] = is_active.lower() in ("1", "true", "yes")
    items, total = list_query(
        db, User, page=page, page_size=page_size, search=search,
        search_fields=[columns[f] for f in ("username", "real_name", "employee_no", "department", "email")],
        filters=filters, order_by=columns["id"], descending=True,
    )
    payload = [_user_payload(u) for u in items]
    if role:
        payload = [u for u in payload if role in u["roles"]]
    return ok({
        "items": payload,
        "meta": {"total": total, "page": page, "page_size": page_size,
                 "pages": (total + page_size - 1) // page_size},
    })


@router.post("/system/users", summary="新建用户", status_code=201)
def create_user(db: DbSession, payload: dict = Body(...),
                user: dict = Depends(require("system:write"))) -> dict:
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    if not username or not password:
        raise HTTPException(status_code=422, detail="用户名与初始密码不能为空")
    if db.execute(select(User).where(User.username == username)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"用户名 {username} 已存在")

    row = User(
        username=username,
        password_hash=hash_password(password),
        real_name=str(payload.get("real_name") or username),
        employee_no=str(payload.get("employee_no") or ""),
        department=str(payload.get("department") or ""),
        title=str(payload.get("title") or ""),
        email=str(payload.get("email") or ""),
        phone=str(payload.get("phone") or ""),
        deployment_env=str(payload.get("deployment_env") or "research"),
        remark=str(payload.get("remark") or ""),
    )
    for key in payload.get("roles") or []:
        role_row = db.execute(select(RoleModel).where(RoleModel.key == key)).scalar_one_or_none()
        if role_row:
            row.roles.append(role_row)
    db.add(row)
    db.flush()
    audit(db, user, action="create_user", resource_type="sys_user", resource_id=row.id,
          summary=f"新建用户 {username}（角色 {'/'.join(r.key for r in row.roles)}）",
          risk_level="attention")
    db.commit()
    return ok(_user_payload(row))


@router.patch("/system/users/{user_id}", summary="更新用户（含角色与启停）")
def update_user(user_id: int, db: DbSession, payload: dict = Body(...),
                user: dict = Depends(require("system:write"))) -> dict:
    row = db.get(User, user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if "roles" in payload:
        row.roles.clear()
        for key in payload.get("roles") or []:
            role_row = db.execute(select(RoleModel).where(RoleModel.key == key)).scalar_one_or_none()
            if role_row:
                row.roles.append(role_row)
    if payload.get("password"):
        row.password_hash = hash_password(str(payload["password"]))
    changed = row.update_from(payload, allowed=(
        "real_name", "employee_no", "department", "title", "email", "phone",
        "is_active", "deployment_env", "remark",
    ))
    db.flush()
    audit(db, user, action="update_user", resource_type="sys_user", resource_id=row.id,
          summary=f"更新用户 {row.username}：{', '.join(changed) or '角色/密码变更'}",
          payload={"changed": changed}, risk_level="attention")
    db.commit()
    return ok(_user_payload(row))


@router.post("/system/users/{user_id}/reset-password", summary="重置用户密码")
def reset_password(user_id: int, db: DbSession, payload: dict = Body(...),
                   user: dict = Depends(require("system:write"))) -> dict:
    row = db.get(User, user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    new_password = str(payload.get("password") or "")
    if len(new_password) < 6:
        raise HTTPException(status_code=422, detail="新密码长度不足 6 位")
    row.password_hash = hash_password(new_password)
    db.flush()
    audit(db, user, action="reset_password", resource_type="sys_user", resource_id=row.id,
          summary=f"重置用户 {row.username} 密码", risk_level="attention")
    db.commit()
    return ok({"user_id": row.id, "username": row.username, "message": "密码已重置"})


# ------------------------------------------------------------------ 平台元信息
MODULES = [
    ("auth", "01 认证", "登录、当前用户与角色权限定义"),
    ("assets", "02 数据资产", "数据资产盘点、切片管理、四层标签关联与存储分层"),
    ("labels", "03 标签体系", "标签定义、标注人员资质、SOP、质控与仲裁"),
    ("models", "04 模型与算力", "模型基座、版本、LoRA 适配器、训练任务与算力资源"),
    ("pipeline", "05 推理流水线", "特征预计算、训练、推理、注意力热区与向量索引"),
    ("agents", "06 智慧医疗 Agent", "五智能体会话、轨迹、证据链、探查记录与能力边界"),
    ("evaluation", "07 评测基座", "评测集、指标、跨中心衰减与 MRMC 人工对照"),
    ("compliance", "08 合规与注册", "伦理台账、审计链、可解释性、审评关口与就绪度"),
    ("edge", "09 云边协同", "边缘节点、模型下发、联邦式增量微调与数据不出域校验"),
    ("registry", "10 注册与路线图", "注册路径、里程碑、风险台账与临床试验中心"),
    ("ops", "11 运营看板", "KPI 快照、团队编制、成本结构与立项决策"),
    ("system", "12 系统管理", "用户、角色、系统配置与数据字典"),
]


@router.get("/system/catalog", summary="平台模块目录（前端导航与能力矩阵的数据源）")
def catalog(db: DbSession, user: dict = Depends(require("system:read"))) -> dict:
    return ok({
        "app": "SmartHealth · 蓝天健康病理垂类模型与智慧医疗 Agent 平台",
        "modules": [
            {"key": key, "label": label, "description": desc} for key, label, desc in MODULES
        ],
        "roles": [
            {"key": key, "name": value["name"], "description": value["description"],
             "permissions": value["permissions"]}
            for key, value in ROLE_DEFINITIONS.items()
        ],
    })


@router.get("/system/migrations", summary="数据库迁移状态（版本/待应用/校验和漂移）")
def migrations(db: DbSession, user: dict = Depends(require("system:read"))) -> dict:
    """给运维看「库结构和代码是否一致」。

    这是升级/回滚时第一个要看的接口：pending 非空或 checksum_drift 非空都意味着
    当前库结构与代码不匹配，此时任何写入都可能失败或产生脏数据。
    """
    from app.core.database import engine
    from app.core.migrations import migration_status

    return ok(migration_status(engine))


@router.get("/system/deployment", summary="部署形态自述（进程角色/锁后端/多进程安全）")
def deployment(db: DbSession, user: dict = Depends(require("system:read"))) -> dict:
    """让运维一眼确认「这个进程扮演什么角色」。

    多进程部署最容易出的问题不是崩溃，而是**角色配错**：
    API 进程里也跑了 Worker（并发翻倍）、或所有进程都跑周期任务（重复执行）。
    这个接口把角色与保护机制显式列出来，避免靠翻配置猜。
    """
    import os

    from app.core.config import settings
    from app.core.locks import lock_status
    from app.core.tasks import TASKS

    locks = lock_status()
    return ok({
        "process": {
            "pid": os.getpid(),
            "role": "api+worker" if settings.workers_in_api else "api_only",
            "role_label": ("单进程：API 与作业 Worker 同进程" if settings.workers_in_api
                           else "多进程：本进程仅提供 API，作业由独立 Worker 进程执行"),
            "worker_id": TASKS.worker_id,
        },
        "database": {
            "backend": settings.db_backend,
            "pool_size": settings.db_pool_size,
            "job_claim_strategy": ("SELECT ... FOR UPDATE SKIP LOCKED（PostgreSQL）"
                                   if settings.db_backend == "postgresql"
                                   else "条件更新乐观并发（SQLite，无 SKIP LOCKED）"),
        },
        "coordination": {
            "lock_backend": locks["backend"],
            "redis_connected": bool(locks["redis"].get("connected")),
            "lease_seconds": locks["lease_seconds"],
            "note": ("Redis 可用：锁与事件推送跨进程实时" if locks["backend"] == "redis"
                     else "Redis 不可用：退化为数据库锁，周期任务仍为 leader-only"),
        },
        "multi_process_safety": {
            "periodic_tasks": "leader-only（每个任务各自抢分布式锁，多实例不会重复执行）",
            "job_recovery": "按心跳判定，启动时不会误杀兄弟进程正在执行的作业",
            "migrations": "迁移前抢锁，多进程同时启动只有一个执行",
            "event_seq": "跨进程惰性对齐 max(seq)，事件流次序可信",
        },
    })


@router.get("/system/scheduler", summary="周期任务状态（下一个触发时间）")
def scheduler(db: DbSession, user: dict = Depends(require("system:read"))) -> dict:
    from app.core.scheduler import scheduler_status

    return ok(scheduler_status())


@router.post("/system/scheduler/{job_id}/run", summary="手工触发一个周期任务")
def run_scheduled(job_id: str, db: DbSession,
                  user: dict = Depends(require("system:write"))) -> dict:
    from app.core.scheduler import run_now

    try:
        detail = run_now(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    audit(db, user, action="run_scheduled_task", resource_type="scheduler", resource_id=job_id,
          summary=f"手工触发周期任务 {job_id}：{detail}")
    db.commit()
    return ok({"job_id": job_id, "detail": detail})


@router.get("/system/metrics-summary", summary="关键指标快照（看板用）")
def metrics_summary(db: DbSession, user: dict = Depends(require("system:read"))) -> dict:
    from app.core.observability import METRICS
    from app.core.tasks import TASKS

    return ok({"metrics": METRICS.snapshot(), "job_engine": TASKS.stats()})


@router.get("/system/health", summary="健康检查与数据规模自述")
def health(db: DbSession, user: dict = Depends(require("system:read"))) -> dict:
    from sqlalchemy import inspect

    tables = sorted(inspect(engine).get_table_names())
    return ok({
        "status": "ok",
        "time": datetime.now().isoformat(timespec="seconds"),
        "table_count": len(tables),
        "tables": tables,
        "user_count": int(db.execute(select(func.count(User.id))).scalar() or 0),
        "role_count": int(db.execute(select(func.count(RoleModel.id))).scalar() or 0),
        "dict_count": int(db.execute(select(func.count(Dictionary.id))).scalar() or 0),
        "config_count": int(db.execute(select(func.count(SystemConfig.id))).scalar() or 0),
    })
