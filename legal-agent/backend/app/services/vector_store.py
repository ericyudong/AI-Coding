"""Qdrant vector store wrapper."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from app.core.config import data_root, get_settings

logger = logging.getLogger(__name__)

COLLECTION = "contract_chunks"
_client = None
_available: bool | None = None


@dataclass
class VectorHit:
    vector_id: str
    contract_id: int
    user_id: int
    chunk_index: int
    section_title: str
    content: str
    score: float


def _ensure_collection(client, dim: int) -> None:
    from qdrant_client.models import Distance, VectorParams

    if not client.collection_exists(COLLECTION):
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        return

    info = client.get_collection(COLLECTION)
    current_dim = info.config.params.vectors.size
    if current_dim != dim:
        logger.warning(
            "Qdrant collection dim mismatch (%s vs %s), recreating",
            current_dim,
            dim,
        )
        client.delete_collection(COLLECTION)
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )


def _get_client():
    global _client, _available
    if _available is False:
        return None
    if _client is not None:
        return _client
    try:
        from qdrant_client import QdrantClient

        settings = get_settings()
        path = data_root() / "qdrant"
        path.mkdir(parents=True, exist_ok=True)
        _client = QdrantClient(path=str(path))
        _ensure_collection(_client, settings.embedding_dimensions)
        _available = True
        return _client
    except Exception as exc:
        logger.warning("Qdrant unavailable: %s", exc)
        _available = False
        return None


def reset_client() -> None:
    """Reset cached client (e.g. after Qdrant path wipe)."""
    global _client, _available
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
    _client = None
    _available = None


def is_vector_store_available() -> bool:
    return _get_client() is not None


def ensure_collection_dim(dim: int) -> None:
    """Ensure Qdrant collection matches embedding dimension."""
    client = _get_client()
    if client:
        _ensure_collection(client, dim)


def upsert_vectors(
    points: list[tuple[str, list[float], dict]],
) -> bool:
    client = _get_client()
    if not client or not points:
        return False
    dim = len(points[0][1])
    _ensure_collection(client, dim)
    from qdrant_client.models import PointStruct

    structs = [
        PointStruct(id=pid, vector=vec, payload=payload)
        for pid, vec, payload in points
    ]
    client.upsert(collection_name=COLLECTION, points=structs)
    return True


def search_vectors(
    vector: list[float],
    user_id: int | None,
    top_k: int = 20,
    contract_id: int | None = None,
) -> list[VectorHit]:
    client = _get_client()
    if not client:
        return []
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    must = []
    if user_id is not None:
        must.append(FieldCondition(key="user_id", match=MatchValue(value=user_id)))
    if contract_id is not None:
        must.append(FieldCondition(key="contract_id", match=MatchValue(value=contract_id)))

    results = client.query_points(
        collection_name=COLLECTION,
        query=vector,
        query_filter=Filter(must=must) if must else None,
        limit=top_k,
        with_payload=True,
    )
    hits: list[VectorHit] = []
    for r in results.points:
        p = r.payload or {}
        hits.append(
            VectorHit(
                vector_id=str(r.id),
                contract_id=int(p.get("contract_id", 0)),
                user_id=int(p.get("user_id", 0)),
                chunk_index=int(p.get("chunk_index", 0)),
                section_title=str(p.get("section_title", "")),
                content=str(p.get("content", "")),
                score=float(r.score or 0),
            )
        )
    return hits


def delete_by_contract(contract_id: int) -> None:
    client = _get_client()
    if not client:
        return
    try:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        client.delete(
            collection_name=COLLECTION,
            points_selector=Filter(
                must=[FieldCondition(key="contract_id", match=MatchValue(value=contract_id))]
            ),
        )
    except Exception as exc:
        logger.debug("delete_by_contract skipped: %s", exc)


def new_point_id() -> str:
    return str(uuid.uuid4())
