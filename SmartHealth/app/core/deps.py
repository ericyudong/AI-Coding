"""FastAPI 依赖：数据库会话、当前用户、权限校验、审计辅助。"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.security import ALL_PERMISSIONS, decode_access_token, has_permission, permissions_for_roles

DbSession = Annotated[Session, Depends(get_db)]


def _extract_token(authorization: str | None, x_token: str | None) -> str | None:
    if x_token:
        return x_token.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def _load_user(db: Session, token: str) -> dict[str, Any]:
    """用令牌解析出当前用户（含角色、权限、数据范围）。

    抽出来是为了让「常规接口（只认请求头）」与「流式端点（还认查询参数）」
    共用同一份解析与校验逻辑 —— 否则两处实现必然会漂移，
    典型后果是流式通道少校验 `is_active`，停用账号还能继续收事件。
    """
    from app.models.system import User

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌无效或已过期")

    user_id = payload.get("sub")
    user = db.get(User, int(user_id)) if user_id and str(user_id).isdigit() else None
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已停用")

    roles = [r.key for r in user.roles]
    return {
        "id": user.id,
        "username": user.username,
        "real_name": user.real_name,
        "department": user.department,
        "roles": roles,
        "permissions": permissions_for_roles(roles),
        "is_admin": "admin" in roles,
        "deployment_env": user.deployment_env,
        # 数据隔离三要素：机构、中心、可见范围（见 core/scoping.py）
        "org_code": user.org_code or "",
        "site_code": user.site_code or "",
        "data_scope": user.data_scope or "all",
    }


def get_current_user(
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
    x_token: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """常规接口鉴权：只接受请求头里的令牌。"""
    token = _extract_token(authorization, x_token)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少访问令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _load_user(db, token)


CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


def get_stream_user(
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
    x_token: Annotated[str | None, Header()] = None,
    token: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    """SSE/WebSocket 专用鉴权：额外接受 `?token=` 查询参数。

    **为什么必须开后门**：浏览器原生 `EventSource` 无法自定义请求头，
    令牌只能放进 URL。这是 SSE 的固有限制，不是设计疏忽。

    为把风险控制住，做了三件事：
    1. **只为流式端点开放**（本函数只给 /jobs/stream 用，普通接口仍只认请求头）；
    2. **访问日志脱敏**：可观测中间件会把 URL 里的 token 抹成 `***`
       （令牌进日志 = 令牌泄露，这比令牌进 URL 更危险）；
    3. 令牌本身是短时效 access token（默认 60 分钟），不是长期凭证。
    """
    resolved = _extract_token(authorization, x_token) or (token.strip() if token else None)
    if not resolved:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少访问令牌（流式端点支持 Authorization 头、X-Token 头或 ?token= 查询参数）",
        )
    return _load_user(db, resolved)


def require(permission: str):
    """权限校验依赖工厂：`Depends(require("asset:write"))`。"""

    def _checker(user: CurrentUser) -> dict[str, Any]:
        if not has_permission(user["permissions"], permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"缺少权限：{permission}",
            )
        return user

    return _checker


def audit(
    db: Session,
    user: dict[str, Any] | None,
    *,
    action: str,
    resource_type: str,
    resource_id: str | int | None = None,
    summary: str | None = None,
    payload: dict[str, Any] | None = None,
    risk_level: str = "normal",
) -> None:
    """在业务接口内写审计链。actor 为空时记为 system（定时任务/种子）。"""
    record_audit(
        db,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        actor=(user or {}).get("username") or "system",
        actor_role=",".join((user or {}).get("roles") or []) or "system",
        summary=summary,
        payload=payload,
        risk_level=risk_level,
    )


__all__ = ["DbSession", "CurrentUser", "get_current_user", "require", "audit", "ALL_PERMISSIONS"]
