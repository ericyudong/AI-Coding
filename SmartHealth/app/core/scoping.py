"""机构级数据隔离（行级权限）。

为什么院内私有化也必须要：
云边协同下同一平台的多个院区、多个数据中心共用一套服务，
如果不做行级隔离，A 院区的医生能查到 B 院区的病例 —— 这在医疗场景是事故级问题。

三种数据范围（User.data_scope）：
- `all`  ：全院可见（通常只给管理员与质控总负责人）
- `org`  ：仅本机构（同一法人实体下的多个科室）
- `site` ：仅本数据中心（最严格，用于多中心临床试验的盲态要求）

实现方式：不改 SQL 生成器、不做 ORM 全局过滤（那样难以排障）。
而是提供一个**显式的过滤器构造函数**，在接口里显式套用 ——
「看不见的权限逻辑」是生产事故的常见来源，宁可多写一行也要让它可读。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.asset import DataAsset, Slide

# 适用范围说明（前端展示用）
SCOPE_LABELS = {
    "all": "全院（全部机构与中心）",
    "org": "本机构（同一法人实体）",
    "site": "本数据中心（最严格）",
}


class ScopeError(PermissionError):
    """越权访问。映射为 403 并记审计。"""


def scope_of(user: dict[str, Any]) -> str:
    return str(user.get("data_scope") or "all")


def visible_site_codes(user: dict[str, Any]) -> list[str] | None:
    """返回该用户可见的数据中心列表；None 表示不限制。"""
    scope = scope_of(user)
    if scope == "all" or user.get("is_admin"):
        return None
    if scope == "site":
        return [user.get("site_code") or ""]
    return None  # org 级不按 site 过滤，按 org_code 过滤


def slide_condition(user: dict[str, Any]):
    """切片可见性条件（可直接放进 `select(...).where(...)`）。返回 None 表示不限制。"""
    scope = scope_of(user)
    if scope == "all" or user.get("is_admin"):
        return None
    if scope == "site":
        # site 级：无归属（空 site_code）的记录视为公共/系统数据，仍可见，
        # 否则新导入但未标注中心的数据会立刻"消失"，反而更难用。
        return or_(Slide.site_code == (user.get("site_code") or ""), Slide.site_code == "")
    org = user.get("org_code") or ""
    if not org:
        return None
    return or_(Slide.org_code == org, Slide.org_code == "")


def asset_condition(user: dict[str, Any]):
    scope = scope_of(user)
    if scope == "all" or user.get("is_admin"):
        return None
    if scope == "site":
        site = user.get("site_code") or ""
        return or_(DataAsset.site_codes.like(f"%{site}%"), DataAsset.site_codes == "")
    org = user.get("org_code") or ""
    if not org:
        return None
    return or_(DataAsset.org_code == org, DataAsset.org_code == "")


def assert_slide_access(db: Session, slide: Any, user: dict[str, Any]) -> None:
    """单条资源的越权校验。用于详情/更新/删除这类「按 id 直接访问」的接口。

    这类接口最容易被遗漏：列表过滤了，但 `/slides/123` 仍能直接拿到别人的数据。
    """
    if slide is None:
        raise ScopeError("切片不存在")
    scope = scope_of(user)
    if scope == "all" or user.get("is_admin"):
        return
    if scope == "site":
        slide_site = getattr(slide, "site_code", "") or ""
        if slide_site and slide_site != (user.get("site_code") or ""):
            raise ScopeError(f"切片 {getattr(slide, 'code', '')} 属于 {slide_site}，"
                             f"你的数据范围为 {SCOPE_LABELS['site']}，无权访问")
        return
    org = user.get("org_code") or ""
    if not org:
        return
    slide_org = getattr(slide, "org_code", "") or ""
    if slide_org and slide_org != org:
        raise ScopeError(f"切片 {getattr(slide, 'code', '')} 属于其他机构，无权访问")


def job_condition(user: dict[str, Any]):
    """作业可见性：本人提交的 + 本机构的 + 无归属的（系统任务）。"""
    from app.models.job import AsyncJob

    scope = scope_of(user)
    if scope == "all" or user.get("is_admin"):
        return None
    conditions = [AsyncJob.created_by == user.get("username", ""), AsyncJob.org_code == ""]
    org = user.get("org_code") or ""
    if org:
        conditions.append(AsyncJob.org_code == org)
    return or_(*conditions)


def describe(user: dict[str, Any]) -> dict[str, Any]:
    """把当前用户的隔离口径说清楚，前端在页头展示 —— 让用户知道自己在看什么范围的数据。"""
    scope = scope_of(user)
    return {
        "scope": scope,
        "label": SCOPE_LABELS.get(scope, scope),
        "org_code": user.get("org_code") or "",
        "site_code": user.get("site_code") or "",
        "is_unrestricted": scope == "all" or bool(user.get("is_admin")),
        "note": ("当前账号可查看全部数据" if scope == "all" or user.get("is_admin")
                 else f"当前账号仅可查看{SCOPE_LABELS.get(scope, scope)}的数据；"
                      "超出范围的记录不会出现在列表里，直接按 ID 访问会返回 403。"),
    }
