"""Multi-modal contract search: keyword, semantic, field, regex, hybrid, natural."""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import date, timedelta
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cms_models import ManagedContract
from app.services import embedding_service, retrieval_service, vector_store

logger = logging.getLogger(__name__)

STATUS_ALIASES: dict[str, str] = {
    "履行中": "active",
    "active": "active",
    "待签署": "pending_sign",
    "pending_sign": "pending_sign",
    "已到期": "expired",
    "expired": "expired",
    "已归档": "archived",
    "archived": "archived",
    "已终止": "terminated",
    "terminated": "terminated",
}

TYPE_ALIASES: dict[str, str] = {
    "采购": "purchase",
    "采购合同": "purchase",
    "purchase": "purchase",
    "销售": "sales",
    "销售合同": "sales",
    "sales": "sales",
    "租赁": "lease",
    "租赁合同": "lease",
    "lease": "lease",
    "劳务": "labor",
    "labor": "labor",
    "保密": "nda",
    "保密协议": "nda",
    "nda": "nda",
    "技术开发": "tech",
    "tech": "tech",
    "其他": "other",
    "other": "other",
}

FIELD_ALIASES: dict[str, str] = {
    "金额": "amount",
    "amount": "amount",
    "状态": "status",
    "status": "status",
    "类型": "contract_type",
    "合同类型": "contract_type",
    "contract_type": "contract_type",
    "甲方": "party_a",
    "party_a": "party_a",
    "乙方": "party_b",
    "party_b": "party_b",
    "编号": "code",
    "合同编号": "code",
    "code": "code",
    "名称": "name",
    "合同名称": "name",
    "name": "name",
    "负责人": "owner",
    "owner": "owner",
    "风险": "risk_level",
    "risk_level": "risk_level",
}

OP_ALIASES: dict[str, str] = {
    "=": "eq",
    "==": "eq",
    "eq": "eq",
    "等于": "eq",
    "包含": "contains",
    "contains": "contains",
    "like": "contains",
    ">": "gt",
    "gt": "gt",
    "大于": "gt",
    ">=": "gte",
    "gte": "gte",
    "大于等于": "gte",
    "<": "lt",
    "lt": "lt",
    "小于": "lt",
    "<=": "lte",
    "lte": "lte",
    "小于等于": "lte",
    "regex": "regex",
    "正则": "regex",
}

STRUCTURED_RE = re.compile(
    r"([^\s=<>!]+?)\s*(=|==|>=|<=|>|<|包含|等于|大于等于|小于等于|大于|小于|regex|正则)\s*([^&|]+?)(?=\s+(?:AND|OR|且|或)\s+|$)",
    re.IGNORECASE,
)

REGEX_PREFIX_RE = re.compile(r"^(?:合同编号|编号|code)\s*[:：]\s*(.+)$", re.IGNORECASE)


def _parse_amount(value: str) -> float | None:
    text = value.strip().replace(",", "").replace("，", "")
    m = re.match(r"^([\d.]+)\s*万$", text)
    if m:
        return float(m.group(1)) * 10000
    m = re.match(r"^([\d.]+)\s*元?$", text)
    if m:
        return float(m.group(1))
    return None


def _normalize_field(field: str) -> str:
    key = field.strip()
    return FIELD_ALIASES.get(key, key)


def _normalize_operator(op: str) -> str:
    return OP_ALIASES.get(op.strip().lower(), op.strip().lower())


def _normalize_filter_value(field: str, value: str) -> str:
    val = value.strip().strip('"').strip("'")
    if field == "status":
        return STATUS_ALIASES.get(val, val)
    if field == "contract_type":
        return TYPE_ALIASES.get(val, val)
    if field == "amount":
        parsed = _parse_amount(val)
        if parsed is not None:
            return str(parsed)
    return val


def parse_structured_query(q: str) -> list[dict[str, str]]:
    filters: list[dict[str, str]] = []
    for m in STRUCTURED_RE.finditer(q):
        field = _normalize_field(m.group(1))
        op = _normalize_operator(m.group(2))
        value = _normalize_filter_value(field, m.group(3))
        filters.append({"field": field, "operator": op, "value": value})
    return filters


