"""LangChain RAG API routes."""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional
from loguru import logger

from backend.services.langchain_rag import langchain_rag, RAGResponse

router = APIRouter(prefix="/api/rag", tags=["rag"])


@router.post("/document")
async def upload_document(
    file: UploadFile = File(...),
    description: Optional[str] = Form(None)
):
    """Upload a document to the RAG system."""
    try:
        import tempfile
        import os
        
        # Save uploaded file temporarily
        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        try:
            chunks = langchain_rag.load_document(tmp_path)
            return {
                "status": "success",
                "filename": file.filename,
                "chunks_added": chunks
            }
        finally:
            os.unlink(tmp_path)
    
    except Exception as e:
        logger.error(f"Document upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/text")
async def add_text(content: str, source: str = "manual"):
    """Add text directly to the RAG system."""
    try:
        chunks = langchain_rag.add_text(
            text=content,
            metadata={"source": source}
        )
        return {
            "status": "success",
            "chunks_added": chunks
        }
    except Exception as e:
        logger.error(f"Add text error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query")
async def query_rag(question: str, use_rag: bool = True):
    """Query the RAG system."""
    try:
        result = await langchain_rag.query(question, use_rag)
        return {
            "answer": result.answer,
            "source_documents": result.source_documents,
            "context": result.context[:500] + "..." if len(result.context) > 500 else result.context
        }
    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_documents(query: str, k: int = 5):
    """Search documents in RAG."""
    try:
        results = langchain_rag.similarity_search(query, k=k)
        return {
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats():
    """Get RAG statistics."""
    return langchain_rag.get_stats()


@router.delete("/clear")
async def clear_documents():
    """Clear all documents from RAG."""
    langchain_rag.clear()
    return {"status": "success", "message": "All documents cleared"}


@router.post("/save")
async def save_index(path: str = "./rag_index"):
    """Save the RAG index to disk."""
    try:
        langchain_rag.save_index(path)
        return {"status": "success", "path": path}
    except Exception as e:
        logger.error(f"Save index error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/load")
async def load_index(path: str = "./rag_index"):
    """Load the RAG index from disk."""
    try:
        langchain_rag.load_index(path)
        return {"status": "success", "path": path}
    except Exception as e:
        logger.error(f"Load index error: {e}")
        raise HTTPException(status_code=500, detail=str(e))