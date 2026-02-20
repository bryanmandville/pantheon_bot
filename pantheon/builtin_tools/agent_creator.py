"""Agent creator tool — create/list/delete custom tool scripts."""

from __future__ import annotations

from pathlib import Path

from pantheon.config import settings
from pantheon.core.tools import tool

_TEMPLATE = '''"""Auto-generated agent: {name}"""

from pantheon.core.tools import tool


@tool(
    "{name}",
    "{description}",
    {params},
)
async def {name}({param_args}) -> str:
    """{description}"""
    # TODO: Implement
    return "Not implemented yet"
'''


@tool(
    "create_agent",
    "Create a new tool script in the agents/ directory",
    {
        "name": {"type": "string", "description": "Tool function name (snake_case)"},
        "description": {"type": "string", "description": "What the tool does"},
        "code": {
            "type": "string",
            "description": "Full Python code. MUST use: @tool('name', 'desc', {params}) decorator syntax. Do NOT use simple @tool.",
            "optional": True,
        },
    },
)
def create_agent(name: str, description: str, code: str = "") -> str:
    """Create a new agent script in agents/ directory."""
    agents_dir = settings.agents_dir
    agents_dir.mkdir(parents=True, exist_ok=True)

    filepath = agents_dir / f"{name}.py"
    if filepath.exists():
        return f"Agent '{name}' already exists. Delete it first or choose a different name."

    if code:
        # Use provided code
        content = code
    else:
        # Generate from template
        content = _TEMPLATE.format(
            name=name,
            description=description,
            params='{"input": {"type": "string", "description": "Input to the tool"}}',
            param_args="input: str",
        )

    filepath.write_text(content, encoding="utf-8")
    
    # Reload tools immediately
    from pantheon.core.tools import discover_user_agents
    discover_user_agents()
    
    return f"Created and loaded agent: {filepath.name}. You can use it immediately."


@tool(
    "list_agents",
    "List all custom tool scripts in agents/ directory",
    {},
)
def list_agents() -> str:
    """List available custom agent scripts."""
    agents_dir = settings.agents_dir
    if not agents_dir.exists():
        return "No agents directory found."

    scripts = [f.name for f in agents_dir.glob("*.py") if not f.name.startswith("_")]
    if not scripts:
        return "No custom agents found."
    return "Custom agents:\n" + "\n".join(f"- {s}" for s in sorted(scripts))


@tool(
    "delete_agent",
    "Delete a custom tool script from agents/ directory",
    {"name": {"type": "string", "description": "Agent name (without .py)"}},
)
def delete_agent(name: str) -> str:
    """Delete a custom agent script."""
    filepath = settings.agents_dir / f"{name}.py"
    if not filepath.exists():
        return f"Agent '{name}' not found."
    filepath.unlink()
    
    # Remove from registry
    from pantheon.core.tools import unregister_tool
    unregister_tool(name)
    
    return f"Deleted and unloaded agent: {name}.py"
