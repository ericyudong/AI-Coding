"""Session management service - handles conversation sessions and message history."""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from backend.config import get_settings
from backend.models import Message, Conversation

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages conversation sessions and message history."""
    
    def __init__(self):
        """Initialize session manager with in-memory storage."""
        self.settings = get_settings()
        self._sessions: Dict[str, Conversation] = {}
    
    def create_session(self, session_id: str = None) -> str:
        """
        Create a new conversation session.
        
        Args:
            session_id: Optional custom session ID. If not provided, generates one.
            
        Returns:
            The session ID
        """
        if session_id is None:
            session_id = __import__('uuid').uuid4().hex
        
        if session_id not in self._sessions:
            self._sessions[session_id] = Conversation(
                session_id=session_id,
                messages=[]
            )
            logger.info(f"Created new session: {session_id}")
        else:
            logger.info(f"Session already exists: {session_id}")
        
        return session_id
    
    def add_message(self, session_id: str, role: str, content: str) -> Message:
        """
        Add a message to a session.
        
        Args:
            session_id: Session ID
            role: Message role ('user' or 'assistant')
            content: Message content
            
        Returns:
            The created Message object
        """
        # Ensure session exists
        if session_id not in self._sessions:
            self.create_session(session_id)
        
        message = Message(role=role, content=content)
        self._sessions[session_id].messages.append(message)
        self._sessions[session_id].updated_at = datetime.utcnow()
        
        logger.debug(f"Added {role} message to session {session_id}")
        return message
    
    def get_conversation(self, session_id: str) -> Optional[Conversation]:
        """
        Get a conversation by session ID.
        
        Args:
            session_id: Session ID
            
        Returns:
            The Conversation object or None if not found
        """
        return self._sessions.get(session_id)
    
    def get_messages(self, session_id: str) -> List[Message]:
        """
        Get all messages in a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            List of Message objects
        """
        conversation = self._sessions.get(session_id)
        if conversation:
            return conversation.messages
        return []
    
    def get_recent_messages(self, session_id: str, limit: int = 10) -> List[Message]:
        """
        Get the most recent messages from a session.
        
        Args:
            session_id: Session ID
            limit: Maximum number of messages to return
            
        Returns:
            List of recent Message objects
        """
        messages = self.get_messages(session_id)
        return messages[-limit:] if len(messages) > limit else messages
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a conversation session.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if deleted, False if not found
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Deleted session: {session_id}")
            return True
        logger.warning(f"Session not found: {session_id}")
        return False
    
    def clear_expired_sessions(self):
        """Clear sessions that have expired based on SESSION_EXPIRY setting."""
        now = datetime.utcnow()
        expiry_delta = timedelta(seconds=self.settings.session_expiry)
        
        expired_sessions = [
            session_id for session_id, conversation in self._sessions.items()
            if now - conversation.updated_at > expiry_delta
        ]
        
        for session_id in expired_sessions:
            self.delete_session(session_id)
        
        if expired_sessions:
            logger.info(f"Cleared {len(expired_sessions)} expired sessions")
    
    def get_all_sessions(self) -> List[str]:
        """
        Get all active session IDs.
        
        Returns:
            List of session IDs
        """
        return list(self._sessions.keys())
    
    def get_session_count(self) -> int:
        """
        Get the number of active sessions.
        
        Returns:
            Number of sessions
        """
        return len(self._sessions)


# Global instance
_session_manager = None


def get_session_manager() -> SessionManager:
    """Get or create SessionManager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
