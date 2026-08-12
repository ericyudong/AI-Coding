"""Contract indexing: chunk → embed → store."""
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.cms_models import ContractChunk, ManagedContract
from app.services import embedding_service, vector_store
from app.services.text_chunker import chunk_contract_text


async def index_contract(db: AsyncSession, contract: ManagedContract) -> bool:
    """Index contract content into DB chunks + Qdrant."""
    text = (contract.content_text or "").strip()
    if not text:
        contract.index_status = "empty"
        await db.commit()
        return False

    settings = get_settings()
    chunks = chunk_contract_text(text, chunk_size=settings.chunk_size, overlap=settings.chunk_overlap)
    if not chunks:
        contract.index_status = "empty"
        await db.commit()
        return False

    await db.execute(delete(ContractChunk).where(ContractChunk.contract_id == contract.id))
    vector_store.delete_by_contract(contract.id)

    texts = [c.content for c in chunks]
    vectors = await embedding_service.embed_texts(texts)

    contract.index_status = "processing"
    await db.flush()

    if vectors is None:
        # Store chunks without vectors for keyword/RAG fallback
        for c in chunks:
            db.add(
                ContractChunk(
                    contract_id=contract.id,
                    chunk_index=c.index,
                    section_title=c.section_title,
                    content=c.content,
                    start_offset=c.start_offset,
                    vector_id="",
                )
            )
        contract.index_status = "no_embedding"
        contract.indexed_at = contract.updated_at
        await db.commit()
        return False

    points = []
    for c, vec in zip(chunks, vectors):
        vid = vector_store.new_point_id()
        db.add(
            ContractChunk(
                contract_id=contract.id,
                chunk_index=c.index,
                section_title=c.section_title,
                content=c.content,
                start_offset=c.start_offset,
                vector_id=vid,
            )
        )
        points.append(
            (
                vid,
                vec,
                {
                    "user_id": contract.user_id,
                    "contract_id": contract.id,
                    "chunk_index": c.index,
                    "section_title": c.section_title,
                    "content": c.content[:2000],
                },
            )
        )

    vector_store.upsert_vectors(points)
    contract.index_status = "indexed"
    from datetime import datetime, timezone

    contract.indexed_at = datetime.now(timezone.utc)
    await db.commit()
    return True


async def ensure_indexed(db: AsyncSession, contract: ManagedContract) -> None:
    if contract.index_status in ("indexed", "no_embedding"):
        return
    await index_contract(db, contract)


async def reindex_all(db: AsyncSession, user_id: int | None = None) -> int:
    q = select(ManagedContract)
    if user_id is not None:
        q = q.where(ManagedContract.user_id == user_id)
    result = await db.execute(q)
    contracts = result.scalars().all()
    count = 0
    for c in contracts:
        if await index_contract(db, c):
            count += 1
    return count
