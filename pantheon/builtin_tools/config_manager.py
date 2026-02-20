"""Config manager tool — request sensitive configuration values from the user."""

from __future__ import annotations

import logging
from pathlib import Path

from pantheon.config import settings
from pantheon.core.tools import tool

log = logging.getLogger(__name__)


@tool(
    "request_config_value",
    "Request a configuration value (like an API key or password) from the user directly. "
    "Use this when APEX requires a sensitive value to proceed but it is missing from the environment. "
    "The input will be hidden from the chat history and saved securely to the .env file.",
    {
        "key": {"type": "string", "description": "The configuration key (e.g., 'OPENROUTER_API_KEY')"},
        "description": {"type": "string", "description": "A short explanation of what this value is and why it's needed"},
        "is_secret": {"type": "boolean", "description": "True if typing should be hidden (for passwords/keys)"},
    },
)
async def request_config_value(key: str, description: str, is_secret: bool = True) -> str:
    """Request a config value securely from the user."""
    key = key.strip().upper()
    if not key:
        return "Invalid key."

    from pantheon.core.interaction import get_interaction
    interaction = get_interaction()
    
    prompt = f"[SYSTEM] APEX needs configuration: {key}\nReason: {description}\nPlease enter the value:"
    
    try:
        value = await interaction.request_info(prompt, is_secret=is_secret)
    except Exception as e:
        log.error("Failed to request config value: %s", e)
        return f"Error: Failed to ask user for value ({e})"

    if not value:
        return f"User did not provide a value for {key}."

    env_path = settings.project_root / ".env"
    
    try:
        # Read existing .env
        if env_path.exists():
            lines = env_path.read_text(encoding="utf-8").splitlines()
        else:
            lines = []
            
        # Update or append
        updated = False
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{key}="):
                lines[i] = f"{key}={value}"
                updated = True
                break
                
        if not updated:
            lines.append(f"{key}={value}")
            
        # Write back
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        
    except Exception as e:
        log.error("Failed to write to .env: %s", e)
        return f"Error: Failed to save the value to .env ({e})"
        
    # Security: Do NOT return the value itself, only a success message
    return f"Success! The user provided the value for {key} and it has been securely saved to the .env file."
