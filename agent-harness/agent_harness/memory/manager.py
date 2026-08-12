"""
Memory Manager - Unified memory management interface.

Coordinates short-term, long-term, and working memory.
"""

from typing import Any, Dict, List, Optional
import logging

from agent_harness.memory.base import MemoryEntry
from agent_harness.memory.short_term import ShortTermMemory
from agent_harness.memory.long_term import LongTermMemory
from agent_harness.memory.working import WorkingMemory

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Unified memory manager that coordinates all memory types.
    
    Provides a single interface for storing and retrieving memories
    across short-term, long-term, and working memory.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # Initialize memory components
        stm_config = self.config.get("short_term", {})
        wm_config = self.config.get("working", {})
        ltm_config = self.config.get("long_term", {})
        
        self.short_term = ShortTermMemory(stm_config) if stm_config.get("enabled", True) else None
        self.working = WorkingMemory(wm_config) if wm_config.get("enabled", True) else None
        self.long_term = LongTermMemory(ltm_config) if ltm_config.get("enabled", True) else None
        
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize all memory components."""
        if self.short_term:
            await self.short_term.initialize()
        if self.working:
            await self.working.initialize()
        if self.long_term:
            await self.long_term.initialize()
        
        self._initialized = True
        logger.info("Memory manager initialized")
    
    async def close(self) -> None:
        """Close all memory components."""
        if self.short_term:
            await self.short_term.close()
        if self.working:
            await self.working.close()
        if self.long_term:
            await self.long_term.close()
        
        self._initialized = False
    
    async def store(
        self,
        content: Any,
        memory_type: str = "auto",
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
        **kwargs
    ) -> str:
        """
        Store content in memory.
        
        Args:
            content: The content to store
            memory_type: Where to store ("short_term", "long_term", "working", "auto")
            importance: Importance score (0.0-1.0)
            tags: Optional tags for categorization
            **kwargs: Additional metadata
            
        Returns:
            The entry ID
        """
        tags = tags or []
        
        # Auto-determine memory type based on importance
        if memory_type == "auto":
            if importance >= 0.7:
                memory_type = "long_term"
            elif importance >= 0.4:
                memory_type = "short_term"
            else:
                memory_type = "working"
        
        entry_id = None
        
        if memory_type == "short_term" and self.short_term:
            entry_id = await self.short_term.store(
                content, importance=importance, tags=tags, **kwargs
            )
        elif memory_type == "long_term" and self.long_term:
            entry_id = await self.long_term.store(
                content, importance=importance, tags=tags, **kwargs
            )
        elif memory_type == "working" and self.working:
            entry_id = await self.working.store(
                content, importance=importance, tags=tags, **kwargs
            )
        else:
            # Fallback to short_term
            if self.short_term:
                entry_id = await self.short_term.store(
                    content, importance=importance, tags=tags, **kwargs
                )
        
        return entry_id
    
    async def retrieve(
        self,
        query: Any,
        limit: int = 10,
        memory_types: Optional[List[str]] = None
    ) -> List[MemoryEntry]:
        """
        Retrieve memories matching the query from all memory types.
        
        Args:
            query: The search query
            limit: Maximum number of results
            memory_types: Which memory types to search (default: all)
            
        Returns:
            List of matching memory entries
        """
        memory_types = memory_types or ["working", "short_term", "long_term"]
        results = []
        
        # Search in priority order: working -> short_term -> long_term
        if "working" in memory_types and self.working:
            entries = await self.working.retrieve(query, limit)
            results.extend(entries)
        
        if "short_term" in memory_types and self.short_term:
            entries = await self.short_term.retrieve(query, limit - len(results))
            results.extend(entries)
        
        if "long_term" in memory_types and self.long_term:
            entries = await self.long_term.retrieve(query, limit - len(results))
            results.extend(entries)
        
        # Sort by importance and recency
        results.sort(
            key=lambda e: (e.importance, e.timestamp),
            reverse=True
        )
        
        return results[:limit]
    
    async def get(self, entry_id: str) -> Optional[MemoryEntry]:
        """Get a specific entry by ID from any memory type."""
        if self.working:
            entry = await self.working.get(entry_id)
            if entry:
                return entry
        
        if self.short_term:
            entry = await self.short_term.get(entry_id)
            if entry:
                return entry
        
        if self.long_term:
            entry = await self.long_term.get(entry_id)
            if entry:
                return entry
        
        return None
    
    async def delete(self, entry_id: str) -> bool:
        """Delete an entry from any memory type."""
        deleted = False
        
        if self.working:
            deleted = await self.working.delete(entry_id) or deleted
        if self.short_term:
            deleted = await self.short_term.delete(entry_id) or deleted
        if self.long_term:
            deleted = await self.long_term.delete(entry_id) or deleted
        
        return deleted
    
    async def clear(self, memory_type: Optional[str] = None) -> None:
        """
        Clear memory.
        
        Args:
            memory_type: Which memory to clear (None = all)
        """
        if memory_type is None or memory_type == "working":
            if self.working:
                await self.working.clear()
        if memory_type is None or memory_type == "short_term":
            if self.short_term:
                await self.short_term.clear()
        if memory_type is None or memory_type == "long_term":
            if self.long_term:
                await self.long_term.clear()
    
    async def consolidate(self) -> Dict[str, Any]:
        """
        Consolidate memories across all types.
        
        Moves important short-term memories to long-term storage.
        """
        results = {"promoted": 0, "removed": 0}
        
        # Promote important short-term memories to long-term
        if self.short_term and self.long_term:
            for entry in list(self.short_term._entries.values()):
                if entry.importance >= 0.7:
                    await self.long_term.store(
                        entry.content,
                        importance=entry.importance,
                        tags=entry.tags,
                        metadata=entry.metadata
                    )
                    await self.short_term.delete(entry.entry_id)
                    results["promoted"] += 1
        
        # Run long-term consolidation
        if self.long_term:
            ltm_results = await self.long_term.consolidate()
            results["removed"] += ltm_results.get("removed", 0)
        
        return results
    
    def get_context_window(self, max_items: int = 10) -> List[MemoryEntry]:
        """
        Get the current context window for agent use.
        
        Combines working memory and recent short-term memory.
        """
        context = []
        
        # Add working memory first (highest priority)
        if self.working:
            context.extend(self.working.get_active_context())
        
        # Fill remaining with recent short-term
        remaining = max_items - len(context)
        if remaining > 0 and self.short_term:
            recent = self.short_term.get_recent(remaining)
            context.extend(recent)
        
        return context[:max_items]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for all memory types."""
        stats = {
            "initialized": self._initialized,
            "short_term": self.short_term.get_stats() if self.short_term else None,
            "working": self.working.get_stats() if self.working else None,
            "long_term": self.long_term.get_stats() if self.long_term else None,
        }
        return stats
    
    async def export(self) -> Dict[str, Any]:
        """Export all memory data."""
        return {
            "short_term": await self.short_term.export() if self.short_term else None,
            "working": await self.working.export() if self.working else None,
            "long_term": await self.long_term.export() if self.long_term else None,
        }
    
    async def import_data(self, data: Dict[str, Any]) -> None:
        """Import memory data."""
        if data.get("short_term") and self.short_term:
            await self.short_term.import_data(data["short_term"])
        if data.get("working") and self.working:
            await self.working.import_data(data["working"])
        if data.get("long_term") and self.long_term:
            await self.long_term.import_data(data["long_term"])