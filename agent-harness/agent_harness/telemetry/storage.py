"""
Telemetry storage backend.

Provides persistent storage for telemetry data.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import logging

from agent_harness.telemetry.metrics import SessionMetrics

logger = logging.getLogger(__name__)


class TelemetryStorage:
    """
    Storage backend for telemetry data.
    
    Supports file-based and SQLite storage.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.backend = self.config.get("backend", "file")
        self.storage_path = Path(self.config.get("path", "data/telemetry"))
        
        self._db = None
        self._sessions: Dict[str, SessionMetrics] = {}
    
    async def initialize(self) -> None:
        """Initialize storage backend."""
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        if self.backend == "sqlite":
            await self._init_sqlite()
        else:
            await self._init_file()
        
        logger.info(f"Telemetry storage initialized with {self.backend} backend")
    
    async def _init_sqlite(self) -> None:
        """Initialize SQLite storage."""
        try:
            import aiosqlite
            db_path = self.storage_path / "telemetry.db"
            self._db = await aiosqlite.connect(str(db_path))
            
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    agent_id TEXT,
                    task TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    data TEXT
                )
            """)
            
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    event_type TEXT,
                    timestamp TEXT,
                    data TEXT
                )
            """)
            
            await self._db.commit()
        except ImportError:
            logger.warning("aiosqlite not available, falling back to file storage")
            self.backend = "file"
            await self._init_file()
    
    async def _init_file(self) -> None:
        """Initialize file-based storage."""
        self.sessions_file = self.storage_path / "sessions.json"
        if self.sessions_file.exists():
            await self._load_sessions()
    
    async def _load_sessions(self) -> None:
        """Load sessions from file."""
        try:
            with open(self.sessions_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for session_id, session_data in data.items():
                    # Reconstruct SessionMetrics from dict
                    session = SessionMetrics(
                        session_id=session_data["session_id"],
                        agent_id=session_data["agent_id"],
                        task=session_data["task"],
                    )
                    for key, value in session_data.items():
                        if hasattr(session, key):
                            # Parse datetime strings back to datetime objects
                            if key in ("start_time", "end_time") and isinstance(value, str):
                                try:
                                    value = datetime.fromisoformat(value)
                                except (ValueError, TypeError):
                                    pass
                            setattr(session, key, value)
                    self._sessions[session_id] = session
        except Exception as e:
            logger.error(f"Error loading sessions: {e}")
    
    async def _save_sessions(self) -> None:
        """Save sessions to file."""
        try:
            data = {
                session_id: session.to_dict()
                for session_id, session in self._sessions.items()
            }
            with open(self.sessions_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving sessions: {e}")
    
    async def save_session(self, session: SessionMetrics) -> None:
        """Save a session."""
        self._sessions[session.session_id] = session
        
        if self.backend == "sqlite" and self._db:
            await self._db.execute(
                """
                INSERT OR REPLACE INTO sessions 
                (session_id, agent_id, task, start_time, end_time, data)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session.session_id,
                    session.agent_id,
                    session.task,
                    session.start_time.isoformat(),
                    session.end_time.isoformat() if session.end_time else None,
                    json.dumps(session.to_dict(), default=str),
                )
            )
            await self._db.commit()
        else:
            await self._save_sessions()
    
    async def get_session(self, session_id: str) -> Optional[SessionMetrics]:
        """Get a session by ID."""
        return self._sessions.get(session_id)
    
    async def list_sessions(
        self,
        agent_id: Optional[str] = None,
        limit: int = 100
    ) -> List[SessionMetrics]:
        """List sessions, optionally filtered by agent_id."""
        sessions = list(self._sessions.values())
        
        if agent_id:
            sessions = [s for s in sessions if s.agent_id == agent_id]
        
        # Sort by start_time descending
        sessions.sort(key=lambda s: s.start_time, reverse=True)
        
        return sessions[:limit]
    
    async def add_event(
        self,
        session_id: str,
        event_type: str,
        data: Dict[str, Any]
    ) -> None:
        """Add an event to a session."""
        session = self._sessions.get(session_id)
        if session:
            session.events.append({
                "event_type": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                "data": data,
            })
            
            if self.backend == "sqlite" and self._db:
                await self._db.execute(
                    """
                    INSERT INTO events (session_id, event_type, timestamp, data)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        event_type,
                        datetime.utcnow().isoformat(),
                        json.dumps(data, default=str),
                    )
                )
                await self._db.commit()
    
    async def get_events(
        self,
        session_id: str,
        event_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get events for a session."""
        session = self._sessions.get(session_id)
        if not session:
            return []
        
        events = session.events
        if event_type:
            events = [e for e in events if e.get("event_type") == event_type]
        
        return events
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            
            if self.backend == "sqlite" and self._db:
                await self._db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
                await self._db.execute("DELETE FROM events WHERE session_id = ?", (session_id,))
                await self._db.commit()
            else:
                await self._save_sessions()
            
            return True
        return False
    
    async def export_session(self, session_id: str, path: str) -> bool:
        """Export a session to a file."""
        session = self._sessions.get(session_id)
        if not session:
            return False
        
        export_path = Path(path)
        export_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, indent=2, default=str)
        
        return True
    
    async def close(self) -> None:
        """Close storage backend."""
        if self.backend == "file":
            await self._save_sessions()
        elif self._db:
            await self._db.close()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        return {
            "backend": self.backend,
            "total_sessions": len(self._sessions),
            "storage_path": str(self.storage_path),
        }