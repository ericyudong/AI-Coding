"""Retrieve relevant contract chunks for search and RAG."""
import re

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.cms_models import ContractChunk, ManagedContract
from app.services import embedding_service, vector_store

_QUERY_SYNONYMS: dict[str, list[str]] = {
    "合同金额": ["金额", "服务费用", "费用", "人民币", "含税", "总价", "Token"],
    "金额": ["服务费用", "费用", "人民币", "含税", "总价"],
    "付款": ["支付", "发票", "结算", "费用及支付"],
    "违约": ["违约金", "违约责任"],
    "到期": ["期限", "届满", "有效期", "服务期"],
}


def _expand_query_keywords(question: str) -> list[str]:
    q = question.replace("？", "").replace("?", "").strip()
    keywords: list[str] = []
    if len(q) >= 2:
        keywords.append(q)
    for part in re.split(r"[，。、；\s]+", q):
        if len(part) >= 2:
            keywords.append(part)
    for key, synonyms in _QUERY_SYNONYMS.items():
        if key in q:
            keywords.extend(synonyms)
    return list(dict.fromkeys(keywords))


async def retrieve_chunks_for_contract(
    db: AsyncSession,
    contract: ManagedContract,
    question: str,
    top_k: int | None = None,
) -> list[ContractChunk]:
    settings = get_settings()
    k = top_k or settings.rag_top_k
    contract_id = contract.id

    query_vec = await embedding_service.embed_query(question)
    if query_vec and vector_store.is_vector_store_available():
        hits = vector_store.search_vectors(
            query_vec,
            user_id=contract.user_id,
            top_k=k,
            contract_id=contract_id,
        )
        if hits:
            hit_ids = [h.vector_id for h in hits]
            result = await db.execute(
                select(ContractChunk).where(
                    ContractChunk.contract_id == contract_id,
                    ContractChunk.vector_id.in_(hit_ids),
                )
            )
            chunks = list(result.scalars().all())
            order = {vid: i for i, vid in enumerate(hit_ids)}
            chunks.sort(key=lambda c: order.get(c.vector_id, 999))
            return chunks[:k]

    # Keyword fallback within contract
    keywords = _expand_query_keywords(question)
    result = await db.execute(
        select(ContractChunk)
        .where(ContractChunk.contract_id == contract_id)
        .order_by(ContractChunk.chunk_index)
    )
    all_chunks = list(result.scalars().all())
    if not all_chunks:
        return []

    scored: list[tuple[int, ContractChunk]] = []
    for ch in all_chunks:
        score = sum(1 for kw in keywords if kw in ch.content)
        if score > 0:
            scored.append((score, ch))
    if scored:
        scored.sort(key=lambda x: -x[0])
        return [c for _, c in scored[:k]]

    return all_chunks[:k]


async def semantic_search_contracts(
    db: AsyncSession,
    user_id: int,
    q: str,
    top_k: int | None = None,
    user=None,
) -> list[dict]:
    """Return [{contract, relevance, highlight, chunk}] sorted by score."""
    settings = get_settings()
    k = top_k or settings.semantic_search_top_k

    query_vec = await embedding_service.embed_query(q)
    if not query_vec or not vector_store.is_vector_store_available():
        return []

    from app.core.access import visible_contract_ids
    from app.core.roles import can_access_all_data

    scope_user_id: int | None = user_id
    allowed: set[int] | None = None
    if user is not None:
        if can_access_all_data(user.role):
            scope_user_id = None
        else:
            allowed = await visible_contract_ids(db, user)
            scope_user_id = None if allowed is not None else user_id

    hits = vector_store.search_vectors(query_vec, user_id=scope_user_id, top_k=k * 3)
    if not hits:
        return []
    if allowed is not None:
        hits = [h for h in hits if h.contract_id in allowed]

    best: dict[int, dict] = {}
    for h in hits:
        if h.contract_id not in best or h.score > best[h.contract_id]["score"]:
            snippet = h.content[:120] + ("..." if len(h.content) > 120 else "")
            best[h.contract_id] = {
                "contract_id": h.contract_id,
                "score": h.score,
                "highlight": f"...{snippet}...",
                "section": h.section_title,
            }

    ids = list(best.keys())
    query = select(ManagedContract).where(ManagedContract.id.in_(ids))
    if user is not None:
        from app.core.access import contract_scope_filter

        query = contract_scope_filter(query, user)
    else:
        query = query.where(ManagedContract.user_id == user_id)
    result = await db.execute(query)
    contracts = {c.id: c for c in result.scalars().all()}

    items = []
    for cid, meta in sorted(best.items(), key=lambda x: -x[1]["score"]):
        c = contracts.get(cid)
        if not c:
            continue
        items.append(
            {
                "contract": c,
                "relevance": round(min(99.0, meta["score"] * 100), 1),
                "highlight": meta["highlight"],
            }
        )
    return items[:k]


async def keyword_search_in_content(
    db: AsyncSession,
    user_id: int,
    q: str,
    limit: int = 50,
    user=None,
) -> list[dict]:
    like = f"%{q}%"
    query = select(ManagedContract)
    if user is not None:
        from app.core.access import contract_scope_filter

        query = contract_scope_filter(query, user)
    else:
        query = query.where(ManagedContract.user_id == user_id)
    result = await db.execute(
        query.where(
            or_(
                ManagedContract.name.ilike(like),
                ManagedContract.code.ilike(like),
                ManagedContract.party_b.ilike(like),
                ManagedContract.tags_json.ilike(like),
                ManagedContract.content_text.ilike(like),
            ),
        )
        .order_by(ManagedContract.updated_at.desc())
        .limit(limit)
    )
    contracts = list(result.scalars().all())
    items = []
    for i, c in enumerate(contracts):
        text = c.content_text or ""
        highlight = text[:120] + "..." if len(text) > 120 else text
        if q in text:
            idx = text.find(q[: min(10, len(q))])
            if idx >= 0:
                snippet = text[max(0, idx - 20) : idx + 80]
                key = q[: min(10, len(q))]
                highlight = snippet.replace(key, f"**{key}**")
        items.append(
            {
                "contract": c,
                "relevance": max(50.0, 90.0 - i * 5),
                "highlight": highlight,
            }
        )
    return items
