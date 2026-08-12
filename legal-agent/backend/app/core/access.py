"""Data access scope helpers (role + department)."""
from __future__ import annotations

from sqlalchemy import Select, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import can_access_all_data
from app.models.cms_models import ManagedContract
from app.models.models import User


def contract_scope_filter(query: Select, user: User) -> Select:
    """Restrict contracts by ownership / department based on role."""
    if can_access_all_data(user.role):
        # Cross-dept roles still limited to same tenant for now: all contracts
        # In single-tenant α, show all managed contracts
        return query
    if user.department_id:
        return query.where(
            or_(
                ManagedContract.user_id == user.id,
                ManagedContract.department_id == user.department_id,
            )
        )
    return query.where(ManagedContract.user_id == user.id)


def can_view_contract(user: User, contract: ManagedContract) -> bool:
    if can_access_all_data(user.role):
        return True
    if contract.user_id == user.id:
        return True
    if user.department_id and contract.department_id == user.department_id:
        return True
    return False


async def visible_contract_ids(db: AsyncSession, user: User) -> set[int] | None:
    """Return visible contract IDs. None means no restriction (cross-dept / admin)."""
    if can_access_all_data(user.role):
        return None
    result = await db.execute(contract_scope_filter(select(ManagedContract.id), user))
    return {row[0] for row in result.all()}
