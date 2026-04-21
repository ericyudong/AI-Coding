"""Session service for managing conversations."""

import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger

from backend.config import settings


class SessionManager:
    """In-memory session manager for conversations."""
    
    def __init__(self):
        self.sessions: Dict[str, Dict] = {}
    
    def create_session(self, session_id: Optional[str] = None) -> str:
        """Create a new session."""
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "id": session_id,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "messages": [],
                "title": "New Conversation"
            }
            logger.info(f"Created new session: {session_id}")
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get a session by ID."""
        return self.sessions.get(session_id)
    
    def add_message(self, session_id: str, role: str, content: str) -> str:
        """Add a message to a session."""
        if session_id not in self.sessions:
            self.create_session(session_id)
        
        message_id = str(uuid.uuid4())
        message = {
            "id": message_id,
            "role": role,
            "content": content,
            "created_at": datetime.utcnow().isoformat()
        }
        
        self.sessions[session_id]["messages"].append(message)
        self.sessions[session_id]["updated_at"] = datetime.utcnow()
        
        # Update title if it's the first user message
        if role == "user" and self.sessions[session_id]["title"] == "New Conversation":
            self.sessions[session_id]["title"] = content[:50] + ("..." if len(content) > 50 else "")
        
        return message_id
    
    def get_messages(self, session_id: str) -> List[Dict]:
        """Get all messages for a session."""
        session = self.get_session(session_id)
        if session:
            # Limit to max conversation history
            messages = session["messages"][-settings.max_conversation_history:]
            return messages
        return []
    
    def clear_session(self, session_id: str) -> bool:
        """Clear a session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Cleared session: {session_id}")
            return True
        return False
    
    def list_sessions(self) -> List[Dict]:
        """List all sessions."""
        sessions = []
        for session_id, data in self.sessions.items():
            sessions.append({
                "id": session_id,
                "title": data["title"],
                "message_count": len(data["messages"]),
                "created_at": data["created_at"].isoformat(),
                "updated_at": data["updated_at"].isoformat()
            })
        return sorted(sessions, key=lambda x: x["updated_at"], reverse=True)
    
    def cleanup_expired(self):
        """Clean up expired sessions."""
        expiry_time = datetime.utcnow() - timedelta(hours=settings.session_expiry_hours)
        expired = [
            sid for sid, data in self.sessions.items()
            if data["updated_at"] < expiry_time
        ]
        for sid in expired:
            del self.sessions[sid]
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")


# Global session manager
session_manager = SessionManager()