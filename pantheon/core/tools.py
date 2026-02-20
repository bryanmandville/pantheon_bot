"""Tool registry — discovery, schema generation, and execution engine."""

from __future__ import annotations

import importlib
import inspect
import json
import logging
import sys
from pathlib import Path
from typing import Any, Callable, get_type_hints

from pantheon.config import settings

log = logging.getLogger(__name__)

# Global registry
_TOOLS: dict[str, dict[str, Any]] = {}


def tool(
    name: str,
    description: str,
    parameters: dict[str, Any] | None = None,
):
    """Decorator to register a function as a tool.

    Usage:
        @tool("search_memory", "Search persistent memory", {
            "query": {"type": "string", "description": "Search query"}
        })
        async def search_memory(query: str) -> str:
            ...
    """
    def decorator(func: Callable) -> Callable:
        # Build parameter schema from decorator args or type hints
        param_schema = _build_param_schema(func, parameters)

        _TOOLS[name] = {
            "name": name,
            "description": description,
            "parameters": param_schema,
            "function": func,
        }
        func._tool_name = name
        return func

    return decorator


def _build_param_schema(
    func: Callable,
    explicit_params: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build JSON Schema for tool parameters."""
    if explicit_params:
        # Convert shorthand {"param": {"type": "string", "description": "..."}}
        # to full JSON Schema
        properties = {}
        required = []
        for param_name, param_def in explicit_params.items():
            properties[param_name] = param_def
            # All params required unless marked optional
            if not param_def.get("optional", False):
                required.append(param_name)
            # Remove our custom 'optional' key from the schema
            param_def.pop("optional", None)

        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }

    # Fallback: infer from type hints
    hints = get_type_hints(func)
    sig = inspect.signature(func)
    properties = {}
    required = []

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue
        ptype = hints.get(param_name, str)
        json_type = _python_type_to_json(ptype)
        properties[param_name] = {"type": json_type, "description": param_name}
        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


def _python_type_to_json(ptype: type) -> str:
    """Map Python types to JSON Schema types."""
    mapping = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }
    return mapping.get(ptype, "string")


def get_all_tools() -> dict[str, dict[str, Any]]:
    """Get all registered tools."""
    return _TOOLS.copy()


def unregister_tool(name: str) -> bool:
    """Remove a tool from the registry.

    Returns:
        True if tool was found and removed, False otherwise.
    """
    if name in _TOOLS:
        del _TOOLS[name]
        return True
    return False


def get_tool_declarations(tool_names: list[str] | None = None) -> list[dict[str, Any]]:
    """Generate Gemini-compatible function declaration list.

    Returns dicts in the format expected by google.genai.types.Tool:
        {"name": ..., "description": ..., "parameters": {...}}

    Args:
        tool_names: Optional list of tool names to include. If None, includes all.
    """
    declarations = []
    for name, tool_def in _TOOLS.items():
        if tool_names and name not in tool_names:
            continue
        declarations.append({
            "name": name,
            "description": tool_def["description"],
            "parameters": tool_def["parameters"],
        })
    return declarations


async def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    """Execute a registered tool by name with given arguments.

    Returns the result as a string for the LLM.
    """
    tool_def = _TOOLS.get(name)
    if not tool_def:
        return f"Error: Unknown tool '{name}'"

    func = tool_def["function"]
    try:
        if inspect.iscoroutinefunction(func):
            result = await func(**arguments)
        else:
            result = func(**arguments)

        if isinstance(result, (dict, list)):
            return json.dumps(result, indent=2, default=str)
        return str(result)
    except Exception as e:
        log.error("Tool '%s' failed: %s", name, e, exc_info=True)
        return f"Error executing '{name}': {e}"


def discover_builtin_tools() -> None:
    """Import all builtin tool modules to register their tools."""
    builtin_dir = Path(__file__).parent.parent / "builtin_tools"
    for py_file in builtin_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue
        module_name = f"pantheon.builtin_tools.{py_file.stem}"
        try:
            importlib.import_module(module_name)
            log.debug("Loaded builtin tools from %s", py_file.name)
        except Exception as e:
            log.error("Failed to load %s: %s", py_file.name, e)


def discover_user_agents() -> None:
    """Import user-created agent scripts from the agents/ directory."""
    agents_dir = settings.agents_dir
    if not agents_dir.exists():
        agents_dir.mkdir(parents=True, exist_ok=True)
        return

    # Add agents dir to path so imports work
    agents_str = str(agents_dir)
    if agents_str not in sys.path:
        sys.path.insert(0, agents_str)

    for py_file in agents_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue
        module_name = py_file.stem
        try:
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)
            log.debug("Loaded user agent from %s", py_file.name)
        except Exception as e:
            log.error("Failed to load agent %s: %s", py_file.name, e)


def discover_all_tools() -> None:
    """Discover and register all tools (builtin + user agents)."""
    discover_builtin_tools()
    discover_user_agents()
    log.debug("Total tools registered: %d", len(_TOOLS))
