"""Document API routes for RAG."""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from typing import Optional
from loguru import logger

from backend.models import DocumentUploadResponse
from backend.services.rag_service import rag_service

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    description: Optional[str] = Form(None)
):
    """Upload a document for RAG."""
    try:
        # Check file type first
        filename = file.filename.lower() if file.filename else "unknown"
        
        if filename.endswith(".pdf"):
            # Handle PDF file - save temporarily and process
            import tempfile
            import os
            
            content = await file.read()
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            
            try:
                chunks_added = await rag_service.add_pdf(tmp_path)
            finally:
                os.unlink(tmp_path)
                
        elif filename.endswith((".txt", ".md", ".text")):
            # Handle text file
            content = await file.read()
            try:
                text_content = content.decode("utf-8")
            except UnicodeDecodeError:
                # Try other encodings
                try:
                    text_content = content.decode("gbk")
                except UnicodeDecodeError:
                    text_content = content.decode("latin-1")
            
            metadata = {
                "filename": file.filename,
                "description": description or ""
            }
            chunks_added = await rag_service.add_document(text_content, metadata)
            
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type. Supported: .txt, .md, .pdf"
            )
        
        return DocumentUploadResponse(
            document_id=file.filename,
            filename=file.filename,
            status="success",
            chunks_added=chunks_added
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/text")
async def add_text_document(content: str, source: str = "manual"):
    """Add a text document directly."""
    try:
        chunks_added = await rag_service.add_document(
            content,
            {"source": source, "type": "text"}
        )
        
        return {
            "status": "success",
            "chunks_added": chunks_added
        }
    
    except Exception as e:
        logger.error(f"Add text error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_document_stats():
    """Get RAG statistics."""
    return rag_service.get_stats()


@router.delete("/clear")
async def clear_documents():
    """Clear all documents from RAG."""
    rag_service.clear()
    return {"status": "success", "message": "All documents cleared"}


@router.get("/search")
async def search_documents(query: str, top_k: int = 5):
    """Search documents in RAG."""
    results = await rag_service.search(query, top_k)
    return {"results": results, "count": len(results)}