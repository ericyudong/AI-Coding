"""
Working memory implementation.

Provides active context management with limited slots.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import logging

from agent_harness.memory.base import BaseMemory, MemoryEntry

logger = logging.getLogger(__name__)


class WorkingMemory(BaseMemory):
    """
    Working memory (active context).
    
    Features:
    - Limited number of active slots
    - Priority-based slot management
    - Automatic compression when full
    - Fast access to active context
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.max_slots = self.config.get("max_slots", 7)
        self.compression_threshold = self.config.get("compression_threshold", 0.8)
        
        # Active slots ordered by priority
        self._slots: List[str] = []  # entry_ids in priority order
    
    async def store(self, content: Any, **kwargs) -> str:
        """Store content in working memory."""
        entry = MemoryEntry(
            content=content,
            metadata=kwargs.get("metadata", {}),
            importance=kwargs.get("importance", 0.5),
            tags=kwargs.get("tags", []),
        )
        
        # Check if we need to make room
        if len(self._slots) >= self.max_slots:
            await self._compress_or_evict()
        
        self._entries[entry.entry_id] = entry
        self._slots.append(entry.entry_id)
        
        logger.debug(f"Stored entry {entry.entry_id} in working memory")
        return entry.entry_id
    
    async def retrieve(self, query: Any, limit: int = 10) -> List[MemoryEntry]:
        """Retrieve entries from working memory."""
        results = []
        query_str = str(query).lower() if query else ""
        
        # Return entries in priority order
        for entry_id in self._slots:
            if len(results) >= limit:
                break
            
            entry = self._entries.get(entry_id)
            if entry:
                content_str = str(entry.content).lower()
                if not query_str or query_str in content_str:
                    entry.access_count += 1
                    entry.last_accessed = datetime.utcnow()
                    results.append(entry)
        
        return results
    
    async def get(self, entry_id: str) -> Optional[MemoryEntry]:
        """Get a specific entry by ID."""
        entry = self._entries.get(entry_id)
        if entry:
            entry.access_count += 1
            entry.last_accessed = datetime.utcnow()
            # Move to front of priority
            if entry_id in self._slots:
                self._slots.remove(entry_id)
                self._slots.append(entry_id)
        return entry
    
    async def delete(self, entry_id: str) -> bool:
        """Delete an entry by ID."""
        if entry_id in self._entries:
            del self._entries[entry_id]
            if entry_id in self._slots:
                self._slots.remove(entry_id)
            return True
        return False
    
    async def clear(self) -> None:
        """Clear all entries."""
        self._entries.clear()
        self._slots.clear()
    
    async def _compress_or_evict(self) -> None:
        """Compress or evict entries when at capacity."""
        if not self._slots:
            return
        
        # Find lowest priority entry (first in list)
        evict_id = self._slots[0]
        entry = self._entries.get(evict_id)
        
        if entry:
            # Check if entry should be compressed (summarized) or evicted
            if entry.importance >= self.compression_threshold:
                # Compress: reduce content but keep entry
                entry.content = self._compress_content(entry.content)
                entry.metadata["compressed"] = True
                # Move to end (higher priority)
                self._slots.remove(evict_id)
                self._slots.append(evict_id)
                logger.debug(f"Compressed entry {evict_id}")
            else:
                # Evict lowest priority
                await self.delete(evict_id)
                logger.debug(f"Evicted entry {evict_id} from working memory")
    
    def _compress_content(self, content: Any) -> Any:
        """Compress content (simple truncation for now)."""
        if isinstance(content, str):
            # Keep first 200 chars as summary
            if len(content) > 200:
                return content[:200] + "..."
        elif isinstance(content, dict):
            # Keep only key fields
            return {k: v for k, v in list(content.items())[:5]}
        return content
    
    def set_priority(self, entry_id: str, priority: int) -> bool:
        """Set the priority of an entry (0 = highest)."""
        if entry_id not in self._slots:
            return False
        
        self._slots.remove(entry_id)
        priority = max(0, min(priority, len(self._slots)))
        self._slots.insert(priority, entry_id)
        return True
    
    def get_active_context(self) -> List[MemoryEntry]:
        """Get all active entries in priority order."""
        return [
            self._entries[eid] for eid in self._slots
            if eid in self._entries
        ]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        stats = super().get_stats()
        stats.update({
            "max_slots": self.max_slots,
            "active_slots": len(self._slots),
            "compression_threshold": self.compression_threshold,
        })
        return stats