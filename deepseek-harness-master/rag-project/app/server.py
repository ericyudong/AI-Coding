"""FastAPI server: document upload, retrieval query, and document management."""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import UPLOAD_DIR, ALLOWED_EXTENSIONS
from app.ingest import extract_text, chunk_text, content_hash
from app.vectorstore import add_documents, query, delete_by_filename, list_documents
from app.llm import generate_answer

app = FastAPI(title="RAG Web App", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str
    top_k: int = 5


class QueryResponse(BaseModel):
    answer: str
    sources: list[dict]


class DocInfo(BaseModel):
    filename: str
    chunks: int


# ── Endpoints ─────────────────────────────────────────────────────────

@app.post("/api/upload", summary="Upload and ingest a document")
async def upload_document(file: UploadFile = File(...)) -> dict:
    """Accept a file upload, parse it, chunk it, and store embeddings."""
    if not file.filename:
        raise HTTPException(400, "Missing filename")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type '{suffix}'. Allowed: {ALLOWED_EXTENSIONS}")

    # Save uploaded file
    dest = UPLOAD_DIR / file.filename
    content = await file.read()
    dest.write_bytes(content)

    # Parse and chunk
    try:
        text = extract_text(dest)
    except Exception as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(422, f"Failed to parse document: {e}")

    chunks = chunk_text(text)
    if not chunks:
        dest.unlink(missing_ok=True)
        raise HTTPException(422, "Document is empty or could not be parsed into chunks")

    # Build metadata and IDs
    metadatas = [{"filename": file.filename, "chunk_index": i} for i in range(len(chunks))]
    ids = [f"{file.filename}::{content_hash(c)}::{i}" for i, c in enumerate(chunks)]

    count = add_documents(chunks, metadatas, ids)
    return {"filename": file.filename, "chunks_ingested": count, "size_bytes": len(content)}


@app.post("/api/query", response_model=QueryResponse, summary="Ask a question over your documents")
async def ask_question(req: QueryRequest) -> QueryResponse:
    """Retrieve relevant chunks and generate an LLM-grounded answer."""
    results = query(req.question, n_results=req.top_k)
    answer = generate_answer(req.question, results)
    sources = [{"filename": r["metadata"].get("filename"), "distance": round(r["distance"], 4), "preview": r["text"][:200]} for r in results]
    return QueryResponse(answer=answer, sources=sources)


@app.get("/api/documents", response_model=list[DocInfo], summary="List ingested documents")
async def get_documents() -> list[DocInfo]:
    """Return all documents currently in the vector store."""
    docs = list_documents()
    return [DocInfo(**d) for d in docs]


@app.delete("/api/documents/{filename}", summary="Delete a document from the store")
async def remove_document(filename: str) -> dict:
    """Remove all chunks for a given filename from the vector store and disk."""
    delete_by_filename(filename)
    filepath = UPLOAD_DIR / filename
    if filepath.exists():
        filepath.unlink()
    return {"deleted": filename}


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}
