"""Shell tool — execute allowlisted commands."""

from __future__ import annotations

import asyncio
import logging

from pantheon.config import settings
from pantheon.core.tools import tool

log = logging.getLogger(__name__)


@tool(
    "run_command",
    "Execute an allowlisted shell command and return its output",
    {"command": {"type": "string", "description": "Shell command to execute"}},
)
async def run_command(command: str) -> str:
    """Run a shell command if it's on the allowlist."""
    # Extract the base command (first word)
    base_cmd = command.strip().split()[0] if command.strip() else ""

    if base_cmd not in settings.shell_allowlist:
        return (
            f"Command '{base_cmd}' is not allowlisted. "
            f"Allowed: {', '.join(sorted(settings.shell_allowlist))}"
        )

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)

        output_parts = []
        if stdout:
            output_parts.append(stdout.decode("utf-8", errors="replace").strip())
        if stderr:
            output_parts.append(f"STDERR: {stderr.decode('utf-8', errors='replace').strip()}")
        if proc.returncode != 0:
            output_parts.append(f"Exit code: {proc.returncode}")

        result = "\n".join(output_parts)
        # Truncate very long output
        if len(result) > 4000:
            result = result[:4000] + "\n... (output truncated)"
        return result or "(no output)"

    except asyncio.TimeoutError:
        return "Command timed out after 30 seconds."
    except Exception as e:
        log.error("Shell command failed: %s", e)
        return f"Command failed: {e}"
