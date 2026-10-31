"""API 层通用工具：统一响应、分页、搜索过滤、通用 CRUD 路由器工厂。

设计目标：14 个业务模块的列表/详情/更新接口形态高度一致，
用一个工厂生成可以让每个模块的代码量从数百行降到十几行，
把注意力留给真正有业务逻辑的接口（如 Agent 会话、评测运行、许可体检）。
"""

from __future__ import annotations

import json
from typing import Any, Callable, Iterable, Sequence

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from sqlalchemy import String, and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, DbSession, audit, require
from app.core.response import ok, paginate


def _coerce_filter(column: Any, raw: str) -> Any:
    """把 URL 查询字符串转换为与列类型匹配的 Python 值。

    SQLite 下 Boolean 列以 0/1 存储，若直接传 "true" 会静默不匹配；
    数值列传字符串在部分方言下也不会隐式转换。这里统一做一次显式转换。
    """
    from sqlalchemy import Boolean as _Boolean, Float as _Float, Integer as _Integer

    try:
        python_type = column.type.python_type
    except Exception:
        return raw
    if python_type is bool:
        return raw.strip().lower() in ("1", "true", "yes", "y", "是")
    if python_type is int:
        try:
            return int(raw)
        except (TypeError, ValueError):
            return raw
    if python_type is float:
        try:
            return float(raw)
        except (TypeError, ValueError):
            return raw
    return raw


def want_async(payload: dict | None) -> bool:
    """业务接口是否走异步作业。

    默认异步（settings.job_async_default）：长任务不能挂在 HTTP 请求里。
    显式传 sync=true 才同步执行 —— 这在自动化测试、小数据集排障、以及
    "我只想立刻看到结果" 的交互场景下是需要的。
    """
    from app.core.config import settings

    if payload and str(payload.get("sync")).strip().lower() in ("1", "true", "yes"):
        return False
    return bool(settings.job_async_default)


def job_brief(job: Any) -> dict:
    """提交作业后返回给前端的作业句柄（刻意只给必要字段）。"""
    if job is None:
        return {}
    return {
        "id": job.id,
        "code": job.code,
        "type": job.job_type,
        "type_label": getattr(job, "type_label", job.job_type),
        "title": job.title,
        "status": job.status,
        "status_label": getattr(job, "status_label", job.status),
        "progress": job.progress,
        "poll_url": f"/api/v1/jobs/{job.id}/progress",
    }


