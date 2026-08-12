"""Tests for memory management module."""

import pytest
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_harness.memory.short_term import ShortTermMemory
from agent_harness.memory.working import WorkingMemory
from agent_harness.memory.manager import MemoryManager


@pytest.fixture
def event_loop():
    """Create event loop for tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.mark.asyncio
async def test_short_term_memory_store_and_retrieve():
    """Test storing and retrieving from short-term memory."""
    stm = ShortTermMemory({"max_size": 10})
    await stm.initialize()
    
    # Store entries
    entry_id = await stm.store("Hello world", importance=0.5)
    assert entry_id is not None
    
    # Retrieve
    results = await stm.retrieve("hello")
    assert len(results) == 1
    assert results[0].content == "Hello world"
    
    await stm.close()


@pytest.mark.asyncio
async def test_short_term_memory_eviction():
    """Test LRU eviction in short-term memory."""
    stm = ShortTermMemory({"max_size": 3, "eviction_policy": "lru"})
    await stm.initialize()
    
    # Store more than max_size
    await stm.store("Entry 1")
    await stm.store("Entry 2")
    await stm.store("Entry 3")
    await stm.store("Entry 4")  # Should evict Entry 1
    
    assert stm.size == 3
    
    # Entry 1 should be evicted
    results = await stm.retrieve("Entry 1")
    assert len(results) == 0
    
    await stm.close()


@pytest.mark.asyncio
async def test_working_memory_slots():
    """Test working memory slot management."""
    wm = WorkingMemory({"max_slots": 3})
    await wm.initialize()
    
    await wm.store("Item 1", importance=0.5)
    await wm.store("Item 2", importance=0.5)
    await wm.store("Item 3", importance=0.5)
    
    assert len(wm.get_active_context()) == 3
    
    # Adding one more should trigger eviction
    await wm.store("Item 4", importance=0.5)
    assert len(wm.get_active_context()) <= 3
    
    await wm.close()


@pytest.mark.asyncio
async def test_memory_manager():
    """Test the unified memory manager."""
    config = {
        "short_term": {"enabled": True, "max_size": 50},
        "working": {"enabled": True, "max_slots": 5},
        "long_term": {"enabled": True, "backend": "file", "path": "data/test_memory"},
    }
    
    mm = MemoryManager(config)
    await mm.initialize()
    
    # Store with different importance levels
    await mm.store("Low importance", importance=0.2)
    await mm.store("Medium importance", importance=0.5)
    await mm.store("High importance", importance=0.9)
    
    # Retrieve
    results = await mm.retrieve("importance", limit=5)
    assert len(results) > 0
    
    # Get stats
    stats = mm.get_stats()
    assert stats["initialized"] is True
    
    await mm.close()


@pytest.mark.asyncio
async def test_memory_consolidation():
    """Test memory consolidation."""
    config = {
        "short_term": {"enabled": True, "max_size": 50},
        "working": {"enabled": True, "max_slots": 5},
        "long_term": {"enabled": True, "backend": "file", "path": "data/test_memory"},
    }
    
    mm = MemoryManager(config)
    await mm.initialize()
    
    # Store high importance item
    await mm.store("Important fact", importance=0.9)
    
    # Consolidate
    result = await mm.consolidate()
    assert "promoted" in result
    assert "removed" in result
    
    await mm.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])