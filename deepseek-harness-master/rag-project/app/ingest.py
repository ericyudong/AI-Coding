"""Document parsing, chunking, and ingestion into the vector store."""

from __future__ import annotations

import hashlib
from pathlib import Path

from pypdf import PdfReader
from docx import Document as DocxDocument

from app.config import CHUNK_SIZE, CHUNK_OVERLAP


def extract_text(path: Path) -> str:
    """Extract plain text from a supported document file."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if suffix == ".docx":
        doc = DocxDocument(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
    # .txt, .md, etc.
    return path.read_text(encoding="utf-8", errors="replace")


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks by character count."""
    if not text.strip():
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return [c.strip() for c in chunks if c.strip()]


def content_hash(text: str) -> str:
    """Deterministic hash for deduplication."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]
