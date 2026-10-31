"""认证、密码哈希与 RBAC。

院内私有化部署下不依赖外部 IdP：账号、角色、权限均本地维护。
密码哈希采用标准库 hashlib.pbkdf2_hmac（无需额外依赖，便于信创环境交付）。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import settings

_PBKDF2_ROUNDS = 120_000
_SALT_BYTES = 16


# --------------------------------------------------------------------- 密码
def hash_password(password: str) -> str:
    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return "pbkdf2_sha256${}${}${}".format(
        _PBKDF2_ROUNDS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, hashed: str) -> bool:
    try:
        algo, rounds, salt_b64, digest_b64 = hashed.split("$")
        if algo != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(rounds))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


# ------------------------------------------------------------- 密码策略与令牌
import re as _re

_PASSWORD_RULES = [
    ("length", "长度至少 {min_length} 位"),
    ("lower", "包含小写字母"),
    ("upper", "包含大写字母"),
    ("digit", "包含数字"),
]

_COMMON_WEAK = {
    "password", "passw0rd", "12345678", "123456789", "qwerty123", "admin123",
    "abc12345", "11111111", "88888888", "smarthealth", "iloveyou",
}


def validate_password_policy(password: str, *, min_length: int | None = None,
                             username: str = "") -> list[str]:
    """校验密码强度，返回不满足项的中文说明（空列表表示通过）。

    刻意不用复杂度打分库：规则必须对现场运维可解释 ——
    医生被拦下时，要能立刻看到「缺哪一条」，而不是一个 0—100 的分数。
    """
    from app.core.config import settings as _settings

    min_len = min_length or int(getattr(_settings, "password_min_length", 8))
    problems: list[str] = []
    if len(password or "") < min_len:
        problems.append(f"长度至少 {min_len} 位")
    if not _re.search(r"[a-z]", password or ""):
        problems.append("包含小写字母")
    if not _re.search(r"[A-Z]", password or ""):
        problems.append("包含大写字母")
    if not _re.search(r"\d", password or ""):
        problems.append("包含数字")
    if (password or "").lower() in _COMMON_WEAK:
        problems.append("不能使用常见弱口令")
    if username and username.lower() in (password or "").lower():
        problems.append("不能包含账号名")
    return problems


def hash_token(raw: str) -> str:
    """令牌指纹。数据库只存哈希：库被拖走也不等于会话被接管。"""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_refresh_token() -> tuple[str, str]:
    """生成刷新令牌，返回 (明文, 哈希)。明文只在这一次响应里出现。"""
    raw = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii").rstrip("=")
    return raw, hash_token(raw)


# ----------------------------------------------------------------------- JWT
def create_access_token(subject: str | int, extra: dict[str, Any] | None = None) -> tuple[str, int]:
    expire_seconds = settings.access_token_expire_minutes * 60
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_expire_minutes)).timestamp()),
        "iss": settings.app_short_name,
    }
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    return token, expire_seconds


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm], issuer=settings.app_short_name)
    except jwt.PyJWTError:
        return None


# ---------------------------------------------------------------------- RBAC
ROLE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "admin": {
        "name": "系统管理员",
        "description": "平台全部权限，含用户与配置管理",
        "permissions": ["*"],
    },
    "cmo": {
        "name": "首席医学官",
        "description": "标签体系、标注 SOP、终审判定与临床验证的主导者（设计文档：该岗位必须在 P0 阶段到位）",
        "permissions": [
            "asset:read", "asset:write", "label:read", "label:write", "label:arbitrate",
            "agent:read", "agent:run", "review:read", "review:decide",
            "eval:read", "eval:write", "compliance:read", "compliance:sign",
            "registry:read", "registry:write", "ops:read", "job:read", "job:write",
        ],
    },
    "pathologist": {
        "name": "病理医师",
        "description": "阅片、终审、标注与仲裁参与者",
        "permissions": [
            "asset:read", "label:read", "label:write", "agent:read", "agent:run",
            "review:read", "review:decide", "eval:read", "ops:read", "job:read", "job:write",
        ],
    },
    "algorithm": {
        "name": "算法工程师",
        "description": "模型基座、流水线、评测与实验",
        "permissions": [
            "asset:read", "label:read", "model:read", "model:write", "model:train",
            "pipeline:read", "pipeline:run", "inference:read", "inference:run",
            "eval:read", "eval:write", "agent:read", "agent:run", "ops:read",
            "job:read", "job:write", "edge:read", "edge:write",
        ],
    },
    "compliance": {
        "name": "注册与合规专员",
        "description": "伦理台账、审计链、注册申报与体系核查",
        "permissions": [
            "asset:read", "compliance:read", "compliance:write", "compliance:sign",
            "registry:read", "registry:write", "model:read", "eval:read", "ops:read",
            "job:read", "job:write",
        ],
    },
    "operator": {
        "name": "科室运营",
        "description": "只读查看运营看板与业务数据",
        "permissions": ["asset:read", "label:read", "agent:read", "eval:read", "ops:read",
                        "job:read"],
    },
}

ALL_PERMISSIONS: list[str] = sorted({p for role in ROLE_DEFINITIONS.values() for p in role["permissions"] if p != "*"})


def permissions_for_roles(role_keys: list[str]) -> list[str]:
    """角色 -> 权限集合。admin 拥有通配权限。"""
    result: set[str] = set()
    for key in role_keys:
        role = ROLE_DEFINITIONS.get(key)
        if not role:
            continue
        for perm in role["permissions"]:
            if perm == "*":
                return ["*"]
            result.add(perm)
    return sorted(result)


def has_permission(granted: list[str], required: str) -> bool:
    if "*" in granted:
        return True
    if required in granted:
        return True
    # 支持 asset:* 形式的域通配
    domain = required.split(":")[0]
    return f"{domain}:*" in granted
