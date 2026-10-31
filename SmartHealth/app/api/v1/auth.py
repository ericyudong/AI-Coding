"""认证与个人中心接口。

商用认证基线（相比演示版的差别）：
1. **双令牌**：短命 access（默认 60 分钟）+ 长命 refresh（默认 14 天）。
   access 泄露的窗口从「一周」压到「一小时」。
2. **refresh 轮换**：一次一换。旧令牌被再次使用即判定为疑似窃取，立即吊销整条会话链。
3. **登录失败锁定**：连续失败达阈值锁定账号，并记录每一次尝试（含 IP）。
4. **会话可管理**：列出自己的登录会话并逐个踢下线 —— 这是等保与院内 IT 的常见要求。
5. **密码策略**：策略校验失败时返回「缺哪一条」而不是笼统的「密码不合规」。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy import func, select

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession, audit
from app.core.response import ok
from app.core.security import (
    ROLE_DEFINITIONS,
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    permissions_for_roles,
    validate_password_policy,
    verify_password,
)
from app.models.system import LoginAttempt, RefreshSession, User

router = APIRouter(prefix="/auth", tags=["01 认证"])


def _client_ip(request: Request | None) -> str:
    if request is None:
        return ""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return (request.client.host if request.client else "")[:64]


def _is_locked(user: User) -> bool:
    if not user.locked_until:
        return False
    try:
        return datetime.fromisoformat(user.locked_until) > datetime.now()
    except ValueError:
        return False


def _record_attempt(db, username: str, ip: str, success: bool, reason: str = "") -> None:
    db.add(LoginAttempt(username=username[:64], client_ip=ip, success=success,
                        reason=reason[:120], at=datetime.now().isoformat(timespec="seconds")))


def _issue_tokens(db, user: User, request: Request | None,
                  *, rotated_from: str = "") -> tuple[str, str, int]:
    """签发 access + refresh，并登记可吊销的会话记录。"""
    roles = [r.key for r in user.roles]
    access, expires_in = create_access_token(
        user.id, extra={"username": user.username, "roles": roles})
    raw_refresh, refresh_hash = create_refresh_token()
    now = datetime.now()
    db.add(RefreshSession(
        user_id=user.id,
        token_hash=refresh_hash,
        issued_at=now.isoformat(timespec="seconds"),
        expires_at=(now + timedelta(days=settings.refresh_token_expire_days)).isoformat(timespec="seconds"),
        rotated_from=rotated_from,
        device=(request.headers.get("user-agent", "")[:200] if request else ""),
        client_ip=_client_ip(request),
        last_used_at=now.isoformat(timespec="seconds"),
    ))
    db.flush()
    return access, raw_refresh, expires_in


def _user_payload(user: User) -> dict:
    roles = [r.key for r in user.roles]
    return {
        "id": user.id,
        "username": user.username,
        "real_name": user.real_name,
        "department": user.department,
        "title": user.title,
        "roles": roles,
        "role_names": [r.name for r in user.roles],
        "permissions": permissions_for_roles(roles),
        "deployment_env": user.deployment_env,
        "org_code": user.org_code or "",
        "site_code": user.site_code or "",
        "data_scope": user.data_scope or "all",
        "must_change_password": bool(user.must_change_password),
    }


# ------------------------------------------------------------------ 登录
@router.post("/login", summary="账号密码登录（返回 access + refresh）")
def login(db: DbSession, request: Request, payload: dict = Body(...)) -> dict:
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    ip = _client_ip(request)
    if not username or not password:
        raise HTTPException(status_code=422, detail="用户名与密码不能为空")

    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if user is None:
        _record_attempt(db, username, ip, False, "账号不存在")
        db.commit()
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if _is_locked(user):
        _record_attempt(db, username, ip, False, "账号已锁定")
        db.commit()
        remaining = (datetime.fromisoformat(user.locked_until) - datetime.now()).seconds // 60 + 1
        raise HTTPException(
            status_code=423,
            detail=f"账号因连续登录失败已被锁定，请约 {remaining} 分钟后重试或联系管理员解锁")

    if not verify_password(password, user.password_hash):
        user.failed_login_count = int(user.failed_login_count or 0) + 1
        reason = f"密码错误（第 {user.failed_login_count} 次）"
        detail = "用户名或密码错误"
        if user.failed_login_count >= settings.login_max_failures:
            user.locked_until = (datetime.now()
                                 + timedelta(minutes=settings.login_lock_minutes)).isoformat(timespec="seconds")
            user.failed_login_count = 0
            reason = "连续失败达到阈值，账号锁定"
            detail = (f"连续 {settings.login_max_failures} 次失败，账号已锁定 "
                      f"{settings.login_lock_minutes} 分钟")
        _record_attempt(db, username, ip, False, reason)
        audit(db, {"username": username, "roles": []}, action="login_failed",
              resource_type="sys_user", resource_id=user.id,
              summary=f"登录失败：{reason}（IP {ip}）", risk_level="attention")
        db.commit()
        raise HTTPException(status_code=401, detail=detail)

    if not user.is_active:
        _record_attempt(db, username, ip, False, "账号已停用")
        db.commit()
        raise HTTPException(status_code=403, detail="账号已停用，请联系系统管理员")

    # 登录成功：清零失败计数与锁定
    user.failed_login_count = 0
    user.locked_until = ""
    user.last_login_at = datetime.now().isoformat(timespec="seconds")
    access, refresh, expires_in = _issue_tokens(db, user, request)
    _record_attempt(db, username, ip, True, "登录成功")
    audit(db, {"username": user.username, "roles": [r.key for r in user.roles]},
          action="login", resource_type="sys_user", resource_id=user.id,
          summary=f"用户 {user.username} 登录成功（IP {ip}）")
    db.commit()

    return ok({
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": expires_in,
        "refresh_expires_in": settings.refresh_token_expire_days * 86400,
        "user": _user_payload(user),
    })


@router.post("/refresh", summary="用刷新令牌换取新令牌（一次一换，旧令牌作废）")
def refresh_token(db: DbSession, request: Request, payload: dict = Body(...)) -> dict:
    raw = str(payload.get("refresh_token") or "").strip()
    if not raw:
        raise HTTPException(status_code=422, detail="必须提供 refresh_token")

    token_hash = hash_token(raw)
    session_row = db.execute(
        select(RefreshSession).where(RefreshSession.token_hash == token_hash)
    ).scalar_one_or_none()
    if session_row is None:
        raise HTTPException(status_code=401, detail="刷新令牌无效")

    if session_row.revoked_at:
        # 已吊销令牌被再次使用 → 疑似令牌泄露，连带吊销该用户全部会话
        db.execute(
            RefreshSession.__table__.update()
            .where(RefreshSession.user_id == session_row.user_id,
                   RefreshSession.revoked_at == "")
            .values(revoked_at=datetime.now().isoformat(timespec="seconds"),
                    revoke_reason="检测到已吊销令牌被重复使用，疑似泄露，全量吊销")
        )
        audit(db, {"username": f"user#{session_row.user_id}", "roles": []},
              action="refresh_replay_detected", resource_type="sys_session",
              resource_id=session_row.id,
              summary=f"刷新令牌重放：已吊销该用户全部会话（IP {_client_ip(request)}）",
              risk_level="attention")
        db.commit()
        raise HTTPException(status_code=401, detail="刷新令牌已失效，该账号全部会话已被强制下线，请重新登录")

    if session_row.expires_at and session_row.expires_at < datetime.now().isoformat(timespec="seconds"):
        raise HTTPException(status_code=401, detail="刷新令牌已过期，请重新登录")

    user = db.get(User, session_row.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="账号不存在或已停用")

    # 轮换：吊销旧会话，签发新会话并记录轮换链
    session_row.revoked_at = datetime.now().isoformat(timespec="seconds")
    session_row.revoke_reason = "正常轮换（refresh 一次一换）"
    session_row.use_count = int(session_row.use_count or 0) + 1
    access, new_refresh, expires_in = _issue_tokens(db, user, request,
                                                    rotated_from=token_hash)
    db.commit()
    return ok({
        "access_token": access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "expires_in": expires_in,
        "rotated": True,
        "user": _user_payload(user),
    })


@router.get("/me", summary="当前登录用户")
def me(db: DbSession, user: CurrentUser) -> dict:
    row = db.get(User, user["id"])
    if row is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return ok({**user, **_user_payload(row)})


@router.get("/data-scope", summary="当前账号的数据可见范围（前端页头展示）")
def data_scope(user: CurrentUser) -> dict:
    from app.core import scoping

    return ok(scoping.describe(user))


@router.get("/roles", summary="角色与权限定义")
def roles(_: CurrentUser) -> dict:
    return ok([
        {"key": key, "name": value["name"], "description": value["description"],
         "permissions": value["permissions"]}
        for key, value in ROLE_DEFINITIONS.items()
    ])


# ------------------------------------------------------------------ 会话管理
@router.get("/sessions", summary="我的登录会话（可逐个踢下线）")
def my_sessions(db: DbSession, user: CurrentUser) -> dict:
    rows = list(db.execute(
        select(RefreshSession).where(RefreshSession.user_id == user["id"])
        .order_by(RefreshSession.id.desc()).limit(50)
    ).scalars())
    now = datetime.now().isoformat(timespec="seconds")
    return ok({
        "items": [
            {**row.to_dict(exclude=("token_hash",)),
             "active": not row.revoked_at and (row.expires_at or "") > now,
             "token_fingerprint": (row.token_hash or "")[:12]}
            for row in rows
        ],
        "active_count": sum(1 for r in rows if not r.revoked_at and (r.expires_at or "") > now),
        "revoked_count": sum(1 for r in rows if r.revoked_at),
    })


@router.post("/sessions/{session_id}/revoke", summary="吊销指定会话")
def revoke_session(session_id: int, db: DbSession, user: CurrentUser) -> dict:
    row = db.get(RefreshSession, session_id)
    if row is None or row.user_id != user["id"]:
        raise HTTPException(status_code=404, detail="会话不存在")
    if row.revoked_at:
        return ok({"session_id": session_id, "already_revoked": True})
    row.revoked_at = datetime.now().isoformat(timespec="seconds")
    row.revoke_reason = f"用户主动吊销（{user['username']}）"
    audit(db, user, action="revoke_session", resource_type="sys_session", resource_id=row.id,
          summary=f"吊销会话 #{row.id}（设备 {row.device[:40]}）", risk_level="attention")
    db.commit()
    return ok({"session_id": session_id, "revoked": True})


@router.post("/logout", summary="退出登录（吊销当前会话）")
def logout(db: DbSession, user: CurrentUser, payload: dict = Body(default={})) -> dict:
    raw = str(payload.get("refresh_token") or "").strip()
    revoked = 0
    if raw:
        row = db.execute(
            select(RefreshSession).where(RefreshSession.token_hash == hash_token(raw))
        ).scalar_one_or_none()
        if row is not None and row.user_id == user["id"] and not row.revoked_at:
            row.revoked_at = datetime.now().isoformat(timespec="seconds")
            row.revoke_reason = "用户登出"
            revoked = 1
    elif payload.get("all_sessions"):
        result = db.execute(
            RefreshSession.__table__.update()
            .where(RefreshSession.user_id == user["id"], RefreshSession.revoked_at == "")
            .values(revoked_at=datetime.now().isoformat(timespec="seconds"),
                    revoke_reason=f"用户登出全部会话（{user['username']}）")
        )
        revoked = int(result.rowcount or 0)
    audit(db, user, action="logout", resource_type="sys_user", resource_id=user["id"],
          summary=f"用户 {user['username']} 退出登录（吊销 {revoked} 个会话）")
    db.commit()
    return ok({"message": "已退出登录", "revoked_sessions": revoked})


# ------------------------------------------------------------------ 密码
@router.post("/change-password", summary="修改本人密码（校验策略 + 吊销其他会话）")
def change_password(db: DbSession, user: CurrentUser, payload: dict = Body(...)) -> dict:
    old_password = str(payload.get("old_password") or "")
    new_password = str(payload.get("new_password") or "")
    row = db.get(User, user["id"])
    if row is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if not verify_password(old_password, row.password_hash):
        raise HTTPException(status_code=400, detail="原密码不正确")
    problems = validate_password_policy(new_password, username=row.username)
    if problems:
        raise HTTPException(status_code=422,
                            detail={"message": "新密码不满足策略", "problems": problems})
    if verify_password(new_password, row.password_hash):
        raise HTTPException(status_code=422, detail="新密码不能与原密码相同")

    row.password_hash = hash_password(new_password)
    row.must_change_password = False
    # 改密后吊销本人其他会话：密码变更意味着「可能有别人知道旧密码」
    result = db.execute(
        RefreshSession.__table__.update()
        .where(RefreshSession.user_id == row.id, RefreshSession.revoked_at == "")
        .values(revoked_at=datetime.now().isoformat(timespec="seconds"),
                revoke_reason="密码已变更，会话统一失效")
    )
    audit(db, user, action="change_password", resource_type="sys_user", resource_id=row.id,
          summary=f"用户 {row.username} 修改密码，吊销 {int(result.rowcount or 0)} 个会话",
          risk_level="attention")
    db.commit()
    return ok({"message": "密码已更新，其他设备需重新登录",
               "revoked_sessions": int(result.rowcount or 0)})


@router.get("/password-policy", summary="密码策略说明（前端表单提示用）")
def password_policy(_: CurrentUser) -> dict:
    return ok({
        "min_length": settings.password_min_length,
        "rules": ["长度至少 %d 位" % settings.password_min_length, "包含小写字母", "包含大写字母",
                  "包含数字", "不能使用常见弱口令", "不能包含账号名"],
        "lock_policy": {
            "max_failures": settings.login_max_failures,
            "lock_minutes": settings.login_lock_minutes,
        },
        "token_policy": {
            "access_expire_minutes": settings.access_token_expire_minutes,
            "refresh_expire_days": settings.refresh_token_expire_days,
            "rotation": "refresh 一次一换；旧令牌被重复使用将强制全量下线",
        },
    })


# ------------------------------------------------------------------ 安全审计
@router.get("/login-attempts", summary="登录尝试记录（异常登录排查）")
def login_attempts(db: DbSession, user: CurrentUser, limit: int = 50,
                   only_failed: bool = False) -> dict:
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="仅系统管理员可查看登录尝试记录")
    stmt = select(LoginAttempt).order_by(LoginAttempt.id.desc()).limit(min(limit, 500))
    if only_failed:
        stmt = (select(LoginAttempt).where(LoginAttempt.success.is_(False))
                .order_by(LoginAttempt.id.desc()).limit(min(limit, 500)))
    rows = list(db.execute(stmt).scalars())
    return ok({
        "items": [r.to_dict() for r in rows],
        "failed_total": int(db.execute(
            select(func.count(LoginAttempt.id)).where(LoginAttempt.success.is_(False))
        ).scalar() or 0),
    })


@router.post("/users/{user_id}/unlock", summary="解锁被锁定的账号（管理员）")
def unlock(db: DbSession, user_id: int, user: CurrentUser) -> dict:
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="仅系统管理员可解锁账号")
    row = db.get(User, user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    row.locked_until = ""
    row.failed_login_count = 0
    audit(db, user, action="unlock_user", resource_type="sys_user", resource_id=row.id,
          summary=f"管理员解锁账号 {row.username}", risk_level="attention")
    db.commit()
    return ok({"user_id": row.id, "username": row.username, "unlocked": True})
