"""统一响应体与分页工具。

约定：所有接口返回 {code, message, data}，code=0 表示成功。
前端 views.js 依据该结构做统一解包与错误提示。
"""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    data: Any = None


def ok(data: Any = None, message: str = "ok") -> dict:
    return {"code": 0, "message": message, "data": data}


def fail(message: str, code: int = 1, data: Any = None, status_code: int = 400) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"code": code, "message": message, "data": data})


class PageMeta(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int


def paginate(items: list, total: int, page: int, page_size: int) -> dict:
    pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    return {
        "items": items,
        "meta": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
        },
    }
