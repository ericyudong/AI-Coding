"""ChromaDB vector store wrapper with local sentence-transformer embeddings."""

from __future__ import annotations

import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from app.config import CHROMA_DIR, EMBEDDING_MODEL, TOP_K

_embedding_model: SentenceTransformer | None = None
_chroma_client: chromadb.PersistentClient | None = None
_collection: chromadb.Collection | None = None


def _get_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    return _embedding_model


def get_collection() -> chromadb.Collection:
    """Return (and lazily create) the default document collection."""
    global _chroma_client, _collection
    if _collection is None:
        _chroma_client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        _collection = _chroma_client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of texts."""
    model = _get_model()
    embeddings = model.encode(texts, normalize_embeddings=True)
    return embeddings.tolist()


def add_documents(chunks: list[str], metadatas: list[dict], ids: list[str]) -> int:
    """Upsert document chunks into the vector store. Returns count added."""
    if not chunks:
        return 0
    collection = get_collection()
    embeddings = embed_texts(chunks)
    collection.upsert(ids=ids, documents=chunks, embeddings=embeddings, metadatas=metadatas)
    return len(chunks)


def query(query_text: str, n_results: int = TOP_K, where: dict | None = None) -> list[dict]:
    """Query the vector store and return ranked results."""
    collection = get_collection()
    q_embedding = embed_texts([query_text])[0]
    kwargs: dict = {"query_embeddings": [q_embedding], "n_results": n_results, "include": ["documents", "metadatas", "distances"]}
    if where:
        kwargs["where"] = where
    results = collection.query(**kwargs)

    items = []
    for i in range(len(results["ids"][0])):
        items.append({
            "id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
        })
    return items


def delete_by_filename(filename: str) -> None:
    """Remove all chunks belonging to a given filename."""
    collection = get_collection()
    try:
        collection.delete(where={"filename": filename})
    except Exception:
        pass


def list_documents() -> list[dict]:
    """Return distinct filenames and chunk counts in the store."""
    collection = get_collection()
    total = collection.count()
    if total == 0:
        return []
    all_meta = collection.get(include=["metadatas"])
    counts: dict[str, int] = {}
    for m in all_meta["metadatas"]:
        fn = m.get("filename", "unknown")
        counts[fn] = counts.get(fn, 0) + 1
    return [{"filename": fn, "chunks": cnt} for fn, cnt in sorted(counts.items())]