def _loads(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def serialize(row: Any, json_fields: Sequence[str] = (), extra: dict[str, Any] | None = None,
              exclude: Sequence[str] = ()) -> dict[str, Any]:
    """ORM -> dict，并把指定的 Text 字段反序列化为 JSON。"""
    if row is None:
        return {}
    payload = row.to_dict(exclude=tuple(exclude))
    for field in json_fields:
        if field in payload:
            key = field[:-5] if field.endswith("_json") else field
            payload[f"{key}_parsed" if field.endswith("_json") else key] = _loads(payload[field], None)
    if extra:
        payload.update(extra)
    return payload


def list_query(
    db: Session,
    model: Any,
    *,
    page: int = 1,
    page_size: int = 20,
    search: str = "",
    search_fields: Sequence[Any] = (),
    filters: dict[str, Any] | None = None,
    date_field: Any = None,
    date_from: str = "",
    date_to: str = "",
    order_by: Any = None,
    descending: bool = True,
) -> tuple[list[Any], int]:
    stmt = select(model)
    conditions = []
    if filters:
        for column, value in filters.items():
            if value is None or value == "":
                continue
            conditions.append(column == value)
    if search and search_fields:
        pattern = f"%{search.strip()}%"
        conditions.append(or_(*[field.like(pattern) for field in search_fields]))
    if date_field is not None:
        if date_from:
            conditions.append(date_field >= date_from)
        if date_to:
            conditions.append(date_field <= date_to)
    if conditions:
        stmt = stmt.where(and_(*conditions))

    total = int(db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0)
    if order_by is not None:
        stmt = stmt.order_by(order_by.desc() if descending else order_by.asc())
    stmt = stmt.offset(max(page - 1, 0) * page_size).limit(page_size)
    return list(db.execute(stmt).scalars()), total


def crud_router(
    *,
    model: Any,
    prefix: str,
    tag: str,
    permission_read: str,
    permission_write: str | None = None,
    search_fields: Sequence[str] = (),
    filter_fields: Sequence[str] = (),
    json_fields: Sequence[str] = (),
    order_by: str = "id",
    list_serializer: Callable[[Any, Session], dict[str, Any]] | None = None,
    detail_serializer: Callable[[Any, Session], dict[str, Any]] | None = None,
    editable_fields: Sequence[str] | None = None,
    create_fields: Sequence[str] | None = None,
    resource_type: str = "",
    summary_template: str = "",
    allow_create: bool = True,
    allow_delete: bool = False,
    list_condition: Callable[[Any], Any] | None = None,
    scope_condition: Callable[[dict], Any] | None = None,
) -> APIRouter:
    """`scope_condition(user)` 用于机构级行级隔离：返回一个 SQLAlchemy 条件或 None。

    它是显式的、必须由每个资源自行声明的 —— 默认不隔离即意味着"漏配就串数据"，
    所以对涉及机构数据的资源应当逐个确认。
    """
    """生成一个标准 CRUD 路由器。

    - GET  {prefix}          列表（分页 + 关键字 + 字段过滤 + 日期区间）
    - GET  {prefix}/{id}     详情
    - POST {prefix}          新建（可选）
    - PATCH {prefix}/{id}    局部更新（可选，写审计链）
    - DELETE {prefix}/{id}   删除（默认关闭；业务数据的删除应在业务接口里带校验）
    """
    router = APIRouter(prefix=prefix, tags=[tag])
    columns = {c.key: c for c in model.__table__.columns}
    resource = resource_type or tag

    @router.get("", summary=f"{tag}列表")
    def list_items(
        request: Request,
        db: DbSession,
        user: dict = Depends(require(permission_read)),
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=200),
        search: str = Query("", description="关键字（在 search_fields 上模糊匹配）"),
        date_from: str = Query("", description="起始日期（取 created_at）"),
        date_to: str = Query("", description="结束日期（取 created_at）"),
        order_desc: bool = Query(True),
    ) -> dict:
        # 过滤字段以 Query 参数形式传入（如 ?status=active&site_code=SITE-A）。
        # 用 request.query_params 读取而非签名中的 **kwargs：FastAPI 不支持 **kwargs
        # 作为任意查询参数，会把 kwargs 本身当成一个必填参数。
        query_params = request.query_params
        filters = {}
        for name in filter_fields:
            value = query_params.get(name)
            if value not in (None, ""):
                column = columns.get(name)
                if column is not None:
                    filters[column] = _coerce_filter(column, value)
        scope_where = scope_condition(user) if scope_condition is not None else None
        if list_condition is not None or scope_where is not None:
            filters["__custom__"] = True
        items, total = list_query(
            db, model, page=page, page_size=page_size, search=search,
            search_fields=[columns[f] for f in search_fields if f in columns],
            filters={k: v for k, v in filters.items() if k != "__custom__"},
            date_field=columns.get("created_at"),
            date_from=date_from, date_to=date_to,
            order_by=columns.get(order_by), descending=order_desc,
        )
        if list_condition is not None or scope_where is not None:
            stmt = select(model)
            if list_condition is not None:
                stmt = stmt.where(list_condition(model))
            if scope_where is not None:
                stmt = stmt.where(scope_where)
            total = int(db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0)
            stmt = stmt.order_by(columns[order_by].desc() if order_desc else columns[order_by].asc())
            items = list(db.execute(stmt.offset(max(page - 1, 0) * page_size).limit(page_size)).scalars())
        serializer = list_serializer or (lambda row, _db: serialize(row, json_fields))
        return ok(paginate([serializer(row, db) for row in items], total, page, page_size))

    @router.get("/{item_id:int}", summary=f"{tag}详情")
    def get_item(item_id: int, db: DbSession,
                 user: dict = Depends(require(permission_read))) -> dict:
        row = db.get(model, item_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"{tag} #{item_id} 不存在")
        # 详情也必须过隔离：列表过滤了但 /xxx/123 仍能直取，是最常见的越权漏洞
        if scope_condition is not None:
            scope_where = scope_condition(user)
            if scope_where is not None:
                visible = db.execute(
                    select(model.id).where(model.id == item_id, scope_where)
                ).scalar_one_or_none()
                if visible is None:
                    raise HTTPException(status_code=403,
                                        detail="该记录不在你的数据可见范围内（机构级隔离）")
        serializer = detail_serializer or (lambda r, _db: serialize(r, json_fields))
        return ok(serializer(row, db))

    if allow_create and permission_write:
        @router.post("", summary=f"新建{tag}", status_code=201)
        def create_item(db: DbSession, payload: dict = Body(...),
                        user: dict = Depends(require(permission_write))) -> dict:
            allowed = set(create_fields) if create_fields else set(columns)
            data = {k: v for k, v in payload.items() if k in allowed and k in columns}
            data.pop("id", None)
            row = model(**data)
            db.add(row)
            db.flush()
            audit(db, user, action=f"create_{resource}", resource_type=resource,
                  resource_id=row.id,
                  summary=(summary_template.format(row=row) if summary_template
                           else f"新建{tag} #{row.id}"),
                  payload={"payload": payload})
            db.commit()
            return ok(serialize(row, json_fields))

    if permission_write:
        @router.patch("/{item_id:int}", summary=f"更新{tag}")
        def update_item(db: DbSession, item_id: int, payload: dict = Body(...),
                        user: dict = Depends(require(permission_write))) -> dict:
            row = db.get(model, item_id)
            if row is None:
                raise HTTPException(status_code=404, detail=f"{tag} #{item_id} 不存在")
            allowed = tuple(editable_fields) if editable_fields else tuple(columns)
            changed = row.update_from(payload, allowed=allowed)
            db.flush()
            audit(db, user, action=f"update_{resource}", resource_type=resource,
                  resource_id=row.id,
                  summary=(summary_template.format(row=row) if summary_template
                           else f"更新{tag} #{row.id}"),
                  payload={"changed": changed, "payload": payload})
            db.commit()
            return ok(serialize(row, json_fields))

    if allow_delete and permission_write:
        @router.delete("/{item_id:int}", summary=f"删除{tag}")
        def delete_item(db: DbSession, item_id: int,
                        user: dict = Depends(require(permission_write))) -> dict:
            row = db.get(model, item_id)
            if row is None:
                raise HTTPException(status_code=404, detail=f"{tag} #{item_id} 不存在")
            db.delete(row)
            audit(db, user, action=f"delete_{resource}", resource_type=resource, resource_id=item_id,
                  summary=f"删除{tag} #{item_id}", risk_level="attention")
            db.commit()
            return ok({"deleted": item_id})

    return router
