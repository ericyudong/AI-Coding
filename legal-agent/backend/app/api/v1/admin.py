"""System management API."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.roles import FEATURE_SYSTEM_ADMIN, ROLE_LABELS, recommended_questions
from app.models.models import User
from app.schemas.prd_schemas import (
    DepartmentOut,
    TagTaxonomyCreate,
    TagTaxonomyUpdate,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
    WorkbenchRecommendResponse,
)
from app.services import admin_service as svc
from app.services.admin_service import require_feature, user_to_response

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/roles")
async def list_roles(user: User = Depends(get_current_user)):
    return [{"id": k, "label": v} for k, v in ROLE_LABELS.items()]


@router.get("/departments", response_model=list[DepartmentOut])
async def departments(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await svc.list_departments(db)


@router.get("/users", response_model=list[UserResponse])
async def users(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        require_feature(user, FEATURE_SYSTEM_ADMIN)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return await svc.list_users(db)


@router.post("/users", response_model=UserResponse)
async def create_user(
    body: UserCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        require_feature(user, FEATURE_SYSTEM_ADMIN)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        return await svc.create_user(db, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    body: UserUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        require_feature(user, FEATURE_SYSTEM_ADMIN)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        return await svc.update_user(db, user_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/workbench/recommendations", response_model=WorkbenchRecommendResponse)
async def workbench_recommendations(user: User = Depends(get_current_user)):
    role = user.role or "legal"
    return WorkbenchRecommendResponse(
        questions=recommended_questions(role),
        role=role,
        role_label=ROLE_LABELS.get(role, role),
    )


@router.get("/tags")
async def list_tag_taxonomy(
    tree: bool = True,
    all: bool = False,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        require_feature(user, FEATURE_SYSTEM_ADMIN)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    from app.services import tag_service

    rows = await tag_service.list_tags(db, active_only=not all)
    if tree:
        return tag_service.tags_to_tree(rows)
    return [
        {
            "id": r.id,
            "level": r.level,
            "code": r.code,
            "name": r.name,
            "parent_id": r.parent_id,
            "sort_order": r.sort_order,
            "is_active": r.is_active,
        }
        for r in rows
    ]


@router.post("/tags")
async def create_tag(
    body: TagTaxonomyCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        require_feature(user, FEATURE_SYSTEM_ADMIN)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    from app.services import tag_service

    try:
        row = await tag_service.create_tag(
            db,
            level=body.level,
            name=body.name,
            code=body.code,
            parent_id=body.parent_id,
            sort_order=body.sort_order,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": row.id,
        "level": row.level,
        "code": row.code,
        "name": row.name,
        "parent_id": row.parent_id,
        "sort_order": row.sort_order,
        "is_active": row.is_active,
    }


@router.put("/tags/{tag_id}")
async def update_tag(
    tag_id: int,
    body: TagTaxonomyUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        require_feature(user, FEATURE_SYSTEM_ADMIN)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    from app.services import tag_service

    try:
        row = await tag_service.update_tag(db, tag_id, body.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": row.id,
        "level": row.level,
        "code": row.code,
        "name": row.name,
        "parent_id": row.parent_id,
        "sort_order": row.sort_order,
        "is_active": row.is_active,
    }


@router.delete("/tags/{tag_id}")
async def delete_tag(
    tag_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        require_feature(user, FEATURE_SYSTEM_ADMIN)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    from app.services import tag_service

    try:
        await tag_service.soft_delete_tag(db, tag_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}
