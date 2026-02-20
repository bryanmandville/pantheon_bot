"""CLI channel — Rich terminal interface for APEX."""

from __future__ import annotations

import asyncio
import logging
import sys

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from pantheon.core.conversation import Conversation
from pantheon.core.tools import discover_all_tools

log = logging.getLogger(__name__)

console = Console()

# CLI slash commands
_COMMANDS = {
    "/quit": "Exit the CLI",
    "/clear": "Clear conversation history",
    "/reset": "Full reset — clear history",
    "/reload": "Reload tools (discover new agents)",
    "/env": "Reload environment variables from .env",
    "/tools": "List all registered tools",
    "/memory": "Search memory (usage: /memory <query>)",
    "/help": "Show this help",
}


async def run_cli(conversation: Conversation) -> None:
    """Start the interactive CLI loop."""
    console.print(
        Panel(
            "[bold cyan]APEX[/bold cyan] — Pantheon AI Agent (Gemini 2.5 Pro)\n"
            "Type [bold]/help[/bold] for commands, [bold]/quit[/bold] to exit.",
            border_style="cyan",
        )
    )

    loop = asyncio.get_event_loop()

    while True:
        try:
            # Get user input (run in executor to not block event loop)
            user_input = await loop.run_in_executor(
                None,
                lambda: console.input("[bold green]you > [/bold green] "),
            )
        except (EOFError, KeyboardInterrupt):
            # This handles Ctrl+D (EOF) and Ctrl+C gracefully
            console.print("\n[dim]Goodbye.[/dim]")
            break
        except Exception as e:
            print(f"DEBUG: Input exception: {e}")
            log.error("CLI loop error: %s", e, exc_info=True)
            console.print(f"\n[bold red]Fatal Error:[/bold red] {e}")
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        # Handle slash commands
        if user_input.startswith("/"):
            handled = await _handle_command(user_input, conversation)
            if handled == "quit":
                break
            continue

        # Send to APEX
        console.print()
        # Send to APEX
        console.print()
        
        # Tool hooks to manage spinner state during execution
        # (Needed for interactive tools like request_shell_access)
        current_status = None
        
        async def on_tool_start(name: str, args: dict[str, Any]):
            nonlocal current_status
            if current_status:
                current_status.stop()
                current_status = None
            console.print(f"[dim]Executing tool: {name}...[/dim]")

        async def on_tool_end(name: str, result: str):
            nonlocal current_status
            if not current_status:
                current_status = console.status("[cyan]APEX is thinking...[/cyan]")
                current_status.start()

        tool_hooks = {
            "on_tool_start": on_tool_start,
            "on_tool_end": on_tool_end,
        }

        current_status = console.status("[cyan]APEX is thinking...[/cyan]")
        current_status.start()
        
        try:
            response = await conversation.send(user_input, tool_hooks=tool_hooks)
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            log.error("Conversation error: %s", e, exc_info=True)
            continue
        finally:
            if current_status:
                current_status.stop()

        # Render response as markdown
        console.print(Panel(
            Markdown(response),
            title="[bold cyan]APEX[/bold cyan]",
            border_style="dim",
        ))
        console.print()


async def _handle_command(cmd: str, conversation: Conversation) -> str | None:
    """Handle a CLI slash command. Returns 'quit' to exit."""
    parts = cmd.split(maxsplit=1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if command == "/quit" or command == "/exit":
        console.print("[dim]Goodbye.[/dim]")
        return "quit"

    elif command == "/clear":
        conversation.clear()
        console.print("[dim]Conversation cleared.[/dim]")

    elif command == "/reset":
        await conversation.reset()
        console.print("[dim]Session reset.[/dim]")

    elif command == "/reload":
        discover_all_tools()
        from pantheon.core.tools import get_all_tools
        count = len(get_all_tools())
        console.print(f"[dim]Tools reloaded. {count} tools registered.[/dim]")
        
    elif command == "/env":
        from pantheon.config import settings
        count = settings.reload_env()
        console.print(f"[dim]Environment reloaded. {count} keys updated.[/dim]")

    elif command == "/tools":
        from pantheon.core.tools import get_all_tools
        tools = get_all_tools()
        if not tools:
            console.print("[dim]No tools registered.[/dim]")
        else:
            for name, t in sorted(tools.items()):
                console.print(f"  [cyan]{name}[/cyan] — {t['description']}")

    elif command == "/memory":
        if not args:
            console.print("[dim]Usage: /memory <search query>[/dim]")
        elif conversation.memory_store:
            results = conversation.memory_store.search(args)
            if results:
                for m in results:
                    console.print(f"  [dim]•[/dim] {m}")
            else:
                console.print("[dim]No memories found.[/dim]")
        else:
            console.print("[dim]Memory store not available.[/dim]")

    elif command == "/help":
        for cmd_name, desc in _COMMANDS.items():
            console.print(f"  [cyan]{cmd_name}[/cyan] — {desc}")

    else:
        console.print(f"[dim]Unknown command: {command}. Type /help.[/dim]")

    return None