def parse_natural_language_rules(q: str) -> tuple[list[dict[str, str]], str]:
    """Rule-based NL parsing. Returns (filters, remaining_keywords)."""
    text = q.strip()
    filters: list[dict[str, str]] = []
    remaining = text

    type_patterns = [
        (r"采购合同?", "purchase"),
        (r"销售合同?", "sales"),
        (r"租赁合同?", "lease"),
        (r"保密协议?", "nda"),
        (r"技术开发合同?", "tech"),
        (r"劳务合同?", "labor"),
    ]
    for pattern, ctype in type_patterns:
        if re.search(pattern, text):
            filters.append({"field": "contract_type", "operator": "eq", "value": ctype})
            remaining = re.sub(pattern, " ", remaining)

    if re.search(r"去年(签订|签署|签)", text):
        year = date.today().year - 1
        filters.append({"field": "sign_date_year", "operator": "eq", "value": str(year)})
        remaining = re.sub(r"去年(签订|签署|签)", " ", remaining)

    m = re.search(r"金额\s*(?:超过|大于|高于|>=?)\s*([\d.]+)\s*万", text)
    if m:
        filters.append({"field": "amount", "operator": "gt", "value": str(float(m.group(1)) * 10000)})
        remaining = re.sub(r"金额\s*(?:超过|大于|高于|>=?)\s*[\d.]+\s*万", " ", remaining)

    m = re.search(r"金额\s*(?:低于|小于|不超过|<=?)\s*([\d.]+)\s*万", text)
    if m:
        filters.append({"field": "amount", "operator": "lt", "value": str(float(m.group(1)) * 10000)})
        remaining = re.sub(r"金额\s*(?:低于|小于|不超过|<=?)\s*[\d.]+\s*万", " ", remaining)

    for label, status in STATUS_ALIASES.items():
        if label in ("active", "pending_sign", "expired", "archived", "terminated"):
            continue
        if label in text:
            filters.append({"field": "status", "operator": "eq", "value": status})
            remaining = remaining.replace(label, " ")
            break

    remaining = re.sub(r"\s+", " ", remaining).strip()
    remaining = re.sub(r"(的|且|和|并|找|查询|搜索|哪些|合同)$", "", remaining).strip()
    return filters, remaining


async def parse_natural_language(q: str) -> tuple[list[dict[str, str]], str]:
    filters, remaining = parse_natural_language_rules(q)
    if filters:
        return filters, remaining or q

    from app.services.llm_service import parse_search_natural_language

    llm_filters, llm_kw = await parse_search_natural_language(q)
    if llm_filters:
        return llm_filters, llm_kw or q
    return [], q


def _apply_filter_clause(column, operator: str, value: str):
    op = _normalize_operator(operator)
    if op == "eq":
        return column == value
    if op == "contains":
        return column.ilike(f"%{value}%")
    if op == "gt":
        return column > float(value)
    if op == "gte":
        return column >= float(value)
    if op == "lt":
        return column < float(value)
    if op == "lte":
        return column <= float(value)
    if op == "regex":
        return None  # handled in Python post-filter
    return column.ilike(f"%{value}%")


def _scope_query(query, user_id: int, user=None):
    if user is not None:
        from app.core.access import contract_scope_filter

        return contract_scope_filter(query, user)
    return query.where(ManagedContract.user_id == user_id)


def _build_filter_query(user_id: int, filters: list[dict[str, str]], user=None):
    query = _scope_query(select(ManagedContract), user_id, user)
    clauses = []
    for f in filters:
        field = _normalize_field(f["field"])
        op = _normalize_operator(f["operator"])
        value = _normalize_filter_value(field, f["value"])
        if field == "sign_date_year":
            year = int(value)
            start = date(year, 1, 1)
            end = date(year, 12, 31)
            clauses.append(and_(ManagedContract.sign_date >= start, ManagedContract.sign_date <= end))
            continue
        col = getattr(ManagedContract, field, None)
        if col is None:
            continue
        if field == "amount":
            clauses.append(_apply_filter_clause(col, op, value))
        elif field in ("status", "contract_type", "risk_level") and op == "eq":
            clauses.append(col == value)
        elif op == "regex":
            continue
        else:
            clauses.append(_apply_filter_clause(col, op, value))
    if clauses:
        query = query.where(and_(*clauses))
    return query.order_by(ManagedContract.updated_at.desc())


def _highlight_text(text: str, terms: list[str], max_len: int = 160) -> str:
    if not text:
        return "（暂无正文摘要）"
    snippet = text
    idx = 0
    for term in terms:
        if not term:
            continue
        pos = text.find(term)
        if pos >= 0:
            idx = pos
            break
    if idx > 0:
        snippet = text[max(0, idx - 30) : idx + max_len]
    else:
        snippet = text[:max_len]
    for term in sorted({t for t in terms if t}, key=len, reverse=True):
        if term in snippet:
            snippet = snippet.replace(term, f"**{term}**")
    if len(text) > len(snippet):
        snippet = f"...{snippet}..."
    return snippet


def _extract_terms(q: str) -> list[str]:
    terms = [t for t in re.split(r"[\s,，、]+", q) if len(t) >= 2]
    return terms or ([q] if q else [])


