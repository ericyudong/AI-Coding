"""System admin service: users and departments."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import ROLE_FEATURES, ROLE_LABELS, Role, has_feature
from app.core.security import hash_password
from app.models.models import User
from app.models.performance_models import Department
from app.schemas.prd_schemas import DepartmentOut, UserCreateRequest, UserResponse, UserUpdateRequest


def user_to_response(user: User, dept_name: str | None = None) -> UserResponse:
    role = user.role or Role.LEGAL
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        role=role,
        department_id=user.department_id,
        department_name=dept_name,
        is_active=bool(user.is_active),
        features=sorted(ROLE_FEATURES.get(role, set())),
    )


async def list_departments(db: AsyncSession) -> list[DepartmentOut]:
    rows = (await db.execute(select(Department).order_by(Department.id))).scalars().all()
    return [DepartmentOut.model_validate(r) for r in rows]


async def list_users(db: AsyncSession) -> list[UserResponse]:
    users = (await db.execute(select(User).order_by(User.id))).scalars().all()
    depts = {d.id: d.name for d in (await db.execute(select(Department))).scalars().all()}
    return [user_to_response(u, depts.get(u.department_id or 0)) for u in users]


async def create_user(db: AsyncSession, body: UserCreateRequest) -> UserResponse:
    if body.role not in ROLE_LABELS:
        raise ValueError(f"无效角色: {body.role}")
    exists = (await db.execute(select(User).where(User.username == body.username))).scalar_one_or_none()
    if exists:
        raise ValueError("用户名已存在")
    user = User(
        username=body.username,
        email=body.email or f"{body.username}@yihui.tech",
        hashed_password=hash_password(body.password),
        display_name=body.display_name or body.username,
        role=body.role,
        department_id=body.department_id,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    dept_name = None
    if user.department_id:
        dept = await db.get(Department, user.department_id)
        dept_name = dept.name if dept else None
    return user_to_response(user, dept_name)


async def update_user(db: AsyncSession, user_id: int, body: UserUpdateRequest) -> UserResponse:
    user = await db.get(User, user_id)
    if not user:
        raise ValueError("用户不存在")
    if body.email is not None:
        user.email = body.email
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.role is not None:
        if body.role not in ROLE_LABELS:
            raise ValueError(f"无效角色: {body.role}")
        user.role = body.role
    if body.department_id is not None:
        user.department_id = body.department_id
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.password:
        user.hashed_password = hash_password(body.password)
    await db.commit()
    await db.refresh(user)
    dept_name = None
    if user.department_id:
        dept = await db.get(Department, user.department_id)
        dept_name = dept.name if dept else None
    return user_to_response(user, dept_name)


def require_feature(user: User, feature: str) -> None:
    if not has_feature(user.role, feature):
        raise PermissionError(f"无权限访问: {feature}")
