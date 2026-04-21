"""RAG (Retrieval-Augmented Generation) service for knowledge base."""

import os
import json
import uuid
from typing import List, Dict, Any, Optional
from pathlib import Path
from loguru import logger

from backend.config import settings
from backend.services.llm_service import llm_service


class DocumentChunk:
    """Represents a chunk of a document."""
    
    def __init__(self, content: str, metadata: Dict[str, Any]):
        self.id = str(uuid.uuid4())
        self.content = content
        self.metadata = metadata
        self.embedding: Optional[List[float]] = None


class RAGService:
    """Service for RAG functionality."""
    
    def __init__(self):
        self.chunks: List[DocumentChunk] = []
        self.index_path = Path(settings.faiss_index_path)
        self._load_index()
    
    def _load_index(self):
        """Load existing index if available."""
        if not settings.rag_enabled:
            logger.info("RAG is disabled")
            return
        
        if self.index_path.exists():
            try:
                chunks_file = self.index_path / "chunks.json"
                if chunks_file.exists():
                    with open(chunks_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        for chunk_data in data:
                            chunk = DocumentChunk(
                                content=chunk_data["content"],
                                metadata=chunk_data.get("metadata", {})
                            )
                            chunk.embedding = chunk_data.get("embedding")
                            self.chunks.append(chunk)
                    logger.info(f"Loaded {len(self.chunks)} chunks from index")
            except Exception as e:
                logger.warning(f"Failed to load index: {e}")
    
    def _save_index(self):
        """Save index to disk."""
        if not settings.rag_enabled:
            return
        
        self.index_path.mkdir(parents=True, exist_ok=True)
        
        chunks_data = []
        for chunk in self.chunks:
            chunks_data.append({
                "id": chunk.id,
                "content": chunk.content,
                "metadata": chunk.metadata,
                "embedding": chunk.embedding
            })
        
        with open(self.index_path / "chunks.json", "w", encoding="utf-8") as f:
            json.dump(chunks_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved {len(self.chunks)} chunks to index")
    
    async def add_document(self, content: str, metadata: Dict[str, Any] = None) -> int:
        """Add a document and create chunks."""
        if not settings.rag_enabled:
            return 0
        
        metadata = metadata or {}
        chunk_size = settings.rag_chunk_size
        overlap = settings.rag_chunk_overlap
        
        # Simple text chunking
        chunks = []
        start = 0
        content_length = len(content)
        
        while start < content_length:
            end = min(start + chunk_size, content_length)
            chunk_text = content[start:end]
            chunks.append(chunk_text)
            start += chunk_size - overlap
        
        # Create embeddings for each chunk
        chunks_created = 0
        for chunk_text in chunks:
            try:
                embedding = await llm_service.get_embedding(chunk_text)
                chunk = DocumentChunk(
                    content=chunk_text,
                    metadata=metadata
                )
                chunk.embedding = embedding
                self.chunks.append(chunk)
                chunks_created += 1
            except Exception as e:
                logger.warning(f"Failed to create embedding for chunk: {e}")
        
        if chunks_created > 0:
            self._save_index()
            logger.info(f"Added {chunks_created} chunks from document")
        
        return chunks_created
    
    async def add_pdf(self, pdf_path: str) -> int:
        """Add content from a PDF file."""
        try:
            from pypdf import PdfReader
        except ImportError:
            logger.error("pypdf not installed")
            return 0
        
        try:
            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            
            filename = os.path.basename(pdf_path)
            return await self.add_document(text, {"source": filename, "type": "pdf"})
        except Exception as e:
            logger.error(f"Failed to process PDF: {e}")
            return 0
    
    async def search(self, query: str, top_k: int = None) -> List[Dict[str, Any]]:
        """Search for relevant chunks."""
        if not settings.rag_enabled or not self.chunks:
            return []
        
        top_k = top_k or settings.rag_top_k
        
        try:
            # Get query embedding
            query_embedding = await llm_service.get_embedding(query)
            
            # Calculate similarities
            results = []
            for chunk in self.chunks:
                if chunk.embedding is None:
                    continue
                
                similarity = self._cosine_similarity(query_embedding, chunk.embedding)
                results.append({
                    "content": chunk.content,
                    "metadata": chunk.metadata,
                    "similarity": similarity
                })
            
            # Sort by similarity and return top_k
            results.sort(key=lambda x: x["similarity"], reverse=True)
            return results[:top_k]
        
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = sum(x * y for x, y in zip(a, b))
        magnitude_a = sum(x * x for x in a) ** 0.5
        magnitude_b = sum(x * x for x in b) ** 0.5
        
        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0
        
        return dot_product / (magnitude_a * magnitude_b)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get RAG statistics."""
        return {
            "enabled": settings.rag_enabled,
            "total_chunks": len(self.chunks),
            "index_path": str(self.index_path)
        }
    
    def clear(self):
        """Clear all documents."""
        self.chunks = []
        self._save_index()
        logger.info("Cleared all RAG documents")


# Global RAG service
rag_service = RAGService()