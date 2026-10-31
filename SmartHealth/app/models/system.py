"""系统管理实体：用户、角色、用户-角色关联、系统配置、数据字典。"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import BaseModel

user_roles = Table(
    "sys_user_role",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("sys_user.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("sys_role.id", ondelete="CASCADE"), primary_key=True),
)


class RoleModel(BaseModel):
    """角色（RBAC 主体）。key 与 core/security.py::ROLE_DEFINITIONS 一一对应。"""

    __tablename__ = "sys_role"

    key = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(80), nullable=False)
    description = Column(String(512), default="")
    permissions_json = Column(Text, default="[]")
    is_builtin = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)


class User(BaseModel):
    """平台用户。院内私有化部署，账号本地维护。"""

    __tablename__ = "sys_user"

    username = Column(String(64), unique=True, index=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    real_name = Column(String(80), nullable=False)
    employee_no = Column(String(64), default="")
    department = Column(String(120), default="")
    title = Column(String(80), default="")
    email = Column(String(160), default="")
    phone = Column(String(32), default="")
    is_active = Column(Boolean, default=True)
    deployment_env = Column(String(16), default="research")
    """该账号所属环境：research=科研/探索线，product=商用主线（受许可证门禁约束）。"""

    org_code = Column(String(64), index=True, default="")
    """所属机构编码。院内私有化下通常为本院；云边协同下用于跨机构隔离。"""
    site_code = Column(String(32), index=True, default="")
    """所属数据中心编号。与 asset_slide.site_code 对应，用于按中心划分数据可见范围。"""
    data_scope = Column(String(16), default="all")
    """数据可见范围：all=全院 / org=本机构 / site=本中心。行级隔离依据（见 core/scoping.py）。"""
    must_change_password = Column(Boolean, default=False)
    """首次登录或管理员重置后强制改密。"""
    failed_login_count = Column(Integer, default=0)
    locked_until = Column(String(32), default="")
    """连续登录失败超过阈值后的锁定截止时间（ISO 字符串，空表示未锁定）。"""

    last_login_at = Column(String(32), default="")
    remark = Column(String(512), default="")

    roles = relationship("RoleModel", secondary=user_roles, lazy="selectin")


class RefreshSession(BaseModel):
    """刷新令牌会话。支持轮换（refresh 一次用一次）与主动吊销（踢下线）。

    为什么必须做：access token 有效期长则被窃取后长期有效；短则用户频繁重登录。
    标准解法是「短 access + 长 refresh + refresh 轮换」，并保留可吊销的会话记录。
    """

    __tablename__ = "sys_refresh_session"

    user_id = Column(Integer, ForeignKey("sys_user.id", ondelete="CASCADE"), index=True, nullable=False)
    token_hash = Column(String(128), unique=True, index=True, nullable=False)
    """只存哈希，不存明文令牌 —— 数据库泄露不等于会话泄露。"""
    issued_at = Column(String(32), default="")
    expires_at = Column(String(32), default="")
    rotated_from = Column(String(128), default="")
    """轮换链：新令牌记录它替换了哪个旧令牌，便于发现重放（旧令牌被再次使用 = 疑似窃取）。"""
    revoked_at = Column(String(32), default="")
    revoke_reason = Column(String(120), default="")
    device = Column(String(200), default="")
    client_ip = Column(String(64), default="")
    last_used_at = Column(String(32), default="")
    use_count = Column(Integer, default=0)


class LoginAttempt(BaseModel):
    """登录尝试记录。用于失败锁定与异常登录审计。"""

    __tablename__ = "sys_login_attempt"

    username = Column(String(64), index=True, default="")
    client_ip = Column(String(64), index=True, default="")
    success = Column(Boolean, default=False)
    reason = Column(String(120), default="")
    at = Column(String(32), default="")


class SystemConfig(BaseModel):
    __tablename__ = "sys_config"

    key = Column(String(128), unique=True, index=True, nullable=False)
    value = Column(Text, default="")
    value_type = Column(String(16), default="string")
    category = Column(String(64), default="general")
    label = Column(String(160), default="")
    description = Column(String(512), default="")
    editable = Column(Boolean, default=True)


class Dictionary(BaseModel):
    __tablename__ = "sys_dictionary"

    dict_type = Column(String(64), index=True, nullable=False)
    dict_key = Column(String(64), nullable=False)
    dict_label = Column(String(120), nullable=False)
    sort_order = Column(Integer, default=0)
    extra_json = Column(Text, default="{}")
    enabled = Column(Boolean, default=True)
