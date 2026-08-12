"""
Short-term memory implementation.

Provides a conversation buffer with TTL and eviction policies.
"""

from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import logging

from agent_harness.memory.base import BaseMemory, MemoryEntry

logger = logging.getLogger(__name__)


class ShortTermMemory(BaseMemory):
    """
    Short-term memory (conversation buffer).
    
    Features:
    - Limited size with configurable eviction policy
    - Time-to-live (TTL) for entries
    - LRU, FIFO, or priority-based eviction
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.max_size = self.config.get("max_size", 100)
        self.ttl = self.config.get("ttl", 3600)  # seconds
        self.eviction_policy = self.config.get("eviction_policy", "lru")
        
        # Use OrderedDict for LRU tracking
        self._entries: OrderedDict[str, MemoryEntry] = OrderedDict()
    
    async def store(self, content: Any, **kwargs) -> str:
        """Store content in short-term memory."""
        entry = MemoryEntry(
            content=content,
            metadata=kwargs.get("metadata", {}),
            importance=kwargs.get("importance", 0.5),
            tags=kwargs.get("tags", []),
        )
        
        # Evict if at capacity
        while len(self._entries) >= self.max_size:
            await self._evict()
        
        self._entries[entry.entry_id] = entry
        
        # Move to end for LRU
        if self.eviction_policy == "lru":
            self._entries.move_to_end(entry.entry_id)
        
        logger.debug(f"Stored entry {entry.entry_id} in short-term memory")
        return entry.entry_id
    
    async def retrieve(self, query: Any, limit: int = 10) -> List[MemoryEntry]:
        """Retrieve recent entries matching the query."""
        # Clean expired entries first
        await self._clean_expired()
        
        results = []
        query_str = str(query).lower() if query else ""
        
        # Iterate from most recent
        for entry in reversed(list(self._entries.values())):
            if len(results) >= limit:
                break
            
            # Simple text matching
            content_str = str(entry.content).lower()
            if not query_str or query_str in content_str:
                entry.access_count += 1
                entry.last_accessed = datetime.utcnow()
                
                # Update LRU position
                if self.eviction_policy == "lru":
                    self._entries.move_to_end(entry.entry_id)
                
                results.append(entry)
        
        return results
    
    async def get(self, entry_id: str) -> Optional[MemoryEntry]:
        """Get a specific entry by ID."""
        await self._clean_expired()
        
        entry = self._entries.get(entry_id)
        if entry:
            entry.access_count += 1
            entry.last_accessed = datetime.utcnow()
            
            if self.eviction_policy == "lru":
                self._entries.move_to_end(entry_id)
        
        return entry
    
    async def delete(self, entry_id: str) -> bool:
        """Delete an entry by ID."""
        if entry_id in self._entries:
            del self._entries[entry_id]
            return True
        return False
    
    async def clear(self) -> None:
        """Clear all entries."""
        self._entries.clear()
    
    async def _evict(self) -> None:
        """Evict an entry based on the eviction policy."""
        if not self._entries:
            return
        
        if self.eviction_policy == "lru":
            # Remove least recently used (first item)
            entry_id, _ = self._entries.popitem(last=False)
        elif self.eviction_policy == "fifo":
            # Remove first in (first item)
            entry_id, _ = self._entries.popitem(last=False)
        elif self.eviction_policy == "priority":
            # Remove lowest importance
            min_entry = min(self._entries.values(), key=lambda e: e.importance)
            entry_id = min_entry.entry_id
            del self._entries[entry_id]
        else:
            # Default to LRU
            entry_id, _ = self._entries.popitem(last=False)
        
        logger.debug(f"Evicted entry {entry_id} from short-term memory")
    
    async def _clean_expired(self) -> None:
        """Remove expired entries based on TTL."""
        if self.ttl <= 0:
            return
        
        now = datetime.utcnow()
        expired = []
        
        for entry_id, entry in self._entries.items():
            age = (now - entry.timestamp).total_seconds()
            if age > self.ttl:
                expired.append(entry_id)
        
        for entry_id in expired:
            del self._entries[entry_id]
            logger.debug(f"Expired entry {entry_id} from short-term memory")
    
    def get_recent(self, count: int = 10) -> List[MemoryEntry]:
        """Get the most recent entries without query filtering."""
        return list(self._entries.values())[-count:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        stats = super().get_stats()
        stats.update({
            "max_size": self.max_size,
            "ttl": self.ttl,
            "eviction_policy": self.eviction_policy,
            "utilization": len(self._entries) / self.max_size if self.max_size > 0 else 0,
        })
        return stats