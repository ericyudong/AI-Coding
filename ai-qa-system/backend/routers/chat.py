"""Chat API routes."""

from fastapi import APIRouter, HTTPException
from typing import List, Optional
from loguru import logger

from backend.models import ChatRequest, ChatResponse, ConversationListResponse
from backend.services.session_service import session_manager
from backend.services.llm_service import llm_service
from backend.services.rag_service import rag_service
from backend.config import settings

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a message and get AI response."""
    try:
        # Create or get session
        session_id = session_manager.create_session(request.session_id)
        
        # Get conversation history
        messages = session_manager.get_messages(session_id)
        
        # Build messages for LLM
        llm_messages = []
        
        # Add context from RAG if enabled and requested
        sources = []
        if request.use_rag and settings.rag_enabled:
            relevant_docs = await rag_service.search(request.message)
            if relevant_docs:
                context = "\n\n".join([doc["content"] for doc in relevant_docs])
                llm_messages.append({
                    "role": "system",
                    "content": f"You are a helpful assistant. Use the following context to answer questions:\n\n{context}"
                })
                sources = relevant_docs
        
        # Add conversation history
        for msg in messages:
            llm_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Add current user message
        llm_messages.append({
            "role": "user",
            "content": request.message
        })
        
        # Generate response
        response_text = await llm_service.generate_response(
            messages=llm_messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        # Save messages
        user_msg_id = session_manager.add_message(session_id, "user", request.message)
        assistant_msg_id = session_manager.add_message(session_id, "assistant", response_text)
        
        return ChatResponse(
            response=response_text,
            session_id=session_id,
            message_id=assistant_msg_id,
            sources=sources,
            metadata={
                "use_rag": request.use_rag,
                "provider": settings.llm_provider
            }
        )
    
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{session_id}")
async def get_history(session_id: str):
    """Get conversation history for a session."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    messages = session_manager.get_messages(session_id)
    return {
        "session_id": session_id,
        "messages": messages,
        "title": session["title"]
    }


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations():
    """List all conversations."""
    sessions = session_manager.list_sessions()
    return ConversationListResponse(
        conversations=sessions,
        total=len(sessions)
    )


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    success = session_manager.clear_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted", "session_id": session_id}


@router.post("/session/{session_id}/clear")
async def clear_session(session_id: str):
    """Clear a session's messages."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session["messages"] = []
    session["title"] = "New Conversation"
    return {"status": "cleared", "session_id": session_id}