async def field_search(
    db: AsyncSession,
    user_id: int,
    filters: list[dict[str, str]],
    limit: int = 50,
    user=None,
) -> list[dict]:
    if not filters:
        return []
    regex_filters = [f for f in filters if _normalize_operator(f["operator"]) == "regex"]
    sql_filters = [f for f in filters if _normalize_operator(f["operator"]) != "regex"]
    query = _build_filter_query(user_id, sql_filters, user=user) if sql_filters else (
        _scope_query(select(ManagedContract), user_id, user).order_by(ManagedContract.updated_at.desc())
    )
    result = await db.execute(query.limit(max(limit * 5, 100)))
    contracts = list(result.scalars().all())
    if regex_filters:
        for rf in regex_filters:
            field = _normalize_field(rf["field"])
            pattern = rf["value"]
            try:
                compiled = re.compile(pattern, re.IGNORECASE)
            except re.error:
                continue
            contracts = [
                c
                for c in contracts
                if compiled.search(str(getattr(c, field, "") or ""))
            ]
    contracts = contracts[:limit]
    items = []
    for i, c in enumerate(contracts):
        items.append(
            {
                "contract": c,
                "relevance": max(55.0, 92.0 - i * 3),
                "highlight": _highlight_text(c.content_text or c.name, []),
                "match_type": "field",
            }
        )
    return items


