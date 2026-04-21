"""Chat router - handles all chat-related API endpoints."""
import logging
from fastapi import APIRouter, HTTPException
from backend.models import ChatRequest, ChatResponse, HistoryResponse
from backend.services.deepseek_api import get_deepseek_api
from backend.services.session import get_session_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a message and get a response from DeepSeek.
    
    Args:
        request: ChatRequest containing the user message and optional session_id
        
    Returns:
        ChatResponse with the AI's response
        
    Raises:
        HTTPException: If there's an error processing the request
    """
    try:
        # Validate input
        if not request.message or not request.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty")
        
        # Get session manager
        session_manager = get_session_manager()
        
        # Get or create session
        session_id = request.session_id or session_manager.create_session()
        
        # Add user message to session
        user_message = session_manager.add_message(
            session_id=session_id,
            role="user",
            content=request.message.strip()
        )
        
        logger.info(f"Processing message in session {session_id}")
        
        # Get DeepSeek API instance
        deepseek_api = await get_deepseek_api()
        
        # Get conversation history (excluding the current message for context)
        conversation_history = session_manager.get_recent_messages(session_id, limit=20)
        
        # Call DeepSeek API
        system_prompt = "你是一个有帮助的AI助手。请用中文回答问题。"
        response_text = await deepseek_api.chat(
            messages=conversation_history,
            system_prompt=system_prompt
        )
        
        # Add assistant response to session
        assistant_message = session_manager.add_message(
            session_id=session_id,
            role="assistant",
            content=response_text
        )
        
        logger.info(f"Successfully processed message in session {session_id}")
        
        return ChatResponse(
            response=response_text,
            session_id=session_id,
            message_id=assistant_message.id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        )


@router.get("/history/{session_id}", response_model=HistoryResponse)
async def get_history(session_id: str):
    """
    Get conversation history for a session.
    
    Args:
        session_id: The session ID
        
    Returns:
        HistoryResponse containing all messages in the session
        
    Raises:
        HTTPException: If session is not found
    """
    try:
        session_manager = get_session_manager()
        conversation = session_manager.get_conversation(session_id)
        
        if conversation is None:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return HistoryResponse(
            messages=conversation.messages,
            session_id=session_id,
            total_messages=len(conversation.messages)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """
    Delete a conversation session.
    
    Args:
        session_id: The session ID to delete
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If session is not found
    """
    try:
        session_manager = get_session_manager()
        deleted = session_manager.delete_session(session_id)
        
        if not deleted:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {"message": f"Session {session_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def list_sessions():
    """
    Get all active sessions.
    
    Returns:
        List of session information
    """
    try:
        session_manager = get_session_manager()
        sessions = []
        
        for session_id in session_manager.get_all_sessions():
            conversation = session_manager.get_conversation(session_id)
            sessions.append({
                "session_id": session_id,
                "message_count": len(conversation.messages),
                "created_at": conversation.created_at.isoformat(),
                "updated_at": conversation.updated_at.isoformat()
            })
        
        return {"sessions": sessions, "total": len(sessions)}
        
    except Exception as e:
        logger.error(f"Error listing sessions: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/new")
async def create_new_session():
    """
    Create a new conversation session.
    
    Returns:
        The new session ID
    """
    try:
        session_manager = get_session_manager()
        session_id = session_manager.create_session()
        return {"session_id": session_id}
        
    except Exception as e:
        logger.error(f"Error creating session: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
