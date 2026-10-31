"""ORM 基类与通用混入。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.inspection import inspect as sa_inspect

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    return value


class TimestampMixin:
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class BaseModel(Base, TimestampMixin):
    """统一主键 + 时间戳 + to_dict 序列化。"""

    __abstract__ = True

    id = Column(Integer, primary_key=True, autoincrement=True)

    def to_dict(self, exclude: tuple[str, ...] = (), include: tuple[str, ...] | None = None) -> dict[str, Any]:
        mapper = sa_inspect(type(self))
        result: dict[str, Any] = {}
        for column in mapper.columns:
            name = column.key
            if name in exclude:
                continue
            if include is not None and name not in include:
                continue
            result[name] = iso(getattr(self, name, None))
        return result

    @classmethod
    def column_names(cls) -> list[str]:
        return [c.key for c in sa_inspect(cls).columns]

    def update_from(self, payload: dict[str, Any], allowed: tuple[str, ...] | None = None) -> list[str]:
        """按字段白名单做局部更新，返回实际变更的字段名。"""
        changed: list[str] = []
        columns = set(self.column_names())
        for key, value in payload.items():
            if key in {"id", "created_at", "updated_at"}:
                continue
            if key not in columns:
                continue
            if allowed is not None and key not in allowed:
                continue
            if getattr(self, key) != value:
                setattr(self, key, value)
                changed.append(key)
        return changed


class CodeNameMixin:
    """带唯一业务编码与名称的实体通用字段。"""

    code = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(160), nullable=False)
    description = Column(String(1024), default="")