async def keyword_search(
    db: AsyncSession,
    user_id: int,
    q: str,
    limit: int = 50,
    user=None,
) -> list[dict]:
    terms = _extract_terms(q)
    if not terms:
        return []

    clauses = []
    for term in terms:
        like = f"%{term}%"
        clauses.append(
            or_(
                ManagedContract.name.ilike(like),
                ManagedContract.code.ilike(like),
                ManagedContract.party_a.ilike(like),
                ManagedContract.party_b.ilike(like),
                ManagedContract.tags_json.ilike(like),
                ManagedContract.content_text.ilike(like),
            )
        )
    query = (
        _scope_query(select(ManagedContract), user_id, user)
        .where(and_(*clauses))
        .order_by(ManagedContract.updated_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    contracts = list(result.scalars().all())
    items = []
    for i, c in enumerate(contracts):
        items.append(
            {
                "contract": c,
                "relevance": max(50.0, 88.0 - i * 4),
                "highlight": _highlight_text(c.content_text or c.name, terms),
                "match_type": "keyword",
            }
        )
    return items


async def regex_search(
    db: AsyncSession,
    user_id: int,
    pattern: str,
    limit: int = 50,
    user=None,
) -> list[dict]:
    m = REGEX_PREFIX_RE.match(pattern.strip())
    regex = m.group(1).strip() if m else pattern.strip()
    try:
        compiled = re.compile(regex, re.IGNORECASE)
    except re.error as e:
        raise ValueError(f"正则表达式无效: {e}") from e

    result = await db.execute(
        _scope_query(select(ManagedContract), user_id, user)
        .order_by(ManagedContract.updated_at.desc())
        .limit(300)
    )
    contracts = [
        c
        for c in result.scalars().all()
        if compiled.search(c.code or "") or compiled.search(c.name or "") or compiled.search(c.content_text or "")
    ][:limit]

    items = []
    for i, c in enumerate(contracts):
        items.append(
            {
                "contract": c,
                "relevance": max(60.0, 95.0 - i * 2),
                "highlight": _highlight_text(c.code or c.name, [regex[:8]]),
                "match_type": "regex",
            }
        )
    return items


def _fuse_results(lists: list[list[dict]], weights: list[float], limit: int) -> list[dict]:
    fused: dict[int, dict[str, Any]] = {}
    for weight, items in zip(weights, lists):
        for rank, item in enumerate(items):
            c = item["contract"]
            cid = c.id
            score = weight * (1.0 / (rank + 1))
            if cid not in fused:
                fused[cid] = {
                    "contract": c,
                    "score": score,
                    "highlight": item.get("highlight", ""),
                    "match_types": {item.get("match_type", "unknown")},
                }
            else:
                fused[cid]["score"] += score
                fused[cid]["match_types"].add(item.get("match_type", "unknown"))
                if len(item.get("highlight", "")) > len(fused[cid]["highlight"]):
                    fused[cid]["highlight"] = item["highlight"]

    merged = sorted(fused.values(), key=lambda x: -x["score"])
    items = []
    max_score = merged[0]["score"] if merged else 1.0
    for row in merged[:limit]:
        rel = round(min(99.0, (row["score"] / max_score) * 98), 1)
        items.append(
            {
                "contract": row["contract"],
                "relevance": rel,
                "highlight": row["highlight"],
                "match_type": "+".join(sorted(row["match_types"])),
            }
        )
    return items


def _build_ai_suggestion(q: str, items: list[dict], mode: str) -> str | None:
    if not items:
        return None
    if "保密" in q:
        return f"您是否在查找涉及保密义务的合同？共找到 {len(items)} 份相关合同，建议优先审查高风险合同。"
    if mode == "natural":
        return f"已按自然语言条件解析并检索，共找到 {len(items)} 份匹配合同。"
    if mode == "hybrid":
        return f"已通过关键词、语义与字段多路召回融合排序，共 {len(items)} 条结果。"
    return None


async def multi_modal_search(
    db: AsyncSession,
    user_id: int,
    *,
    q: str = "",
    mode: str = "hybrid",
    filters: list[dict[str, str]] | None = None,
    limit: int = 50,
    user=None,
) -> dict:
    start = time.perf_counter()
    q = (q or "").strip()
    filters = list(filters or [])
    interpreted_query = q
    mode = (mode or "hybrid").lower()

    if mode == "natural" and q:
        nl_filters, kw = await parse_natural_language(q)
        filters.extend(nl_filters)
        interpreted_query = kw or q
        mode = "hybrid"

    if not filters and q and mode in ("field", "hybrid"):
        parsed = parse_structured_query(q)
        if parsed:
            filters.extend(parsed)

    if mode == "field" and filters:
        items = await field_search(db, user_id, filters, limit, user=user)
    elif mode == "regex":
        if not q:
            raise ValueError("正则检索需要提供表达式")
        items = await regex_search(db, user_id, q, limit, user=user)
    elif mode == "keyword":
        items = await keyword_search(db, user_id, q or interpreted_query, limit, user=user)
        if not items and q:
            items = await retrieval_service.keyword_search_in_content(db, user_id, q, limit, user=user)
    elif mode == "semantic":
        items = await retrieval_service.semantic_search_contracts(db, user_id, q or interpreted_query, user=user)
        if not items:
            items = await keyword_search(db, user_id, q or interpreted_query, limit, user=user)
    elif mode == "hybrid":
        kw_items = await keyword_search(db, user_id, q or interpreted_query, limit, user=user) if (q or interpreted_query) else []
        sem_items = (
            await retrieval_service.semantic_search_contracts(db, user_id, q or interpreted_query, user=user)
            if (q or interpreted_query)
            else []
        )
        field_items = await field_search(db, user_id, filters, limit, user=user) if filters else []
        if not kw_items and not sem_items and not field_items and (q or interpreted_query):
            kw_items = await retrieval_service.keyword_search_in_content(
                db, user_id, q or interpreted_query, limit, user=user
            )
        lists = [x for x in [kw_items, sem_items, field_items] if x]
        weights = [1.0, 1.2, 1.1][: len(lists)]
        items = _fuse_results(lists, weights, limit) if lists else []
    else:
        items = await keyword_search(db, user_id, q, limit, user=user)

    if filters and mode not in ("field", "hybrid"):
        allowed = {
            c.id
            for c in (await db.execute(_build_filter_query(user_id, filters, user=user).limit(500))).scalars().all()
        }
        items = [i for i in items if i["contract"].id in allowed]

    suggestion = _build_ai_suggestion(q or interpreted_query, items, mode)
    elapsed = int((time.perf_counter() - start) * 1000) or 1
    return {
        "items": items[:limit],
        "total": len(items[:limit]),
        "elapsed_ms": elapsed,
        "ai_suggestion": suggestion,
        "mode": mode,
        "interpreted_query": interpreted_query,
        "applied_filters": filters,
    }


async def search_suggestions(db: AsyncSession, user_id: int, q: str = "", limit: int = 8, user=None) -> dict:
    q = (q or "").strip()
    suggestions: list[str] = []
    contracts: list[str] = []

    if q:
        like = f"%{q}%"
        result = await db.execute(
            _scope_query(select(ManagedContract.name, ManagedContract.code), user_id, user)
            .where(or_(ManagedContract.name.ilike(like), ManagedContract.code.ilike(like)))
            .order_by(ManagedContract.updated_at.desc())
            .limit(limit)
        )
        for name, code in result.all():
            contracts.append(f"{code} · {name}")

        if "保密" in q or "保密".startswith(q):
            suggestions.append("哪些合同涉及保密义务")
        if "违约" in q:
            suggestions.append("保密条款 违约金")
        if "采购" in q:
            suggestions.append("去年签订且金额超过50万的采购合同")
        if re.search(r"ct|CT|编号", q, re.I):
            suggestions.append("合同编号:CT-\\d{8}")
    else:
        suggestions = [
            "哪些合同涉及保密义务",
            "保密条款 违约金",
            "金额>100万 AND 状态=履行中",
            "去年签订且金额超过50万的采购合同",
            "包含自动续签条款的租赁合同",
        ]

    return {"suggestions": suggestions, "contracts": contracts}
