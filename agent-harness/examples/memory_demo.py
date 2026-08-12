"""
Memory Management Demo

Demonstrates the memory management capabilities of Agent Harness.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_harness.memory.manager import MemoryManager
from agent_harness.utils.logger import setup_logger

logger = setup_logger(level="INFO")


async def main():
    """Run the memory management demo."""
    print("=" * 50)
    print("Agent Harness - Memory Management Demo")
    print("=" * 50)
    
    # Create memory manager with configuration
    config = {
        "short_term": {
            "enabled": True,
            "max_size": 50,
            "ttl": 3600,
            "eviction_policy": "lru",
        },
        "working": {
            "enabled": True,
            "max_slots": 5,
        },
        "long_term": {
            "enabled": True,
            "backend": "file",
            "path": "data/memory/long_term",
        },
    }
    
    memory = MemoryManager(config)
    await memory.initialize()
    
    print("\n1. Storing memories with different importance levels...")
    
    # Store some memories
    memories = [
        ("User's name is Alice", 0.8, ["user_info", "name"]),
        ("User prefers dark mode", 0.6, ["preference", "ui"]),
        ("Last conversation was about Python", 0.4, ["context", "history"]),
        ("User asked about machine learning", 0.7, ["topic", "ml"]),
        ("Temporary calculation: 2+2=4", 0.2, ["temp"]),
    ]
    
    for content, importance, tags in memories:
        entry_id = await memory.store(
            content,
            importance=importance,
            tags=tags,
        )
        print(f"  Stored: '{content}' (importance: {importance}) -> {entry_id[:8]}...")
    
    print("\n2. Retrieving memories by query...")
    
    # Retrieve memories
    queries = ["user", "Python", "machine learning"]
    
    for query in queries:
        results = await memory.retrieve(query, limit=3)
        print(f"\n  Query: '{query}'")
        for entry in results:
            print(f"    - {entry.content} (importance: {entry.importance})")
    
    print("\n3. Getting context window...")
    
    context = memory.get_context_window(max_items=5)
    print(f"  Context window ({len(context)} items):")
    for entry in context:
        print(f"    - {entry.content[:50]}...")
    
    print("\n4. Memory statistics...")
    
    stats = memory.get_stats()
    print(f"  Short-term: {stats['short_term']['size']} entries")
    print(f"  Working: {stats['working']['size']} entries")
    print(f"  Long-term: {stats['long_term']['size']} entries")
    
    print("\n5. Memory consolidation...")
    
    result = await memory.consolidate()
    print(f"  Promoted: {result['promoted']}")
    print(f"  Removed: {result['removed']}")
    
    # Cleanup
    await memory.close()
    
    print("\n" + "=" * 50)
    print("Memory demo completed!")


if __name__ == "__main__":
    asyncio.run(main())