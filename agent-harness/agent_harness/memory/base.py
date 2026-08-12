"""
Base classes for memory management.

Defines the core memory entry structure and abstract base memory class.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid


@dataclass
class MemoryEntry:
    """Represents a single memory entry."""
    content: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    importance: float = 0.5  # 0.0 to 1.0
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    embedding: Optional[List[float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entry_id": self.entry_id,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "importance": self.importance,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "tags": self.tags,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        """Create from dictionary."""
        return cls(
            entry_id=data.get("entry_id", str(uuid.uuid4())),
            content=data.get("content"),
            metadata=data.get("metadata", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else datetime.utcnow(),
            importance=data.get("importance", 0.5),
            access_count=data.get("access_count", 0),
            last_accessed=datetime.fromisoformat(data["last_accessed"]) if data.get("last_accessed") else None,
            tags=data.get("tags", []),
        )


class BaseMemory(ABC):
    """
    Abstract base class for memory implementations.
    
    All memory types (short-term, long-term, working) should inherit from this.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._entries: Dict[str, MemoryEntry] = {}
        self._initialized = False
    
    @property
    def size(self) -> int:
        """Get the number of entries in memory."""
        return len(self._entries)
    
    async def initialize(self) -> None:
        """Initialize the memory store."""
        self._initialized = True
    
    async def close(self) -> None:
        """Close and cleanup the memory store."""
        self._initialized = False
    
    @abstractmethod
    async def store(self, content: Any, **kwargs) -> str:
        """
        Store content in memory.
        
        Args:
            content: The content to store
            **kwargs: Additional metadata
            
        Returns:
            The entry ID
        """
        pass
    
    @abstractmethod
    async def retrieve(self, query: Any, limit: int = 10) -> List[MemoryEntry]:
        """
        Retrieve entries matching the query.
        
        Args:
            query: The search query
            limit: Maximum number of results
            
        Returns:
            List of matching memory entries
        """
        pass
    
    @abstractmethod
    async def get(self, entry_id: str) -> Optional[MemoryEntry]:
        """
        Get a specific entry by ID.
        
        Args:
            entry_id: The entry ID
            
        Returns:
            The memory entry or None
        """
        pass
    
    @abstractmethod
    async def delete(self, entry_id: str) -> bool:
        """
        Delete an entry by ID.
        
        Args:
            entry_id: The entry ID
            
        Returns:
            True if deleted, False otherwise
        """
        pass
    
    async def clear(self) -> None:
        """Clear all entries from memory."""
        self._entries.clear()
    
    async def update(self, entry_id: str, content: Any = None, **kwargs) -> bool:
        """
        Update an existing entry.
        
        Args:
            entry_id: The entry ID
            content: New content (optional)
            **kwargs: Additional metadata to update
            
        Returns:
            True if updated, False otherwise
        """
        if entry_id not in self._entries:
            return False
        
        entry = self._entries[entry_id]
        if content is not None:
            entry.content = content
        
        if "importance" in kwargs:
            entry.importance = kwargs["importance"]
        if "tags" in kwargs:
            entry.tags = kwargs["tags"]
        if "metadata" in kwargs:
            entry.metadata.update(kwargs["metadata"])
        
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        return {
            "size": self.size,
            "initialized": self._initialized,
            "config": self.config,
        }
    
    async def export(self) -> Dict[str, Any]:
        """Export memory contents."""
        return {
            "entries": {
                entry_id: entry.to_dict()
                for entry_id, entry in self._entries.items()
            },
            "config": self.config,
        }
    
    async def import_data(self, data: Dict[str, Any]) -> None:
        """Import memory contents."""
        entries = data.get("entries", {})
        for entry_id, entry_data in entries.items():
            self._entries[entry_id] = MemoryEntry.from_dict(entry_data)