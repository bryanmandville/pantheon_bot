"""System prompt builder — assembles SOUL.md + USER.md + TOOLS.md."""

from __future__ import annotations

import logging
from pathlib import Path

from pantheon.config import settings

log = logging.getLogger(__name__)


def _read_file(path: Path) -> str:
    """Read a file, return empty string if missing."""
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        log.warning("Prompt file not found: %s", path)
        return ""


def build_system_prompt() -> str:
    """Assemble the system prompt from markdown files.

    Re-reads files each call so agent self-edits take effect immediately.
    TOOLS.md is omitted — tool schemas are sent separately via Ollama's tool API.
    """
    soul = _read_file(settings.prompts_dir / "SOUL.md")
    user = _read_file(settings.prompts_dir / "USER.md")

    parts = [p for p in [soul, user] if p]
    return "\n\n---\n\n".join(parts)


def build_memory_context(memories: list[str]) -> str:
    """Format retrieved memories as a context block for injection.

    Returns empty string if no memories, so it adds zero tokens.
    """
    if not memories:
        return ""

    mem_text = "\n".join(f"- {m}" for m in memories)
    return f"# Relevant Memories\n{mem_text}"
