"""File editor tool — read/write SOUL.md, USER.md, TOOLS.md, schedules."""

from __future__ import annotations

import logging
from pathlib import Path

from pantheon.config import settings
from pantheon.core.tools import tool

log = logging.getLogger(__name__)

# Allowed directories for file operations
_ALLOWED_DIRS = {
    "prompts": settings.prompts_dir,
    "schedules": settings.schedules_dir,
}


def _resolve_path(path: str) -> Path:
    """Resolve a path, ensuring it's within allowed directories.

    Accepts: 'SOUL.md', 'prompts/SOUL.md', 'schedules/CRON.md', etc.
    """
    p = Path(path)

    # If it's just a filename, try to find it in allowed dirs
    if not p.parent.name or p.parent.name == ".":
        for dir_path in _ALLOWED_DIRS.values():
            candidate = dir_path / p.name
            if candidate.exists():
                return candidate
        # Default to prompts dir for new files
        return settings.prompts_dir / p.name

    # If it starts with an allowed dir name
    for dir_name, dir_path in _ALLOWED_DIRS.items():
        if p.parts[0] == dir_name:
            resolved = dir_path / Path(*p.parts[1:])
            return resolved

    raise ValueError(f"Path not in allowed directories: {path}")


@tool(
    "read_file",
    "Read the contents of a prompt or schedule file",
    {"path": {"type": "string", "description": "File path (e.g. 'SOUL.md', 'schedules/CRON.md')"}},
)
def read_file(path: str) -> str:
    """Read a file from prompts/ or schedules/ directory."""
    resolved = _resolve_path(path)
    if not resolved.exists():
        return f"File not found: {path}"
    return f"File content of '{resolved.name}':\n```\n{resolved.read_text(encoding='utf-8')}\n```"


@tool(
    "write_file",
    "Write/overwrite a prompt or schedule file",
    {
        "path": {"type": "string", "description": "File path (e.g. 'SOUL.md', 'schedules/HEARTBEAT.md')"},
        "content": {"type": "string", "description": "New file content"},
    },
)
def write_file(path: str, content: str) -> str:
    """Write content to a file in prompts/ or schedules/ directory."""
    resolved = _resolve_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")
    return f"Written: {resolved.name} ({len(content)} chars)"


@tool(
    "append_file",
    "Append content to a prompt or schedule file",
    {
        "path": {"type": "string", "description": "File path"},
        "content": {"type": "string", "description": "Content to append"},
    },
)
def append_file(path: str, content: str) -> str:
    """Append content to a file in prompts/ or schedules/ directory."""
    resolved = _resolve_path(path)
    if not resolved.exists():
        return f"File not found: {path}"
    with open(resolved, "a", encoding="utf-8") as f:
        f.write("\n" + content)
    return f"Appended to: {resolved.name} ({len(content)} chars)"
