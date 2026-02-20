"""Memory tools — search, add, list persistent memories via mem0."""

from __future__ import annotations

import asyncio

from pantheon.core.tools import tool

# Memory store reference — set by main.py at startup
_memory_store = None


def set_memory_store(store) -> None:
    """Set the global memory store reference."""
    global _memory_store
    _memory_store = store


@tool(
    "search_memory",
    "Search persistent memory for relevant facts and past context",
    {"query": {"type": "string", "description": "What to search for"}},
)
async def search_memory(query: str) -> str:
    """Search mem0 for relevant memories."""
    if not _memory_store:
        return "Memory store not available."
    results = await asyncio.to_thread(_memory_store.search, query)
    if not results:
        return "No relevant memories found."
    return "\n".join(f"- {m}" for m in results)


@tool(
    "add_memory",
    "Store a new fact or important information in persistent memory",
    {"content": {"type": "string", "description": "The fact or information to remember"}},
)
async def add_memory(content: str) -> str:
    """Add a new memory to mem0."""
    if not _memory_store:
        return "Memory store not available."
    await asyncio.to_thread(_memory_store.add, content)
    return f"Stored in memory: {content[:80]}..."


@tool(
    "list_memories",
    "List all facts stored in persistent memory",
    {},
)
async def list_memories() -> str:
    """List all memories from mem0."""
    if not _memory_store:
        return "Memory store not available."
    memories = await asyncio.to_thread(_memory_store.get_all)
    if not memories:
        return "No memories stored yet."
    return "\n".join(f"- {m}" for m in memories)
