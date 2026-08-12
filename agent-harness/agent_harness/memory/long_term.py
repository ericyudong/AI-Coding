"""
Long-term memory implementation.

Provides persistent storage with optional vector similarity search.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import logging
import asyncio

from agent_harness.memory.base import BaseMemory, MemoryEntry

logger = logging.getLogger(__name__)


class LongTermMemory(BaseMemory):
    """
    Long-term memory (persistent storage).
    
    Features:
    - Persistent storage (SQLite or file-based)
    - Optional vector similarity search
    - Memory consolidation
    - Importance-based retention
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.backend = self.config.get("backend", "file")
        self.storage_path = Path(self.config.get("path", "data/memory/long_term"))
        self.vector_enabled = self.config.get("vector_store", {}).get("enabled", False)
        self.vector_dimension = self.config.get("vector_store", {}).get("dimension", 1536)
        
        # Consolidation settings
        consolidation = self.config.get("consolidation", {})
        self.consolidation_enabled = consolidation.get("enabled", True)
        self.consolidation_interval = consolidation.get("interval", 300)
        self.min_importance = consolidation.get("min_importance", 0.5)
        
        self._db = None
        self._consolidation_task = None
    
    async def initialize(self) -> None:
        """Initialize long-term memory storage."""
        # Ensure storage directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        if self.backend == "file":
            await self._init_file_storage()
        elif self.backend == "sqlite":
            await self._init_sqlite_storage()
        
        # Start consolidation task if enabled
        if self.consolidation_enabled:
            self._consolidation_task = asyncio.create_task(self._consolidation_loop())
        
        self._initialized = True
        logger.info(f"Long-term memory initialized with {self.backend} backend")
    
    async def _init_file_storage(self) -> None:
        """Initialize file-based storage."""
        self.storage_file = self.storage_path.with_suffix(".json")
        if self.storage_file.exists():
            await self._load_from_file()
    
    async def _init_sqlite_storage(self) -> None:
        """Initialize SQLite storage."""
        try:
            import aiosqlite
            db_path = self.storage_path.with_suffix(".db")
            self._db = await aiosqlite.connect(str(db_path))
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    entry_id TEXT PRIMARY KEY,
                    content TEXT,
                    metadata TEXT,
                    timestamp TEXT,
                    importance REAL,
                    access_count INTEGER,
                    last_accessed TEXT,
                    tags TEXT
                )
            """)
            await self._db.commit()
        except ImportError:
            logger.warning("aiosqlite not available, falling back to file storage")
            self.backend = "file"
            await self._init_file_storage()
    
    async def _load_from_file(self) -> None:
        """Load entries from file."""
        try:
            with open(self.storage_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for entry_id, entry_data in data.get("entries", {}).items():
                    self._entries[entry_id] = MemoryEntry.from_dict(entry_data)
            logger.info(f"Loaded {len(self._entries)} entries from file")
        except Exception as e:
            logger.error(f"Error loading from file: {e}")
    
    async def _save_to_file(self) -> None:
        """Save entries to file."""
        try:
            data = {
                "entries": {
                    entry_id: entry.to_dict()
                    for entry_id, entry in self._entries.items()
                }
            }
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving to file: {e}")
    
    async def store(self, content: Any, **kwargs) -> str:
        """Store content in long-term memory."""
        entry = MemoryEntry(
            content=content,
            metadata=kwargs.get("metadata", {}),
            importance=kwargs.get("importance", 0.5),
            tags=kwargs.get("tags", []),
        )
        
        self._entries[entry.entry_id] = entry
        
        # Persist based on backend
        if self.backend == "file":
            await self._save_to_file()
        elif self.backend == "sqlite" and self._db:
            await self._save_to_sqlite(entry)
        
        logger.debug(f"Stored entry {entry.entry_id} in long-term memory")
        return entry.entry_id
    
    async def _save_to_sqlite(self, entry: MemoryEntry) -> None:
        """Save entry to SQLite."""
        try:
            await self._db.execute(
                """
                INSERT OR REPLACE INTO memories 
                (entry_id, content, metadata, timestamp, importance, access_count, last_accessed, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.entry_id,
                    json.dumps(entry.content, default=str),
                    json.dumps(entry.metadata, default=str),
                    entry.timestamp.isoformat(),
                    entry.importance,
                    entry.access_count,
                    entry.last_accessed.isoformat() if entry.last_accessed else None,
                    json.dumps(entry.tags),
                )
            )
            await self._db.commit()
        except Exception as e:
            logger.error(f"Error saving to SQLite: {e}")
    
    async def retrieve(self, query: Any, limit: int = 10) -> List[MemoryEntry]:
        """Retrieve entries matching the query."""
        results = []
        query_str = str(query).lower() if query else ""
        
        # Score entries by relevance
        scored_entries = []
        for entry in self._entries.values():
            score = self._calculate_relevance(entry, query_str)
            if score > 0:
                scored_entries.append((score, entry))
        
        # Sort by score (descending) and importance
        scored_entries.sort(key=lambda x: (x[0], x[1].importance), reverse=True)
        
        for score, entry in scored_entries[:limit]:
            entry.access_count += 1
            entry.last_accessed = datetime.utcnow()
            results.append(entry)
        
        return results
    
    def _calculate_relevance(self, entry: MemoryEntry, query: str) -> float:
        """Calculate relevance score for an entry."""
        if not query:
            return entry.importance
        
        content_str = str(entry.content).lower()
        tags_str = " ".join(entry.tags).lower()
        
        score = 0.0
        
        # Text matching
        if query in content_str:
            score += 1.0
        if query in tags_str:
            score += 0.5
        
        # Word overlap
        query_words = set(query.split())
        content_words = set(content_str.split())
        overlap = len(query_words & content_words)
        if overlap > 0:
            score += overlap / len(query_words)
        
        # Importance weighting
        score *= (0.5 + entry.importance * 0.5)
        
        # Recency bonus
        age_days = (datetime.utcnow() - entry.timestamp).days
        recency_bonus = max(0, 1 - age_days / 30)  # Decay over 30 days
        score += recency_bonus * 0.1
        
        return score
    
    async def get(self, entry_id: str) -> Optional[MemoryEntry]:
        """Get a specific entry by ID."""
        entry = self._entries.get(entry_id)
        if entry:
            entry.access_count += 1
            entry.last_accessed = datetime.utcnow()
        return entry
    
    async def delete(self, entry_id: str) -> bool:
        """Delete an entry by ID."""
        if entry_id in self._entries:
            del self._entries[entry_id]
            
            if self.backend == "file":
                await self._save_to_file()
            elif self.backend == "sqlite" and self._db:
                await self._db.execute("DELETE FROM memories WHERE entry_id = ?", (entry_id,))
                await self._db.commit()
            
            return True
        return False
    
    async def _consolidation_loop(self) -> None:
        """Periodic memory consolidation."""
        while self._initialized:
            await asyncio.sleep(self.consolidation_interval)
            await self.consolidate()
    
    async def consolidate(self) -> Dict[str, Any]:
        """
        Consolidate memory by removing low-importance entries
        and summarizing related entries.
        """
        if not self.consolidation_enabled:
            return {"removed": 0, "consolidated": 0}
        
        removed = 0
        consolidated = 0
        
        # Remove low-importance, rarely accessed entries
        to_remove = []
        for entry_id, entry in self._entries.items():
            if (entry.importance < self.min_importance and 
                entry.access_count < 2 and
                (datetime.utcnow() - entry.timestamp).days > 7):
                to_remove.append(entry_id)
        
        for entry_id in to_remove:
            await self.delete(entry_id)
            removed += 1
        
        # TODO: Implement summarization of related entries
        
        logger.info(f"Memory consolidation: removed {removed}, consolidated {consolidated}")
        return {"removed": removed, "consolidated": consolidated}
    
    async def close(self) -> None:
        """Close and cleanup."""
        if self._consolidation_task:
            self._consolidation_task.cancel()
            try:
                await self._consolidation_task
            except asyncio.CancelledError:
                pass
        
        if self.backend == "file":
            await self._save_to_file()
        elif self._db:
            await self._db.close()
        
        self._initialized = False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        stats = super().get_stats()
        stats.update({
            "backend": self.backend,
            "vector_enabled": self.vector_enabled,
            "consolidation_enabled": self.consolidation_enabled,
        })
        return stats