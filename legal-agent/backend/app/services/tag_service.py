"""Tag taxonomy admin + contract taxonomy helpers."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.performance_models import TagTaxonomy

DEFAULT_TREE: list[tuple[int, str, str, str | None, int]] = [
    # level, code, name, parent_code, sort
    (1, "purchase", "采购合同", None, 10),
    (1, "sales", "销售合同", None, 20),
    (1, "general", "通用合同", None, 30),
    (2, "purchase_soft", "软件采购", "purchase", 11),
    (2, "purchase_hw", "硬件采购", "purchase", 12),
    (2, "purchase_cloud", "云服务采购", "purchase", 13),
    (2, "purchase_svc", "服务采购", "purchase", 14),
    (2, "sales_svc", "服务销售", "sales", 21),
    (2, "sales_goods", "货物销售", "sales", 22),
    (2, "general_nda", "保密协议", "general", 31),
    (2, "general_lease", "租赁合同", "general", 32),
    (3, "tag_saas", "SaaS", "purchase_soft", 111),
    (3, "tag_framework", "年度框架", "purchase_svc", 141),
    (3, "tag_milestone", "按里程碑付款", "purchase_svc", 142),
    (3, "tag_source", "源代码交付", "purchase_soft", 112),
    (3, "tag_nda", "保密义务", "general_nda", 311),
    (3, "tag_bet", "对赌条款", "sales_svc", 211),
]


async def seed_tag_taxonomy(db: AsyncSession) -> None:
    existing = (await db.execute(select(TagTaxonomy).limit(1))).scalar_one_or_none()
    if existing:
        return
    code_to_id: dict[str, int] = {}
    for level, code, name, parent_code, sort_order in DEFAULT_TREE:
        parent_id = code_to_id.get(parent_code) if parent_code else None
        row = TagTaxonomy(
            level=level,
            code=code,
            name=name,
            parent_id=parent_id,
            sort_order=sort_order,
            is_active=True,
        )
        db.add(row)
        await db.flush()
        code_to_id[code] = row.id
    await db.commit()


async def list_tags(db: AsyncSession, *, active_only: bool = True) -> list[TagTaxonomy]:
    q = select(TagTaxonomy).order_by(TagTaxonomy.level, TagTaxonomy.sort_order, TagTaxonomy.id)
    if active_only:
        q = q.where(TagTaxonomy.is_active.is_(True))
    return list((await db.execute(q)).scalars().all())


def tags_to_tree(rows: list[TagTaxonomy]) -> list[dict]:
    by_id = {r.id: {"id": r.id, "level": r.level, "code": r.code, "name": r.name,
                    "parent_id": r.parent_id, "sort_order": r.sort_order,
                    "is_active": r.is_active, "children": []} for r in rows}
    roots: list[dict] = []
    for r in rows:
        node = by_id[r.id]
        if r.parent_id and r.parent_id in by_id:
            by_id[r.parent_id]["children"].append(node)
        else:
            roots.append(node)
    return roots


async def create_tag(
    db: AsyncSession,
    *,
    level: int,
    name: str,
    code: str = "",
    parent_id: int | None = None,
    sort_order: int = 0,
) -> TagTaxonomy:
    if level not in (1, 2, 3):
        raise ValueError("level 必须为 1/2/3")
    if level > 1 and not parent_id:
        raise ValueError("二级/三级标签必须指定父级")
    if parent_id:
        parent = await db.get(TagTaxonomy, parent_id)
        if not parent or not parent.is_active:
            raise ValueError("父级标签不存在")
        if parent.level != level - 1:
            raise ValueError("父级层级不匹配")
    row = TagTaxonomy(
        level=level,
        name=name.strip(),
        code=(code or name).strip()[:64],
        parent_id=parent_id,
        sort_order=sort_order,
        is_active=True,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def update_tag(db: AsyncSession, tag_id: int, data: dict) -> TagTaxonomy:
    row = await db.get(TagTaxonomy, tag_id)
    if not row:
        raise ValueError("标签不存在")
    for k in ("name", "code", "sort_order", "is_active", "parent_id"):
        if k in data and data[k] is not None:
            setattr(row, k, data[k])
    await db.commit()
    await db.refresh(row)
    return row


async def soft_delete_tag(db: AsyncSession, tag_id: int) -> None:
    row = await db.get(TagTaxonomy, tag_id)
    if not row:
        raise ValueError("标签不存在")
    row.is_active = False
    # soft-delete children
    children = (
        await db.execute(select(TagTaxonomy).where(TagTaxonomy.parent_id == tag_id))
    ).scalars().all()
    for c in children:
        c.is_active = False
        grand = (
            await db.execute(select(TagTaxonomy).where(TagTaxonomy.parent_id == c.id))
        ).scalars().all()
        for g in grand:
            g.is_active = False
    await db.commit()


async def validate_levels(db: AsyncSession, level1: str | None, level2: str | None) -> None:
    """Ensure L1/L2 names exist in active taxonomy when provided."""
    rows = await list_tags(db, active_only=True)
    l1_names = {r.name for r in rows if r.level == 1}
    if level1 and level1 not in l1_names:
        raise ValueError(f"一级标签「{level1}」不在标签体系中，请先在后台配置")
    if level2:
        l1 = next((r for r in rows if r.level == 1 and r.name == level1), None) if level1 else None
        l2_ok = any(
            r.level == 2 and r.name == level2 and (l1 is None or r.parent_id == l1.id)
            for r in rows
        )
        if not l2_ok:
            raise ValueError(f"二级标签「{level2}」不在标签体系中或不属于所选一级")
