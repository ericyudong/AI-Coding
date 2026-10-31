"""API v1 路由聚合。

12 个业务模块的路由在 main.py 中统一挂载到 settings.api_prefix 之下。
模块顺序即前端左侧导航顺序，与设计文档章节一一对应。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    agents,
    assets,
    auth,
    compliance,
    edge,
    evaluation,
    jobs,
    labels,
    models,
    ops,
    pipeline,
    registry,
    stream,
    uploads,
    system,
)

# 模块顺序 = 导航顺序 = 设计文档章节顺序
MODULE_ROUTERS = [
    auth.router,
    assets.router,
    labels.router,
    models.router,
    pipeline.router,
    agents.router,
    evaluation.router,
    compliance.router,
    edge.router,
    registry.router,
    stream.router,
    uploads.router,
    ops.router,
    system.router,
    jobs.router,
]


def build_router() -> APIRouter:
    api = APIRouter()
    for module_router in MODULE_ROUTERS:
        api.include_router(module_router)
    return api


__all__ = ["build_router", "MODULE_ROUTERS"]
