"""Allowlist manager — dynamically add commands to shell allowlist."""

from __future__ import annotations

import asyncio
import logging

from pantheon.config import settings
from pantheon.core.tools import tool

log = logging.getLogger(__name__)


@tool(
    "request_shell_access",
    "Request permission to execute a shell command that is not currently allowlisted. "
    "Usage: Call this when a user asks to run a command (e.g. 'git') that fails with 'not allowlisted'. "
    "This tool will ask the user for confirmation and add it to the allowlist.",
    {"command": {"type": "string", "description": "The command (executable name) to allow"}},
)
async def request_shell_access(command: str) -> str:
    """Request user permission to add a command to the allowlist."""
    base_cmd = command.strip().split()[0] if command.strip() else ""
    
    if not base_cmd:
        return "Invalid command."

    if base_cmd in settings.shell_allowlist:
        return f"Command '{base_cmd}' is already allowed."

    # Ask user for confirmation via abstract provider (CLI or Telegram)
    from pantheon.core.interaction import get_interaction
    
    print(f"\n\n[SYSTEM] APEX requests access to run: '{base_cmd}'")
    try:
        interaction = get_interaction()
        approved = await interaction.confirm(f"Do you want to allow '{base_cmd}'?")
    except Exception as e:
        log.error("Failed to get user confirmation: %s", e)
        return f"Failed to ask for permission: {e}"

    if not approved:
        return f"Access denied. User rejected '{base_cmd}'."

    # Update persistent file
    allowlist_path = settings.project_root / "SHELL_ALLOWLIST"
    try:
        if allowlist_path.exists():
            content = allowlist_path.read_text(encoding="utf-8")
            if base_cmd not in content:
                with allowlist_path.open("a", encoding="utf-8") as f:
                    f.write(f"\n{base_cmd}")
        else:
             # Should have been created by config, but just in case
             with allowlist_path.open("w", encoding="utf-8") as f:
                 f.write(f"# APEX Shell Allowlist\n{base_cmd}\n")
    except Exception as e:
        return f"Failed to persist allowlist change: {e}"

    # Update runtime settings
    settings.shell_allowlist.append(base_cmd)
    
    return f"Access granted. Command '{base_cmd}' has been added to the allowlist. You can now run it."
