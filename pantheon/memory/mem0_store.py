"""mem0 persistent memory store — local Qdrant backend."""

from __future__ import annotations

import logging
from typing import Any

from pantheon.config import settings

log = logging.getLogger(__name__)

# Default user ID for all Pantheon memories
_USER_ID = "bryan"


class MemoryStore:
    """Wrapper around mem0 with local Ollama + Qdrant backend."""

    def __init__(self):
        self._memory = None
        self._init_error: str | None = None

    def initialize(self):
        """Eagerly connect to Qdrant. Call at startup to avoid first-message delay."""
        self._ensure_initialized()

    def _ensure_initialized(self):
        """Lazy init — only connect when first used."""
        if self._memory is not None:
            return
        if self._init_error:
            raise RuntimeError(self._init_error)

        try:
            from mem0 import Memory

            config = {
                "llm": {
                    "provider": "openai",
                    "config": {
                        "model": settings.ollama_model,
                        "openai_base_url": f"{settings.ollama_base_url.rstrip('/')}/v1",
                        "api_key": "ollama",  # Required by client but ignored by server
                    },
                },
                "embedder": {
                    "provider": "openai",
                    "config": {
                        "model": settings.embedding_model,
                        "openai_base_url": f"{settings.ollama_base_url.rstrip('/')}/v1",
                        "api_key": "ollama",
                    },
                },
                "vector_store": {
                    "provider": "qdrant",
                    "config": {
                        "host": settings.qdrant_host,
                        "port": settings.qdrant_port,
                        "collection_name": "pantheon_memories",
                        "embedding_model_dims": 768,
                    },
                },
            }
            self._memory = Memory.from_config(config)
            log.debug("Memory store initialized (Qdrant @ %s:%s)", settings.qdrant_host, settings.qdrant_port)

        except Exception as e:
            self._init_error = str(e)
            log.error("Failed to initialize memory store: %s", e)
            raise

    def search(self, query: str, limit: int = 5) -> list[str]:
        """Search for relevant memories."""
        self._ensure_initialized()
        try:
            results = self._memory.search(query, user_id=_USER_ID, limit=limit)
            return [r.get("memory", r.get("text", str(r))) for r in results.get("results", results) if r]
        except Exception as e:
            log.warning("Memory search error: %s", e)
            return []

    def add(self, content: str, metadata: dict[str, Any] | None = None) -> None:
        """Add a new memory."""
        self._ensure_initialized()
        try:
            self._memory.add(content, user_id=_USER_ID, metadata=metadata or {})
        except Exception as e:
            log.warning("Memory add error: %s", e)

    def get_all(self) -> list[str]:
        """Retrieve all stored memories."""
        self._ensure_initialized()
        try:
            results = self._memory.get_all(user_id=_USER_ID)
            return [r.get("memory", r.get("text", str(r))) for r in results.get("results", results) if r]
        except Exception as e:
            log.warning("Memory get_all error: %s", e)
            return []
